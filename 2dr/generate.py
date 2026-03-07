#!/usr/bin/env python3
# 2DR pipeline: meta -> render -> assign. Run `python generate.py` or single steps (meta | render | assign).
# See README.md for methods and usage.
import argparse
import os
import sys
from pathlib import Path


def _ensure_path():
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


def _parse_grid_size(s: str):
    a, b = s.strip().replace("，", ",").split(",")[:2]
    return (int(a.strip()), int(b.strip()))


def run_meta(args):
    from src.meta_shape import generate_batch_to_directory
    batch_dir = generate_batch_to_directory(
        samples=args.samples,
        grid_size_range=args.grid_size_range,
        global_mode=args.mode,
        output_dir=args.output_dir,
    )
    print(f"\nBatch dir: {batch_dir}")
    return batch_dir


def run_render(batch_dir: str, args):
    from src.render import render_batch
    render_batch(
        batch_dir,
        modes=args.render_mode.split(",") if getattr(args, "render_mode", None) else ["task"],
        range_filter=getattr(args, "render_range", None),
        duration=getattr(args, "duration", None) or 3.0,
    )


def run_assign(batch_dir, args):
    from src.assign_json import generate_all_task_data
    batch_path = Path(batch_dir)
    output_file = getattr(args, "output", None) and Path(args.output) or (batch_path / "assign_data.jsonl")
    data_path = (getattr(args, "data_path", None) or "/root/autodl-fs/data/2dr-training").rstrip("/")
    category_mix = getattr(args, "assign_category", None) or "easy"
    generate_all_task_data(batch_path, output_file, data_path, category_mix=category_mix)


def run_pipeline(args):
    _ensure_path()
    print("========== 1/3 meta ==========")
    batch_dir = run_meta(args)
    print("\n========== 2/3 render ==========")
    run_render(batch_dir, args)
    print("\n========== 3/3 assign ==========")
    run_assign(batch_dir, args)
    print(f"\nDone. Batch: {batch_dir}")


def main():
    root = _ensure_path()
    parser = argparse.ArgumentParser(
        description="2DR: meta -> render -> assign",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See README.md for details.",
    )
    parser.add_argument("command", nargs="?", default="all", choices=["all", "meta", "render", "assign"], help="all | meta | render | assign")
    parser.add_argument("--samples", "-n", type=int, default=5, help="samples (meta/all)")
    parser.add_argument("--output-dir", "-O", type=str, default="medias", help="batch root (meta/all)")
    parser.add_argument("--grid-size", type=str, default="2,3", help="grid size range e.g. 2,3 (meta/all)")
    parser.add_argument("--mode", type=str, default="mixed", choices=["mixed", "color", "texture"], help="meta mode (meta/all)")
    parser.add_argument("--render-mode", type=str, default="task", help="render mode (render/all)")
    parser.add_argument("--render-range", "--range", "-r", type=str, default=None, help="range e.g. 5 or [1,5] (render/all)")
    parser.add_argument("--duration", "-D", type=float, default=None, help="video duration sec (render/all)")
    parser.add_argument("--data-path", "-d", type=str, default="data/2dr", help="JSONL path prefix (assign/all)")
    parser.add_argument("-o", "--output", type=str, default=None, help="assign output JSONL (assign/all)")
    parser.add_argument("--assign-category", type=str, default="easy", choices=["easy", "hard", "mixed"], help="task difficulty (assign/all)")
    parser.add_argument("batch_dir", nargs="?", type=str, help="batch dir (required for render/assign)")

    args = parser.parse_args()
    cmd = (args.command or "all").lower()

    # Parse grid_size
    try:
        args.grid_size_range = _parse_grid_size(args.grid_size)
    except Exception:
        args.grid_size_range = (2, 3)

    if cmd == "all":
        run_pipeline(args)
        return

    if cmd == "meta":
        run_meta(args)
        return

    if cmd == "render":
        batch_dir = args.batch_dir
        if not batch_dir:
            print("Provide batch_dir, e.g. python generate.py render medias/batch_xxx")
            sys.exit(1)
        if not os.path.isdir(batch_dir):
            print(f"Not a directory: {batch_dir}")
            sys.exit(1)
        run_render(batch_dir, args)
        return

    if cmd == "assign":
        batch_dir = args.batch_dir
        if not batch_dir:
            print("Provide batch_dir, e.g. python generate.py assign medias/batch_xxx")
            sys.exit(1)
        if not os.path.isdir(batch_dir):
            print(f"Not a directory: {batch_dir}")
            sys.exit(1)
        run_assign(batch_dir, args)
        return


if __name__ == "__main__":
    main()
