#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCQ Task Composer
- instance-level workers
- global render lock (manim not thread-safe)
- stable tqdm layout: render output is swallowed into a global DEVNULL
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, Thread
from typing import Dict, List, Tuple, Optional

from tqdm import tqdm


# ============================================================
# 0. global silent sinks (NEVER closed)
# ============================================================

# keep them open for the whole process lifetime – manim/rich may keep references
DEVNULL_OUT = open(os.devnull, "w")
DEVNULL_ERR = open(os.devnull, "w")


class StdSwap:
    """Temporarily redirect stdout/stderr to global devnull without closing."""
    def __init__(self):
        self._old_out = None
        self._old_err = None

    def __enter__(self):
        self._old_out = sys.stdout
        self._old_err = sys.stderr
        sys.stdout = DEVNULL_OUT
        sys.stderr = DEVNULL_ERR
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._old_out
        sys.stderr = self._old_err


# ============================================================
# 1. import renderer
# ============================================================

def _import_renderer():
    here = Path(__file__).resolve()
    project_root = here.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from src.renderer import render_video, extract_frame
        return render_video, extract_frame
    except Exception as e:
        print("[FATAL] cannot import src.renderer:", e, file=sys.stderr)
    return None, None


RENDER_VIDEO, EXTRACT_FRAME = _import_renderer()
if RENDER_VIDEO is None or EXTRACT_FRAME is None:
    sys.exit(1)

# Manim is not thread-safe; use a global lock when rendering
RENDER_LOCK = Lock()


# ============================================================
# Basic utils: parse mrt_*.json filenames, load entries
# ============================================================

JSON_NAME_RE = re.compile(r"^(mrt_[eh])(\d{3})_(\d+)_([0-9]+)_s([0-3])_r([0-3])\.json$")


@dataclass
class JsonEntry:
    path: Path
    kind: str
    global_id: int
    group_id: int
    instance_id: int
    s: int
    r: int
    data: Dict


def parse_json_filename(path: Path) -> Optional[Tuple[str, int, int, int, int, int]]:
    m = JSON_NAME_RE.match(path.name)
    if not m:
        return None
    prefix, gid, grp, inst, s, r = m.groups()
    kind = prefix[-1]
    return kind, int(gid), int(grp), int(inst), int(s), int(r)


def load_json_entries_from_root(batch_dir: Path) -> List[JsonEntry]:
    out: List[JsonEntry] = []
    for p in sorted(batch_dir.glob("mrt_*.json")):
        parsed = parse_json_filename(p)
        if not parsed:
            continue
        kind, gid, grp, inst, s, r = parsed
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        out.append(JsonEntry(
            path=p,
            kind=kind,
            global_id=gid,
            group_id=grp,
            instance_id=inst,
            s=s,
            r=r,
            data=data,
        ))
    return out


def load_json_entries_from_dir(d: Path) -> List[JsonEntry]:
    out: List[JsonEntry] = []
    for p in sorted(d.glob("*.json")):
        parsed = parse_json_filename(p)
        if not parsed:
            continue
        kind, gid, grp, inst, s, r = parsed
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        out.append(JsonEntry(
            path=p,
            kind=kind,
            global_id=gid,
            group_id=grp,
            instance_id=inst,
            s=s,
            r=r,
            data=data,
        ))
    return out


def ensure_instance_dirs(instance_root: Path) -> Dict[str, Path]:
    meta = instance_root / "meta"
    task = instance_root / "task"
    guidance = instance_root / "guidance"
    meta.mkdir(parents=True, exist_ok=True)
    task.mkdir(parents=True, exist_ok=True)
    guidance.mkdir(parents=True, exist_ok=True)
    return {"meta": meta, "task": task, "guidance": guidance}


# ============================================================
# 3. compose
# ============================================================

def compose(batch_dir: Path) -> None:
    """Configs live in batch_dir/shape/; ensure img/ and video/ exist (flat, 2dr-style)."""
    shape_dir = batch_dir / "shape"
    if not shape_dir.is_dir():
        shape_dir = batch_dir
    entries = load_json_entries_from_root(shape_dir)
    grouped: Dict[str, List[JsonEntry]] = {}
    for e in entries:
        key = f"mrt_{e.kind}{e.global_id:03d}"
        grouped.setdefault(key, []).append(e)

    (batch_dir / "images").mkdir(parents=True, exist_ok=True)
    (batch_dir / "video").mkdir(parents=True, exist_ok=True)
    print(f"[INFO] compose done: {len(grouped)} instances.")


# ============================================================
# 4. s3 tag
# ============================================================

