#!/usr/bin/env python3
# Render: Manim scene for grid rotation; batch reads batch_dir/shape/*.json, writes img/ + video/. See README.md.

import os
import sys
import json
import time
import math
import glob
import shutil
import argparse
import subprocess
import logging
import io
import contextlib
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
from tqdm import tqdm

from manim import (
    Scene, VGroup, Square, Rectangle, Circle, RegularPolygon, Star,
    BLUE, RED, GREEN, ORANGE, PINK, PURPLE, GRAY, WHITE, BLACK, YELLOW,
    FadeIn, FadeOut, Write, Create, Transform, Rotate,
    rate_functions, config
)

# --- Helpers ---

COLOR_MAP = {
    "BLUE": BLUE,
    "RED": RED,
    "GREEN": GREEN,
    "ORANGE": ORANGE,
    "PINK": PINK,
    "PURPLE": PURPLE,
    "GRAY": GRAY,
    "WHITE": WHITE,
    "BLACK": BLACK,
    "YELLOW": YELLOW,
}

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def grid_mobject_from_json(obj_cfg: Dict[str, Any], visual_cfg: Optional[Dict[str, Any]] = None, 
                            type_cfg: Optional[str] = None, rows_cfg: Optional[int] = None, 
                            cols_cfg: Optional[int] = None, mode_cfg: Optional[str] = None) -> VGroup:
    """Build grid VGroup from variant (cells or legacy pattern/cell_colors). Top-level type, rows, cols, mode, visual passed in."""
    rows = rows_cfg if rows_cfg is not None else int(obj_cfg.get("rows", 1))
    cols = cols_cfg if cols_cfg is not None else int(obj_cfg.get("cols", 1))
    
    # cell_size, show_grid from visual or obj_cfg
    if visual_cfg:
        cell_size = float(visual_cfg.get("cell_size", 1.0))
        show_grid = bool(visual_cfg.get("show_grid", True))
    else:
        cell_size = float(obj_cfg.get("cell_size", 1.0))
        show_grid = bool(obj_cfg.get("show_grid", True))
    
    pattern = obj_cfg.get("pattern")
    
    cell_colors = obj_cfg.get("cell_colors", obj_cfg.get("cell_styles", []))
    if visual_cfg:
        uniform_fill_opacity = visual_cfg.get("fill_opacity", 0.8)
        uniform_stroke_width = visual_cfg.get("stroke_width", 2.0)
        uniform_stroke_color = visual_cfg.get("stroke_color", "WHITE")
        uniform_texture_opacity = visual_cfg.get("texture_opacity", 1.0)
        uniform_texture_color = visual_cfg.get("texture_color", "BLACK")
    else:
        uniform_fill_opacity = obj_cfg.get("fill_opacity", 0.8)
        uniform_stroke_width = obj_cfg.get("stroke_width", 2.0)
        uniform_stroke_color = obj_cfg.get("stroke_color", "WHITE")
        uniform_texture_opacity = obj_cfg.get("texture_opacity", 1.0)
        uniform_texture_color = obj_cfg.get("texture_color", "BLACK")

    cells = obj_cfg.get("cells")
    total_w = cols * cell_size
    total_h = rows * cell_size
    origin_x = - total_w / 2 + cell_size / 2
    origin_y = + total_h / 2 - cell_size / 2

    group = VGroup()
    
    if cells:
        for cell_data in cells:
            r, c = cell_data["pos"]
            x = origin_x + c * cell_size
            y = origin_y - r * cell_size
            cell = Square(side_length=cell_size)
            style = cell_data
            fill_color_name = style.get("color", "BLUE")
            fill_color = COLOR_MAP.get(fill_color_name, BLUE)
            fill_opacity = float(uniform_fill_opacity)

            # stroke
            if show_grid:
                stroke_color_name = uniform_stroke_color
                stroke_color = COLOR_MAP.get(stroke_color_name, WHITE)
                stroke_width = float(uniform_stroke_width)
                cell.set_stroke(stroke_color, width=stroke_width)
            else:
                cell.set_stroke(None, width=0)

            cell.set_fill(fill_color, opacity=fill_opacity)
            if mode_cfg == "texture":
                texture_color_name = uniform_texture_color
                texture_color_actual = COLOR_MAP.get(texture_color_name, fill_color)
                texture_opacity = float(uniform_texture_opacity)
                
                texture_type = style.get("texture_type")
                if texture_type == "line":
                    direction = style.get("line_direction")
                    dirs = {
                        "vertical": ([0, cell_size/2, 0], [0, -cell_size/2, 0]),
                        "horizontal": ([-cell_size/2, 0, 0], [cell_size/2, 0, 0]),
                        "left_slash": ([cell_size/2, cell_size/2, 0], [-cell_size/2, -cell_size/2, 0]),
                        "right_slash": ([-cell_size/2, cell_size/2, 0], [cell_size/2, -cell_size/2, 0])
                    }
                    if direction in dirs:
                        from manim import Line
                        line = Line(dirs[direction][0], dirs[direction][1], stroke_width=2)
                        line.set_color(texture_color_actual)
                        line.set_opacity(texture_opacity)
                        cell.add(line)
                
                elif texture_type == "polygon":
                    shape = style.get("polygon_shape")
                    if shape == "triangle":
                        poly = RegularPolygon(3)
                    elif shape == "square":
                        poly = Square()
                    elif shape == "circle":
                        poly = Circle()
                    elif shape == "diamond":
                        poly = RegularPolygon(4)
                        poly.rotate(45 * 3.14159 / 180)
                    else:
                        poly = None
                    
                    if poly:
                        max_dim = cell_size * 0.6
                        if shape == "square":
                            poly.scale_to_fit_width(max_dim)
                        elif shape == "circle":
                            poly.scale_to_fit_width(max_dim)
                        elif shape == "diamond":
                            poly.scale_to_fit_height(max_dim)
                        else:
                            poly.scale_to_fit_height(max_dim)
                        poly.shift(-poly.get_center())
                        poly.move_to([0, 0, 0])
                        
                        poly.set_color(texture_color_actual)
                        poly.set_opacity(texture_opacity)
                        cell.add(poly)
            
            cell.move_to([x, y, 0])
            group.add(cell)
        
        return group
    
    # Legacy: pattern + cell_colors
    pattern = obj_cfg.get("pattern")
    if pattern is None:
        pattern = [[1 for _ in range(cols)] for _ in range(rows)]
    
    style_idx = 0
    for r in range(rows):
        for c in range(cols):
            if int(pattern[r][c]) != 1:
                continue
            
            x = origin_x + c * cell_size
            y = origin_y - r * cell_size
            cell = Square(side_length=cell_size)
            style = cell_colors[style_idx] if style_idx < len(cell_colors) else (cell_colors[-1] if cell_colors else {})
            style_idx += 1

            fill_color_name = style.get("color", "BLUE")
            fill_color = COLOR_MAP.get(fill_color_name, BLUE)
            fill_opacity = float(uniform_fill_opacity)

            # stroke
            if show_grid:
                stroke_color_name = uniform_stroke_color
                stroke_color = COLOR_MAP.get(stroke_color_name, WHITE)
                stroke_width = float(uniform_stroke_width)
                cell.set_stroke(stroke_color, width=stroke_width)
            else:
                cell.set_stroke(None, width=0)

            cell.set_fill(fill_color, opacity=fill_opacity)
            is_texture = mode_cfg == "texture" if mode_cfg else style.get("style_type") == "texture" if mode_cfg else style.get("style_type") == "texture"
            if is_texture:
                texture_color_name = uniform_texture_color
                texture_color_actual = COLOR_MAP.get(texture_color_name, fill_color)
                texture_opacity = float(uniform_texture_opacity)
                
                texture_type = style.get("texture_type")
                if texture_type == "line":
                    direction = style.get("line_direction")
                    dirs = {
                        "vertical": ([0, cell_size/2, 0], [0, -cell_size/2, 0]),
                        "horizontal": ([-cell_size/2, 0, 0], [cell_size/2, 0, 0]),
                        "left_slash": ([cell_size/2, cell_size/2, 0], [-cell_size/2, -cell_size/2, 0]),
                        "right_slash": ([-cell_size/2, cell_size/2, 0], [cell_size/2, -cell_size/2, 0])
                    }
                    if direction in dirs:
                        from manim import Line
                        line = Line(dirs[direction][0], dirs[direction][1], stroke_width=2)
                        line.set_color(texture_color_actual)
                        line.set_opacity(texture_opacity)
                        cell.add(line)
                
                elif texture_type == "polygon":
                    shape = style.get("polygon_shape")
                    if shape == "triangle":
                        poly = RegularPolygon(3)
                    elif shape == "square":
                        poly = Square()
                    elif shape == "circle":
                        poly = Circle()
                    elif shape == "diamond":
                        poly = RegularPolygon(4)
                        poly.rotate(45 * 3.14159 / 180)
                    else:
                        poly = None
                    
                    if poly:
                        max_dim = cell_size * 0.6
                        if shape == "square":
                            poly.scale_to_fit_width(max_dim)
                        elif shape == "circle":
                            poly.scale_to_fit_width(max_dim)
                        elif shape == "diamond":
                            poly.scale_to_fit_height(max_dim)
                        else:
                            poly.scale_to_fit_height(max_dim)
                        poly.shift(-poly.get_center())
                        poly.move_to([0, 0, 0])
                        
                        poly.set_color(texture_color_actual)
                        poly.set_opacity(texture_opacity)
                        cell.add(poly)
            
            cell.move_to([x, y, 0])
            group.add(cell)
    
    if len(group) == 0:
        cell = Square(side_length=cell_size).set_opacity(0.0)
        group.add(cell)

    return group


