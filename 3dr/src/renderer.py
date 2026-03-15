#!/usr/bin/env python3
"""
Renderer helpers for 3dr: render MRT config to video, locate Manim output, extract first/last frame.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Union


def render_video(config_path: Path, config_data: dict = None, save_meta: bool = True) -> Path:
    """Render one MRT config to video via cube_stack_animation. Config may be path or in-memory dict."""
    import sys
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from src.cube_stack_animation import create_video_from_config

    if config_data is not None:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
            temp_config_path = f.name
        result_path = create_video_from_config(temp_config_path, save_meta=save_meta)
        os.unlink(temp_config_path)
    else:
        result_path = create_video_from_config(str(config_path), save_meta=save_meta)
    return Path(result_path)


def find_actual_video_path(expected_path: Path, video_dir: str) -> Path:
    """Resolve actual video path; Manim may write to subdirs (e.g. videos/720p30/)."""
    if expected_path.exists():
        return expected_path
    possible_paths = [
        expected_path,
        Path(video_dir) / "videos" / "720p30" / expected_path.name,
        Path(video_dir) / "videos" / "1080p60" / expected_path.name,
        Path(video_dir) / "videos" / "480p15" / expected_path.name,
        Path(video_dir) / "videos" / "360p30" / expected_path.name,
        Path(video_dir) / expected_path.name,
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def extract_frame(video_path: Path, out_path: Path, select: str) -> bool:
    """Extract first or last frame from video using ffmpeg. select: 'first' or 'last'."""
    try:
        if select == "first":
            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-frames:v", "1",
                str(out_path)
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-sseof", "-0.04", "-i", str(video_path),
                "-frames:v", "1",
                str(out_path)
            ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def render_folder(
    folder: Path,
    modes: List[str],
    limit: int = None,
    *,
    image_output_dir: Optional[Union[str, Path]] = None,
    skip_default_images: bool = False,
) -> None:
    """Render all JSON configs in folder: video and/or first/last frame extraction."""
    folder = Path(folder)
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")
    json_files = sorted(folder.glob("*.json"))
    if limit is not None:
        json_files = json_files[:max(0, int(limit))]
    print(f"Found {len(json_files)} configs")

    for idx, cfg in enumerate(json_files, 1):
        print(f"[{idx}/{len(json_files)}] {cfg.name}")
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            output_config = data.get("output", {})
            video_dir = output_config.get("video_dir", "videos")
            image_dir = output_config.get("image_dir", "images")
            filename = output_config.get("filename", "output")
        except Exception as e:
            print(f"  Config read failed: {e}")
            continue
        Path(video_dir).mkdir(parents=True, exist_ok=True)
        Path(image_dir).mkdir(parents=True, exist_ok=True)
        video_path = None
        if "video" in modes:
            try:
                video_path = render_video(cfg, data)
                print(f"  Video: {video_path}")
            except Exception as e:
                print(f"  Render failed: {e}")
        if ("first" in modes or "last" in modes) and video_path is None:
            try:
                import tempfile
                import copy
                import shutil as _shutil
                temp_root = Path(tempfile.mkdtemp(prefix="render_tmp_"))
                temp_images = temp_root / "images"
                temp_meta = temp_root / "meta"
                temp_videos = temp_root / "videos"
                temp_images.mkdir(parents=True, exist_ok=True)
                temp_meta.mkdir(parents=True, exist_ok=True)
                temp_videos.mkdir(parents=True, exist_ok=True)

                data_for_video = copy.deepcopy(data)
                data_for_video.setdefault("output", {})
                # 覆盖所有输出目录，避免在批次目录下生成任何文件
                data_for_video["output"]["image_dir"] = str(temp_images)
                data_for_video["output"]["meta_dir"] = str(temp_meta)
                data_for_video["output"]["video_dir"] = str(temp_videos)
                video_path = render_video(cfg, data_for_video, save_meta=False)
                print(f"  Video (for frames): {video_path}")
                try:
                    _shutil.rmtree(temp_root, ignore_errors=True)
                except Exception:
                    pass
            except Exception as e:
                print(f"  Render failed (for frames): {e}")

        if video_path and video_path.exists():
            base = video_path.stem
            override_dir = Path(image_output_dir) if image_output_dir is not None else None
            target_dir_default = Path(image_dir)
            targets = []
            if "first" in modes:
                targets.append(("first", f"{base}_first.jpg"))
            if "last" in modes:
                targets.append(("last", f"{base}_last.jpg"))
            for select, fname in targets:
                wrote = False
                if override_dir is not None:
                    override_dir.mkdir(parents=True, exist_ok=True)
                    out_path = override_dir / fname
                    if extract_frame(video_path, out_path, select):
                        print(f"  {select} frame (override): {out_path}")
                        wrote = True
                    else:
                        print(f"  {select} frame extract failed (override)")
                if (not skip_default_images) and (not wrote or image_output_dir is None):
                    target_dir_default.mkdir(parents=True, exist_ok=True)
                    out_path_def = target_dir_default / fname
                    if extract_frame(video_path, out_path_def, select):
                        print(f"  {select} frame: {out_path_def}")
                    else:
                        print(f"  {select} frame extract failed")
        else:
            if video_path:
                actual_video_path = find_actual_video_path(video_path, video_dir)
                if actual_video_path and actual_video_path.exists():
                    base = actual_video_path.stem
                    if "first" in modes:
                        out_first = Path(image_dir) / f"{base}_first.jpg"
                        if extract_frame(actual_video_path, out_first, "first"):
                            print(f"  First frame: {out_first}")
                        else:
                            print("  First frame extract failed")
                    if "last" in modes:
                        out_last = Path(image_dir) / f"{base}_last.jpg"
                        if extract_frame(actual_video_path, out_last, "last"):
                            print(f"  Last frame: {out_last}")
                        else:
                            print("  Last frame extract failed")
                else:
                    print("  Actual video file not found")


def main():
    import sys as _sys
    if len(_sys.argv) >= 3 and _sys.argv[1] == "render-one":
        # Single render from CLI for subprocess mode (avoids thread buildup in parent)
        config_path = Path(_sys.argv[2])
        result = render_video(config_path, config_data=None, save_meta=False)
        print(str(result))
        return
    parser = argparse.ArgumentParser(description="Render MRT JSON configs in a folder (video and/or first/last frames)")
    parser.add_argument("folder", type=str, help="Folder containing JSON configs")
    parser.add_argument("--modes", nargs="+", default=["video"], choices=["video", "first", "last"],
                        help="Modes: video, first, last (multiple allowed)")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N JSONs")
    args = parser.parse_args()
    render_folder(Path(args.folder), args.modes, args.limit)


if __name__ == "__main__":
    main()