def decide_s3_tag(kind: str, by_sr: Dict[Tuple[int, int], JsonEntry]) -> str:
    key = (3, 0) if kind == "e" else (3, 3)
    if key not in by_sr or (0, 0) not in by_sr:
        return "modify"

    def count_voxels(d: Dict) -> int:
        if "voxels" in d:
            return len(d["voxels"])
        if "voxel" in d and "data" in d["voxel"]:
            return len(d["voxel"]["data"])
        return 0

    c0 = count_voxels(by_sr[(0, 0)].data)
    c3 = count_voxels(by_sr[key].data)
    if c3 == c0:
        return "move"
    if c3 == c0 - 1:
        return "remove"
    return "modify"


# ============================================================
# 5. render one json with policy
# ============================================================

def render_one_json(
    instance_key: str,
    entry: JsonEntry,
    *,
    guidance_dir: Path,
    final_name: Optional[str],
) -> Optional[Path]:
    """
    render with manim (serialized, silenced) → move to guidance_dir → return path
    """
    with RENDER_LOCK, StdSwap():
        video_path = RENDER_VIDEO(entry.path, entry.data, save_meta=False)

    if not video_path or not video_path.exists():
        # very important: we are now back to normal stdout
        tqdm.write(f"[ERROR] {instance_key}: render failed for {entry.path.name}")
        return None

    guidance_dir.mkdir(parents=True, exist_ok=True)
    if final_name:
        target = guidance_dir / final_name
    else:
        target = guidance_dir / f"{entry.path.stem}.mp4"

    try:
        shutil.move(str(video_path), str(target))
    except Exception:
        try:
            shutil.copy2(str(video_path), str(target))
        except Exception:
            tqdm.write(f"[ERROR] {instance_key}: cannot move/copy video")
            return None
    return target


# ============================================================
# 6. per-instance pipeline
# ============================================================