def compute_output_paths(json_path: str, idx: int, want_first: bool, want_last: bool, want_video: bool):
    """Output paths: stem_first.jpg, stem_last.jpg, stem.mp4."""
    base_dir = os.path.dirname(json_path)
    stem = f"2dr_{idx:04d}"
    out_dir = base_dir
    ensure_dir(out_dir)

    first_path = os.path.join(out_dir, f"{stem}_first.jpg") if want_first else None
    last_path  = os.path.join(out_dir, f"{stem}_last.jpg")  if want_last  else None
    video_path = os.path.join(out_dir, f"{stem}.mp4")       if want_video else None
    return out_dir, first_path, last_path, video_path


# --- Scene ---

class GridRotationScene(Scene):
    """Background from video config; linear rotation (no extra wait). Modes: first | last | video."""

    def construct(self):
        json_path = os.environ.get("JSON_PATH")
        mode = os.environ.get("RENDER_MODE", "video")
        if not json_path:
            return
        cfg = load_json(json_path)
        rot_cfg = cfg.get("rotation", {})
        vid_cfg = cfg.get("video", {})
        visual_cfg = cfg.get("visual", {})
        type_cfg = cfg.get("type")
        rows_cfg = cfg.get("rows")
        cols_cfg = cfg.get("cols")
        mode_cfg = cfg.get("mode")
        obj_cfg = cfg.get("object", {})
        duration = float(rot_cfg.get("duration", os.environ.get("RENDER_DURATION", "3.0")))
        bg = vid_cfg.get("background_color", "#1a1a2e")
        self.camera.background_color = bg
        grid = grid_mobject_from_json(obj_cfg, visual_cfg, type_cfg, rows_cfg, cols_cfg, mode_cfg)
        self.add(grid)
        angle_deg = float(rot_cfg.get("rotation_angle", 90.0))
        clockwise = bool(rot_cfg.get("clockwise", True))
        angle_rad = math.radians(angle_deg) * (-1.0 if clockwise else 1.0)
        if mode == "first":
            self.wait(0.01)
            return
        if mode == "last":
            grid.rotate(angle_rad)
            self.wait(0.01)
            return
        if mode == "video":
            self.play(
                Rotate(grid, angle=angle_rad),
                run_time=duration,
                rate_func=rate_functions.linear
            )
            return


