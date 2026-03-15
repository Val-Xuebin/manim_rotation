#!/usr/bin/env python3
"""
3dr pipeline entry: meta -> compose -> task+guidance -> assign.

Usage:
  python generate.py                         # full pipeline (same as 'all')
  python generate.py all [--batch-dir DIR] [--limit-easy N] [--limit-hard N]
  python generate.py meta [--batch-dir DIR]  # save batch to DIR (default: medias/batch_<timestamp>)
  python generate.py compose <batch_dir>
  python generate.py task <batch_dir> [--worker N]
  python generate.py assign <batch_dir> [-o out.jsonl]
"""
import argparse
import os
import sys
from pathlib import Path


def _root():
    return Path(__file__).resolve().parent


def _ensure_path():
    root = _root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run_meta(args):
    _ensure_path()
    from src.MRT_generator import create_mrt_configs, EASY_INSTANCE_NUM, HARD_INSTANCE_NUM
    chiral_path = _root() / "chiral_voxels_variants.json"
    if not chiral_path.exists():
        print("chiral_voxels_variants.json not found at", chiral_path)
        sys.exit(1)
    output_dir = getattr(args, "batch_output", None) or getattr(args, "output_dir", None)
    batch_dir, config_files = create_mrt_configs(
        str(chiral_path),
        easy_instances_per_group=getattr(args, "easy", None) or EASY_INSTANCE_NUM,
        hard_instances_per_group=getattr(args, "hard", None) or HARD_INSTANCE_NUM,
        output_dir=output_dir,
    )
    print("Batch dir:", batch_dir)
    return batch_dir


def run_compose(batch_dir: str):
    _ensure_path()
    from task_compose.mcq_task_compose import compose
    compose(Path(batch_dir))
    print("Compose done.")


def run_task(batch_dir: str, args):
    _ensure_path()
    import re
    from task_compose.mcq_task_compose import run_instances_with_workers
    batch_path = Path(batch_dir)
    instances = []
    shape_dir = batch_path / "shape"
    if shape_dir.is_dir():
        configs = list(shape_dir.glob("mrt_*.json"))
        instances = sorted(set(m.group(1) for p in configs for m in [re.match(r"^(mrt_[eh]\d{3})_", p.name)] if m))
    if not instances:
        img_dir = batch_path / "images"
        if img_dir.is_dir():
            instances = sorted(
                d for d in img_dir.iterdir()
                if d.is_dir() and re.match(r"^mrt_[eh]\d{3}$", d.name)
            )
        else:
            instances = sorted(
                d for d in batch_path.iterdir()
                if d.is_dir() and re.match(r"^mrt_[eh]\d{3}$", d.name)
            )
    if not instances:
        print("No instances (mrt_e001, mrt_h001, ...) in", batch_dir)
        return
    run_instances_with_workers(
        batch_path,
        instances,
        do_task=True,
        do_guidance=True,
        limit_easy=getattr(args, "limit_easy", None),
        limit_hard=getattr(args, "limit_hard", None),
        worker_count=getattr(args, "worker", 1),
    )
    print("Task + guidance done.")


def run_assign(batch_dir: str, args):
    _ensure_path()
    from task_compose.assign_template import generate_all_task_data
    batch_path = Path(batch_dir)
    out = getattr(args, "output", None)
    output_file = Path(out) if out else batch_path / "assign_data.jsonl"
    generate_all_task_data(batch_path, output_file, getattr(args, "limit_easy", None), getattr(args, "limit_hard", None))
    print("Assign done:", output_file)


def run_pipeline(args):
    _ensure_path()
    print("========== 1/4 meta ==========")
    batch_dir = run_meta(args)
    print("\n========== 2/4 compose ==========")
    run_compose(batch_dir)
    print("\n========== 3/4 task + guidance ==========")
    run_task(batch_dir, args)
    print("\n========== 4/4 assign ==========")
    run_assign(batch_dir, args)
    print("\nDone. Batch:", batch_dir)


def main():
    root = _ensure_path()
    parser = argparse.ArgumentParser(description="3dr: one-shot meta->compose->task->assign or single step")
    parser.add_argument("command", nargs="?", default="all", choices=["all", "meta", "compose", "task", "assign"])
    parser.add_argument("batch_dir", nargs="?", type=str, help="Batch dir (required for compose / task / assign)")
    parser.add_argument("--batch-dir", "--output-dir", dest="batch_output", type=str, default=None,
                        help="Save batch to this directory (meta/all). Default: medias/batch_<timestamp>")
    parser.add_argument("--easy", type=int, default=None, help="Easy instances per group (meta)")
    parser.add_argument("--hard", type=int, default=None, help="Hard instances per group (meta)")
    parser.add_argument("--limit-easy", type=int, default=None)
    parser.add_argument("--limit-hard", type=int, default=None)
    parser.add_argument("--worker", "-w", type=int, default=1, help="Parallel workers (subprocess mode defaults to min(4,cpu_count) if 1)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Assign output JSONL path")
    args = parser.parse_args()

    cmd = (args.command or "all").lower()

    if cmd == "all":
        run_pipeline(args)
        return

    # meta: single step when you only want to create a new batch (no batch_dir)
    if cmd == "meta":
        run_meta(args)
        return

    if cmd in ("compose", "task", "assign"):
        batch_dir = args.batch_dir
        if not batch_dir:
            print("Provide batch_dir, e.g.: python generate.py", cmd, "medias/batch_xxx")
            sys.exit(1)
        if not Path(batch_dir).is_dir():
            print("Not a directory:", batch_dir)
            sys.exit(1)
        if cmd == "compose":
            run_compose(batch_dir)
        elif cmd == "task":
            run_task(batch_dir, args)
        else:
            run_assign(batch_dir, args)
        return

    print("Unknown command:", cmd)
    sys.exit(1)


if __name__ == "__main__":
    main()