def process_instance(
    instance_dir: Path,
    batch_dir: Path,
    entries: List[JsonEntry],
    *,
    do_task: bool,
    do_guidance: bool,
    pbar: tqdm,
    pbar_lock: Lock,
    status_bar: tqdm,
) -> None:
    instance_key = instance_dir.name if isinstance(instance_dir, Path) else instance_dir
    if isinstance(instance_dir, Path) and (instance_dir / "task").is_dir():
        task_dir = instance_dir / "task"
        guidance_dir = instance_dir / "guidance"
    else:
        task_dir = batch_dir / "images"
        guidance_dir = batch_dir / "video"
        task_dir.mkdir(parents=True, exist_ok=True)
        guidance_dir.mkdir(parents=True, exist_ok=True)
    if not entries:
        return

    by_sr = {(e.s, e.r): e for e in entries}
    is_easy = instance_key.startswith("mrt_e")
    s3_tag = decide_s3_tag("e" if is_easy else "h", by_sr)

    def extract_to(video_fp: Path, out_path: Path, mode: str):
        # 抽帧不必抢 stdout，但为了统一也包一层
        with StdSwap():
            ok = EXTRACT_FRAME(video_fp, out_path, mode)
        return ok

    # -------------------------
    # EASY
    # -------------------------
    if is_easy:
        # s0_r0
        e_s0 = by_sr.get((0, 0))
        if e_s0:
            if do_guidance:
                status_bar.set_description_str(f"[{instance_key}] s0_r0 → guidance_easy")
                video_fp = render_one_json(
                    instance_key,
                    e_s0,
                    guidance_dir=guidance_dir,
                    final_name=f"{instance_key}_guidance_easy.mp4",
                )
            else:
                status_bar.set_description_str(f"[{instance_key}] s0_r0 → task(q,a)")
                video_fp = render_one_json(
                    instance_key,
                    e_s0,
                    guidance_dir=guidance_dir,
                    final_name=f"{e_s0.path.stem}.mp4",
                )

            if video_fp and do_task:
                q_out = task_dir / f"{instance_key}_question.jpg"
                a_out = task_dir / f"{instance_key}_answer.jpg"
                extract_to(video_fp, q_out, "first")
                extract_to(video_fp, a_out, "last")

            # task-only → delete
            if video_fp and (do_task and not do_guidance):
                try: video_fp.unlink()
                except Exception: pass

            with pbar_lock: pbar.update(1)

        # s1/s2/s3
        for (s, tag_name) in [(1, "mirror1"), (2, "mirror2"), (3, s3_tag)]:
            e = by_sr.get((s, 0))
            if not e:
                continue
            if do_task:
                status_bar.set_description_str(f"[{instance_key}] s{s}_r0 → task({tag_name})")
                video_fp = render_one_json(
                    instance_key,
                    e,
                    guidance_dir=guidance_dir,
                    final_name=f"{e.path.stem}.mp4",
                )
                if video_fp:
                    out = task_dir / f"{instance_key}_{tag_name}.jpg"
                    extract_to(video_fp, out, "last")
                    try: video_fp.unlink()
                    except Exception: pass
                with pbar_lock: pbar.update(1)
            else:
                # guidance-only: easy 不需要这几个
                continue

        status_bar.set_description_str(f"[{instance_key}] done")
        return

    # -------------------------
    # HARD
    # -------------------------
    else:
        # guidance part
        if do_guidance:
            # s0_r0
            e00 = by_sr.get((0, 0))
            if e00:
                status_bar.set_description_str(f"[{instance_key}] s0_r0 → guidance_answer")
                video_fp = render_one_json(
                    instance_key,
                    e00,
                    guidance_dir=guidance_dir,
                    final_name=f"{instance_key}_guidance_answer.mp4",
                )
                if video_fp and do_task:
                    q_out = task_dir / f"{instance_key}_question.jpg"
                    a_out = task_dir / f"{instance_key}_answer.jpg"
                    extract_to(video_fp, q_out, "first")
                    extract_to(video_fp, a_out, "last")
                with pbar_lock: pbar.update(1)

            # s0_r1
            e01 = by_sr.get((0, 1))
            if e01:
                status_bar.set_description_str(f"[{instance_key}] s0_r1 → guidance_mirror1")
                render_one_json(
                    instance_key,
                    e01,
                    guidance_dir=guidance_dir,
                    final_name=f"{instance_key}_guidance_mirror1.mp4",
                )
                with pbar_lock: pbar.update(1)

            # s0_r2
            e02 = by_sr.get((0, 2))
            if e02:
                status_bar.set_description_str(f"[{instance_key}] s0_r2 → guidance_mirror2")
                render_one_json(
                    instance_key,
                    e02,
                    guidance_dir=guidance_dir,
                    final_name=f"{instance_key}_guidance_mirror2.mp4",
                )
                with pbar_lock: pbar.update(1)

            # s0_r3
            e03 = by_sr.get((0, 3))
            if e03:
                status_bar.set_description_str(f"[{instance_key}] s0_r3 → guidance_{s3_tag}")
                render_one_json(
                    instance_key,
                    e03,
                    guidance_dir=guidance_dir,
                    final_name=f"{instance_key}_guidance_{s3_tag}.mp4",
                )
                with pbar_lock: pbar.update(1)
        else:
            # no guidance but task may need s0_r0
            e00 = by_sr.get((0, 0))
            if e00 and do_task:
                status_bar.set_description_str(f"[{instance_key}] s0_r0 → task(q,a)")
                video_fp = render_one_json(
                    instance_key,
                    e00,
                    guidance_dir=guidance_dir,
                    final_name=f"{e00.path.stem}.mp4",
                )
                if video_fp:
                    q_out = task_dir / f"{instance_key}_question.jpg"
                    a_out = task_dir / f"{instance_key}_answer.jpg"
                    extract_to(video_fp, q_out, "first")
                    extract_to(video_fp, a_out, "last")
                    try: video_fp.unlink()
                    except Exception: pass
                with pbar_lock: pbar.update(1)

        # task-only parts (or task+guidance)
        if do_task:
            for (s, r, tag) in [
                (1, 1, "mirror1"),
                (2, 2, "mirror2"),
                (3, 3, s3_tag),
            ]:
                e = by_sr.get((s, r))
                if not e:
                    continue
                status_bar.set_description_str(f"[{instance_key}] s{s}_r{r} → task({tag})")
                video_fp = render_one_json(
                    instance_key,
                    e,
                    guidance_dir=guidance_dir,
                    final_name=f"{e.path.stem}.mp4",
                )
                if video_fp:
                    out = task_dir / f"{instance_key}_{tag}.jpg"
                    extract_to(video_fp, out, "last")
                    try: video_fp.unlink()
                    except Exception: pass
                with pbar_lock: pbar.update(1)

        status_bar.set_description_str(f"[{instance_key}] done")


# ============================================================
# 7. worker pool
# ============================================================