# --- Batch render ---

def extract_frame_from_video(video_path: str, frame_path: str, frame_number: int):
    """Extract frame: 0 = first, -1 = last."""
    if frame_number == -1:
        probe_cmd = f"ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 '{video_path}'"
        result = subprocess.run(probe_cmd, shell=True, capture_output=True, timeout=10, text=True)
        if result.returncode == 0:
            total_frames = int(result.stdout.strip())
            cmd = f"ffmpeg -i '{video_path}' -vf \"select='eq(n,{total_frames-1})'\" -frames:v 1 -y '{frame_path}'"
        else:
            cmd = f"ffmpeg -sseof -0.001 -i '{video_path}' -frames:v 1 -y '{frame_path}'"
    else:
        cmd = f"ffmpeg -i '{video_path}' -frames:v 1 -y '{frame_path}'"
    result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10, text=True)
    if result.returncode != 0:
        print(f"Frame extract failed: {result.stderr}")


def render_one_variant(variant_obj: Dict[str, Any], img_dir: str, video_dir: str, stem: str, variant_idx: int, modes: List[str], duration: float, json_cfg: Dict[str, Any]):
    """Render one variant to img_dir / video_dir via temp JSON + Manim subprocess."""
    temp_json = os.path.join(img_dir, f"temp_variant_{stem}_{variant_idx}.json")
    variant_cfg = {
        "object": variant_obj, 
        "type": json_cfg.get("type"),
        "rows": json_cfg.get("rows"),
        "cols": json_cfg.get("cols"),
        "mode": json_cfg.get("mode"),
        "visual": json_cfg.get("visual", {}),
        "rotation": json_cfg.get("rotation", {}), 
        "video": json_cfg.get("video", {})
    }
    with open(temp_json, "w") as f:
        json.dump(variant_cfg, f)
    temp_media_dir = os.path.join(img_dir, f"temp_render_{stem}_{variant_idx}")
    ensure_dir(temp_media_dir)
    
    os.environ["JSON_PATH"] = temp_json
    os.environ["RENDER_MODE"] = "video"
    os.environ["RENDER_DURATION"] = str(duration)
    config.media_dir = temp_media_dir
    config.output_file = f"{stem}_{variant_idx}"
    config.pixel_width = 1280
    config.pixel_height = 720
    config.frame_rate = 30
    logging.getLogger("manim").setLevel(logging.ERROR)
    logging.getLogger().setLevel(logging.ERROR)
    
    f = io.StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        scene = GridRotationScene()
        scene.render()
    
    video_cands = sorted(glob.glob(os.path.join(temp_media_dir, "**", "*.mp4"), recursive=True), key=os.path.getmtime)
    if not video_cands:
        shutil.rmtree(temp_media_dir, ignore_errors=True)
        os.remove(temp_json)
        return
    final_video = video_cands[-1]
    if "video" in modes:
        target_video = os.path.join(video_dir, f"{stem}_{variant_idx}.mp4")
        ensure_dir(video_dir)
        shutil.copy2(final_video, target_video)
    if "first" in modes or "last" in modes:
        for frame_mode in ["first", "last"]:
            if frame_mode not in modes:
                continue
            frame_num = 0 if frame_mode == "first" else -1
            target_frame = os.path.join(img_dir, f"{stem}_{variant_idx}_{frame_mode}.jpg")
            extract_frame_from_video(final_video, target_frame, frame_num)
    if "video" not in modes:
        os.remove(final_video)
    shutil.rmtree(temp_media_dir, ignore_errors=True)
    os.remove(temp_json)


def render_one(json_path: str, modes: List[str], idx: int, duration: float = 3.0, img_dir: str = None, video_dir: str = None):
    """Render one JSON and all variants; output to img_dir, video_dir."""
    base_dir = os.path.dirname(json_path)
    if img_dir is None:
        img_dir = base_dir
    if video_dir is None:
        video_dir = base_dir
    ensure_dir(img_dir)
    ensure_dir(video_dir)
    stem = f"2dr_{idx:04d}"
    
    cfg = load_json(json_path)
    rot_cfg = cfg.get("rotation", {})
    duration = float(rot_cfg.get("duration", duration))
    variants = cfg.get("variants", {})
    if not variants:
        return
    if "task" in modes:
        if "s0" in variants:
            render_one_variant(variants["s0"], img_dir, video_dir, stem, 0, ["first", "last", "video"], duration, cfg)
        for i in range(1, 5):
            variant_key = f"s{i}"
            if variant_key in variants:
                render_one_variant(variants[variant_key], img_dir, video_dir, stem, i, ["last"], duration, cfg)
        return
    for variant_key in sorted(variants.keys()):
        if variant_key == "s5":
            continue
        variant_obj = variants[variant_key]
        variant_idx = int(variant_key[1])
        render_one_variant(variant_obj, img_dir, video_dir, stem, variant_idx, modes, duration, cfg)