def run_instances_with_workers(
    batch_dir: Path,
    instances: List,  # List[Path] (legacy) or List[str] (flat inst_key)
    *,
    do_task: bool,
    do_guidance: bool,
    limit_easy: Optional[int],
    limit_hard: Optional[int],
    worker_count: int,
) -> None:
    shape_dir = batch_dir / "shape"
    if not shape_dir.is_dir():
        shape_dir = batch_dir
    all_entries = load_json_entries_from_root(shape_dir)
    grouped_entries: Dict[str, List[JsonEntry]] = {}
    for e in all_entries:
        key = f"mrt_{e.kind}{e.global_id:03d}"
        grouped_entries.setdefault(key, []).append(e)

    def _key(x) -> str:
        return x.name if isinstance(x, Path) else x

    filtered: List = []
    e_cnt = h_cnt = 0
    for d in instances:
        k = _key(d)
        if k.startswith("mrt_e"):
            if limit_easy is not None and e_cnt >= limit_easy:
                continue
            e_cnt += 1
        else:
            if limit_hard is not None and h_cnt >= limit_hard:
                continue
            h_cnt += 1
        filtered.append(d)

    total = 0
    for d in filtered:
        metas = grouped_entries.get(_key(d), [])
        is_easy = _key(d).startswith("mrt_e")
        by_sr = {(e.s, e.r): e for e in metas}
        _s3 = decide_s3_tag("e" if is_easy else "h", by_sr)
        if do_task and do_guidance:
            if is_easy:
                total += 1 + 3
            else:
                total += 4 + 3 + 0
        elif do_guidance:
            total += 1 if is_easy else 4
        else:
            total += 4
    desc = "task+guidance" if (do_task and do_guidance) else ("guidance" if do_guidance else "task")
    print(f"Start {desc}: {len(filtered)} instances, ~{total} items, workers={worker_count}")

    pbar = tqdm(total=total, desc=desc, unit="item", position=0)
    pbar_lock = Lock()
    idx_lock = Lock()
    cursor = {"i": 0}

    def worker_loop(wid: int):
        status = tqdm(total=0, bar_format="{desc}", position=wid + 1, leave=False)
        while True:
            with idx_lock:
                if cursor["i"] >= len(filtered):
                    break
                inst_dir = filtered[cursor["i"]]
                cursor["i"] += 1
            entries = grouped_entries.get(_key(inst_dir), [])
            process_instance(
                inst_dir,
                batch_dir,
                entries,
                do_task=do_task,
                do_guidance=do_guidance,
                pbar=pbar,
                pbar_lock=pbar_lock,
                status_bar=status,
            )
        status.set_description_str(f"[worker-{wid}] idle")

    threads: List[Thread] = []
    for wid in range(worker_count):
        t = Thread(target=worker_loop, args=(wid,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    pbar.close()


# ============================================================
# 8. main
# ============================================================

def main():
    parser = argparse.ArgumentParser("MCQ Task Composer (stable tqdm)")
    parser.add_argument("batch_dir", type=str)
    parser.add_argument("--mode", nargs="+", choices=["compose", "task", "guidance"], required=True)
    parser.add_argument("--limit-easy", type=int, default=None)
    parser.add_argument("--limit-hard", type=int, default=None)
    parser.add_argument("--worker", type=int, default=1)
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir)

    if "compose" in args.mode:
        compose(batch_dir)

    shape_dir = batch_dir / "shape"
    if shape_dir.is_dir():
        configs = list(shape_dir.glob("mrt_*.json"))
        all_instances = sorted(set(m.group(1) for p in configs for m in [re.match(r"^(mrt_[eh]\d{3})_", p.name)] if m))
    else:
        img_dir = batch_dir / "images"
        if img_dir.is_dir():
            all_instances = sorted(
                d for d in img_dir.iterdir()
                if d.is_dir() and re.match(r"^mrt_[eh]\d{3}$", d.name)
            )
        else:
            all_instances = sorted(
                d for d in batch_dir.iterdir()
                if d.is_dir() and re.match(r"^mrt_[eh]\d{3}$", d.name)
            )

    if "task" in args.mode and "guidance" in args.mode:
        run_instances_with_workers(
            batch_dir,
            all_instances,
            do_task=True,
            do_guidance=True,
            limit_easy=args.limit_easy,
            limit_hard=args.limit_hard,
            worker_count=args.worker,
        )
        return

    for m in args.mode:
        if m == "guidance":
            run_instances_with_workers(
                batch_dir,
                all_instances,
                do_task=False,
                do_guidance=True,
                limit_easy=args.limit_easy,
                limit_hard=args.limit_hard,
                worker_count=args.worker,
            )
        elif m == "task":
            run_instances_with_workers(
                batch_dir,
                all_instances,
                do_task=True,
                do_guidance=False,
                limit_easy=args.limit_easy,
                limit_hard=args.limit_hard,
                worker_count=args.worker,
            )


if __name__ == "__main__":
    main()