def parse_range(range_str: str):
    """Parse --range: N | A:B | [A,B]. Returns (kind, value) for filtering."""
    if not range_str:
        return None
    s = str(range_str).strip()
    try:
        if s.startswith('[') and s.endswith(']'):
            parts = s.strip('[]').split(',')
            start, end = int(parts[0].strip()), int(parts[1].strip())
            return ("pred", lambda i, a=start, b=end: (i >= a and i <= b))
        if ':' in s:
            left, right = s.split(':', 1)
            left = left.strip()
            right = right.strip()
            start = int(left) if left else None
            end = int(right) if right else None
            return ("pred", lambda i, a=start, b=end: (a is None or i >= a) and (b is None or i <= b))
        n = int(s)
        return ("first_n", n)
    except Exception:
        return None


def render_batch(batch_dir: str, modes: List[str], range_filter: str = None, duration: float = 3.0):
    """Render all 2dr_*.json under batch_dir/shape/; output to batch_dir/img/, batch_dir/video/."""
    shape_dir = os.path.join(batch_dir, "shape")
    img_dir = os.path.join(batch_dir, "img")
    video_dir = os.path.join(batch_dir, "video")
    if not os.path.isdir(shape_dir):
        print(f"[WARN] shape dir not found: {shape_dir}")
        return
    ensure_dir(img_dir)
    ensure_dir(video_dir)
    json_files = []
    for name in sorted(os.listdir(shape_dir)):
        if name.startswith("2dr_") and name.endswith(".json"):
            json_file = os.path.join(shape_dir, name)
            if os.path.isfile(json_file):
                file_idx = int(name.replace("2dr_", "").replace(".json", ""))
                json_files.append((file_idx, json_file))
    if not json_files:
        print(f"[WARN] No 2dr_*.json in {shape_dir}")
        return
    rf = parse_range(range_filter)
    if rf:
        kind, val = rf
        if kind == "first_n":
            json_files = json_files[:max(0, int(val))]
        elif kind == "pred":
            pred = val
            json_files = [(idx, jp) for idx, jp in json_files if pred(idx)]
    if not json_files:
        print("[WARN] No files after range filter")
        return
    total = len(json_files)
    with tqdm(total=total, desc="Render", unit="") as pbar:
        for file_idx, jp in json_files:
            name = os.path.basename(jp)
            pbar.set_postfix_str(name)
            render_one(jp, modes=modes, idx=file_idx, duration=duration, img_dir=img_dir, video_dir=video_dir)
            pbar.update(1)


# -----------------------------
# CLI
# -----------------------------

def main():
    parser = argparse.ArgumentParser(description="2D Grid Manim Renderer (linear rotation, no waits).")
    parser.add_argument("target", nargs='?', type=str, help="batch dir (positional)")
    parser.add_argument("--input", type=str, default=None, help="single JSON path")
    parser.add_argument("--batch_dir", type=str, default=None, help="batch dir")
    parser.add_argument("--mode", type=str, required=True, help="first,last,video,task (comma-sep)")
    parser.add_argument("--range", type=str, default=None, help="e.g. 5 or [1,5]")
    parser.add_argument("--duration", type=float, default=None, help="video duration (sec)")
    args = parser.parse_args()
    batch_dir = args.target or args.batch_dir
    if not args.input and not batch_dir:
        print("Provide --input or batch dir.")
        sys.exit(1)
    modes = [m.strip() for m in args.mode.split(",")]
    valid_modes = ["first", "last", "video", "task"]
    for m in modes:
        if m not in valid_modes:
            print(f"Invalid mode '{m}'; must be in {valid_modes}")
            sys.exit(1)

    duration = args.duration if args.duration is not None else 3.0

    if args.input:
        render_one(args.input, modes=modes, idx=1, duration=duration)
    if batch_dir:
        render_batch(batch_dir, modes=modes, range_filter=args.range, duration=duration)


if __name__ == "__main__":
    main()