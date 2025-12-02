#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_2d_grid.py
- 从单个 JSON (--input) 或批量目录 (--batch_dir) 读取配置
- 使用 Manim 渲染：线性速度连续旋转（无多余 wait）
- 渲染模式：--mode first / last / video
- 输出命名：
  batch_datetime/2dr_001/2dr_001_first.jpg
  batch_datetime/2dr_001/2dr_001_last.jpg
  batch_datetime/2dr_001/2dr_001.mp4
"""

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

# -----------------------------
# 实用函数
# -----------------------------

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
    """
    根据 JSON 的 object 配置构造网格 VGroup。
    支持：
      - variant中只有cell_colors, pattern, description
      - 其他字段从顶层读取：type, rows, cols, mode, visual (cell_size, show_grid等)
    
    Args:
        obj_cfg: variant的配置（只包含cell_colors, pattern, description）
        visual_cfg: 顶层的visual配置（统一视觉参数）
        type_cfg: 顶层的type
        rows_cfg: 顶层的rows
        cols_cfg: 顶层的cols
        mode_cfg: 顶层的mode
    """
    rows = rows_cfg if rows_cfg is not None else int(obj_cfg.get("rows", 1))
    cols = cols_cfg if cols_cfg is not None else int(obj_cfg.get("cols", 1))
    
    # 从visual读取cell_size和show_grid
    if visual_cfg:
        cell_size = float(visual_cfg.get("cell_size", 1.0))
        show_grid = bool(visual_cfg.get("show_grid", True))
    else:
        cell_size = float(obj_cfg.get("cell_size", 1.0))
        show_grid = bool(obj_cfg.get("show_grid", True))
    
    pattern = obj_cfg.get("pattern")
    
    # 新结构：使用cell_colors，统一字段在顶层的visual参数中
    cell_colors = obj_cfg.get("cell_colors", obj_cfg.get("cell_styles", []))  # 兼容新旧格式
    
    # 从visual_cfg读取统一字段（如果有），否则从obj_cfg读取（兼容旧格式）
    if visual_cfg:
        uniform_fill_opacity = visual_cfg.get("fill_opacity", 0.8)
        uniform_stroke_width = visual_cfg.get("stroke_width", 2.0)
        uniform_stroke_color = visual_cfg.get("stroke_color", "WHITE")
        uniform_texture_opacity = visual_cfg.get("texture_opacity", 1.0)
        uniform_texture_color = visual_cfg.get("texture_color", "BLACK")
    else:
        # 兼容旧格式：从obj_cfg直接读取
        uniform_fill_opacity = obj_cfg.get("fill_opacity", 0.8)
        uniform_stroke_width = obj_cfg.get("stroke_width", 2.0)
        uniform_stroke_color = obj_cfg.get("stroke_color", "WHITE")
        uniform_texture_opacity = obj_cfg.get("texture_opacity", 1.0)
        uniform_texture_color = obj_cfg.get("texture_color", "BLACK")

    # 新结构：读取cells，或者兼容旧pattern格式
    cells = obj_cfg.get("cells")
    
    # 居中：计算左上角 cell 中心点位置
    total_w = cols * cell_size
    total_h = rows * cell_size
    origin_x = - total_w / 2 + cell_size / 2
    origin_y = + total_h / 2 - cell_size / 2

    group = VGroup()
    
    if cells:
        # 新格式：使用cells
        for cell_data in cells:
            r, c = cell_data["pos"]
            
            # 位置
            x = origin_x + c * cell_size
            y = origin_y - r * cell_size
            
            # cell
            cell = Square(side_length=cell_size)
            style = cell_data  # style信息在cell_data中
            
            # 颜色与透明度（使用统一字段）
            fill_color_name = style.get("color", "BLUE")
            fill_color = COLOR_MAP.get(fill_color_name, BLUE)
            fill_opacity = float(uniform_fill_opacity)

            # 描边（使用统一字段）
            if show_grid:
                stroke_color_name = uniform_stroke_color
                stroke_color = COLOR_MAP.get(stroke_color_name, WHITE)
                stroke_width = float(uniform_stroke_width)
                cell.set_stroke(stroke_color, width=stroke_width)
            else:
                cell.set_stroke(None, width=0)

            # 填充
            cell.set_fill(fill_color, opacity=fill_opacity)
            
            # texture处理（根据顶层mode判断）
            if mode_cfg == "texture":
                # 使用统一的texture_color
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
                        poly.rotate(45 * 3.14159 / 180)  # 旋转45度得到菱形
                    else:
                        poly = None
                    
                    if poly:
                        # 调整大小，使其填充cell的一部分
                        max_dim = cell_size * 0.6
                        if shape == "square":
                            poly.scale_to_fit_width(max_dim)
                        elif shape == "circle":
                            poly.scale_to_fit_width(max_dim)
                        elif shape == "diamond":
                            poly.scale_to_fit_height(max_dim)
                        else:  # polygon
                            poly.scale_to_fit_height(max_dim)
                        
                        # 居中
                        poly.shift(-poly.get_center())
                        poly.move_to([0, 0, 0])
                        
                        poly.set_color(texture_color_actual)
                        poly.set_opacity(texture_opacity)
                        cell.add(poly)
            
            cell.move_to([x, y, 0])
            group.add(cell)
        
        return group
    
    # 兼容旧格式：使用pattern
    pattern = obj_cfg.get("pattern")
    if pattern is None:
        pattern = [[1 for _ in range(cols)] for _ in range(rows)]
    
    style_idx = 0
    for r in range(rows):
        for c in range(cols):
            if int(pattern[r][c]) != 1:
                continue
            
            # 位置
            x = origin_x + c * cell_size
            y = origin_y - r * cell_size
            
            # cell
            cell = Square(side_length=cell_size)
            style = cell_colors[style_idx] if style_idx < len(cell_colors) else (cell_colors[-1] if cell_colors else {})
            style_idx += 1

            # 颜色与透明度（使用统一字段）
            fill_color_name = style.get("color", "BLUE")
            fill_color = COLOR_MAP.get(fill_color_name, BLUE)
            fill_opacity = float(uniform_fill_opacity)

            # 描边（使用统一字段）
            if show_grid:
                stroke_color_name = uniform_stroke_color
                stroke_color = COLOR_MAP.get(stroke_color_name, WHITE)
                stroke_width = float(uniform_stroke_width)
                cell.set_stroke(stroke_color, width=stroke_width)
            else:
                cell.set_stroke(None, width=0)

            # 填充
            cell.set_fill(fill_color, opacity=fill_opacity)
            
            # texture处理（根据顶层mode判断，如果mode为空则兼容旧格式）
            is_texture = mode_cfg == "texture" if mode_cfg else style.get("style_type") == "texture"
            if is_texture:
                # 使用统一的texture_color
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
                        poly.rotate(45 * 3.14159 / 180)  # 旋转45度得到菱形
                    else:
                        poly = None
                    
                    if poly:
                        # 调整大小，使其填充cell的一部分
                        max_dim = cell_size * 0.6
                        if shape == "square":
                            poly.scale_to_fit_width(max_dim)
                        elif shape == "circle":
                            poly.scale_to_fit_width(max_dim)
                        elif shape == "diamond":
                            poly.scale_to_fit_height(max_dim)
                        else:  # polygon
                            poly.scale_to_fit_height(max_dim)
                        
                        # 居中
                        poly.shift(-poly.get_center())
                        poly.move_to([0, 0, 0])
                        
                        poly.set_color(texture_color_actual)
                        poly.set_opacity(texture_opacity)
                        cell.add(poly)
            
            cell.move_to([x, y, 0])
            group.add(cell)
    
    # 兼容旧格式：使用pattern
    pattern = obj_cfg.get("pattern")
    if pattern is None:
        pattern = [[1 for _ in range(cols)] for _ in range(rows)]
    
    style_idx = 0
    for r in range(rows):
        for c in range(cols):
            if int(pattern[r][c]) != 1:
                continue
            
            # 位置
            x = origin_x + c * cell_size
            y = origin_y - r * cell_size
            
            # cell
            cell = Square(side_length=cell_size)
            style = cell_colors[style_idx] if style_idx < len(cell_colors) else (cell_colors[-1] if cell_colors else {})
            style_idx += 1
            
            # 颜色与透明度（使用统一字段）
            fill_color_name = style.get("color", "BLUE")
            fill_color = COLOR_MAP.get(fill_color_name, BLUE)
            fill_opacity = float(uniform_fill_opacity)

            # 描边（使用统一字段）
            if show_grid:
                stroke_color_name = uniform_stroke_color
                stroke_color = COLOR_MAP.get(stroke_color_name, WHITE)
                stroke_width = float(uniform_stroke_width)
                cell.set_stroke(stroke_color, width=stroke_width)
            else:
                cell.set_stroke(None, width=0)

            # 填充
            cell.set_fill(fill_color, opacity=fill_opacity)
            
            # texture处理（根据顶层mode判断，如果mode为空则兼容旧格式）
            is_texture = mode_cfg == "texture" if mode_cfg else style.get("style_type") == "texture"
            if is_texture:
                # 使用统一的texture_color
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
                        poly.rotate(45 * 3.14159 / 180)  # 旋转45度得到菱形
                    else:
                        poly = Circle()
                    
                    # 确保polygon的anchor point是center
                    poly.shift(-poly.get_center())
                    # 确保polygon在origin (0,0,0)，然后缩放
                    poly.move_to([0, 0, 0])
                    poly.scale(cell_size / 2.5)
                    poly.set_color(texture_color_actual)
                    poly.set_opacity(texture_opacity)
                    cell.add(poly)
            
            cell.move_to([x, y, 0.0])
            group.add(cell)

    if len(group) == 0:
        # 防御：如果 pattern 全 0，至少给一个透明占位，避免 Manim 抛错
        cell = Square(side_length=cell_size).set_opacity(0.0)
        group.add(cell)

    return group


def compute_output_paths(json_path: str, idx: int, want_first: bool, want_last: bool, want_video: bool):
    """
    依据输入 JSON 路径生成输出路径：
      batch_datetime/2dr_XXX/2dr_XXX_first.jpg / _last.jpg / .mp4
    """
    base_dir = os.path.dirname(json_path)
    stem = f"2dr_{idx:04d}"  # 支持1000以上

    # 输出目录就是JSON所在的目录
    out_dir = base_dir
    ensure_dir(out_dir)

    first_path = os.path.join(out_dir, f"{stem}_first.jpg") if want_first else None
    last_path  = os.path.join(out_dir, f"{stem}_last.jpg")  if want_last  else None
    video_path = os.path.join(out_dir, f"{stem}.mp4")       if want_video else None
    return out_dir, first_path, last_path, video_path


 # -----------------------------
# Manim 场景
# -----------------------------

class GridRotationScene(Scene):
    """
    - 背景色按 JSON video.background_color
    - 线性速度旋转，整个 run_time 都在旋转，**无**额外 wait
    - mode=first: 只输出初始帧
      mode=last : 只输出末帧（直接把对象旋转到终态后保存）
      mode=video: 播放线性 Rotate 动画并写出视频
    """

    def construct(self):
        # 从环境变量获取参数
        json_path = os.environ.get("JSON_PATH")
        mode = os.environ.get("RENDER_MODE", "video")
        
        if not json_path:
            return
        
        # 加载JSON
        cfg = load_json(json_path)
        
        # 获取配置（新结构：直接在顶层）
        rot_cfg = cfg.get("rotation", {})
        vid_cfg = cfg.get("video", {})
        visual_cfg = cfg.get("visual", {})
        
        # 从顶层获取统一字段
        type_cfg = cfg.get("type")
        rows_cfg = cfg.get("rows")
        cols_cfg = cfg.get("cols")
        mode_cfg = cfg.get("mode")
        
        # obj_cfg是variant的配置（兼容旧格式）
        obj_cfg = cfg.get("object", {})
        
        # 从JSON读取duration（优先），如果不存在则从环境变量读取
        duration = float(rot_cfg.get("duration", os.environ.get("RENDER_DURATION", "3.0")))

        # 背景色
        bg = vid_cfg.get("background_color", "#1a1a2e")
        self.camera.background_color = bg

        # 构建网格（传入所有顶层配置）
        grid = grid_mobject_from_json(obj_cfg, visual_cfg, type_cfg, rows_cfg, cols_cfg, mode_cfg)
        self.add(grid)

        # 角度（Manim 逆时针为正；clockwise=True 表示顺时针 => 负角度）
        angle_deg = float(rot_cfg.get("rotation_angle", 90.0))
        clockwise = bool(rot_cfg.get("clockwise", True))
        angle_rad = math.radians(angle_deg) * (-1.0 if clockwise else 1.0)

        # MODE: first
        if mode == "first":
            # 直接保存第一帧
            self.wait(0.01)
            return

        # MODE: last
        if mode == "last":
            # 把对象直接旋到终态，然后保存一帧
            grid.rotate(angle_rad)
            self.wait(0.01)
            return

        # MODE: video
        if mode == "video":
            # 线性速度旋转：整个 run_time = duration
            self.play(
                Rotate(grid, angle=angle_rad),
                run_time=duration,
                rate_func=rate_functions.linear
            )
            return


# -----------------------------
# 渲染调度
# -----------------------------

def extract_frame_from_video(video_path: str, frame_path: str, frame_number: int):
    """从视频中提取单帧
    frame_number: 0表示第一帧，-1表示最后一帧
    """
    if frame_number == -1:
        # 获取视频总帧数，然后提取真正的最后一帧
        # 使用ffprobe获取帧数
        probe_cmd = f"ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 '{video_path}'"
        result = subprocess.run(probe_cmd, shell=True, capture_output=True, timeout=10, text=True)
        if result.returncode == 0:
            total_frames = int(result.stdout.strip())
            # 提取指定帧（最后一帧索引是total_frames-1）
            cmd = f"ffmpeg -i '{video_path}' -vf \"select='eq(n,{total_frames-1})'\" -frames:v 1 -y '{frame_path}'"
        else:
            # 如果获取帧数失败，使用非常小的偏移
            cmd = f"ffmpeg -sseof -0.001 -i '{video_path}' -frames:v 1 -y '{frame_path}'"
    else:
        # 提取第一帧
        cmd = f"ffmpeg -i '{video_path}' -frames:v 1 -y '{frame_path}'"
    
    result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10, text=True)
    if result.returncode != 0:
        print(f"⚠️  提取帧失败: {result.stderr}")


def render_one_variant(variant_obj: Dict[str, Any], out_dir: str, stem: str, variant_idx: int, modes: List[str], duration: float, json_cfg: Dict[str, Any]):
    """渲染单个variant，直接保存到out_dir"""
    # 创建临时JSON文件给variant使用（包含所有顶层配置）
    temp_json = os.path.join(out_dir, f"temp_variant_{variant_idx}.json")
    variant_cfg = {
        "object": variant_obj, 
        "type": json_cfg.get("type"),  # 顶层type
        "rows": json_cfg.get("rows"),  # 顶层rows
        "cols": json_cfg.get("cols"),  # 顶层cols
        "mode": json_cfg.get("mode"),  # 顶层mode
        "visual": json_cfg.get("visual", {}),  # 传递visual参数
        "rotation": json_cfg.get("rotation", {}), 
        "video": json_cfg.get("video", {})
    }
    with open(temp_json, "w") as f:
        json.dump(variant_cfg, f)
    
    # 使用临时目录渲染
    temp_media_dir = os.path.join(out_dir, f"temp_render_{variant_idx}")
    ensure_dir(temp_media_dir)
    
    os.environ["JSON_PATH"] = temp_json
    os.environ["RENDER_MODE"] = "video"  # 总是渲染video模式
    os.environ["RENDER_DURATION"] = str(duration)
    
    config.media_dir = temp_media_dir
    config.output_file = f"{stem}_{variant_idx}"
    
    # 设置输出为720p30fps
    config.pixel_width = 1280
    config.pixel_height = 720
    config.frame_rate = 30
    
    # 渲染视频
    logging.getLogger("manim").setLevel(logging.ERROR)
    logging.getLogger().setLevel(logging.ERROR)
    
    f = io.StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        scene = GridRotationScene()
        scene.render()
    
    # 查找生成的视频文件
    video_cands = sorted(glob.glob(os.path.join(temp_media_dir, "**", "*.mp4"), recursive=True), key=os.path.getmtime)
    
    if not video_cands:
        shutil.rmtree(temp_media_dir, ignore_errors=True)
        os.remove(temp_json)
        return
    
    final_video = video_cands[-1]
    
    # 根据mode保存对应输出
    if "video" in modes:
        target_video = os.path.join(out_dir, f"{stem}_{variant_idx}.mp4")
        shutil.copy2(final_video, target_video)
    
    # 提取帧（如果需要）
    if "first" in modes or "last" in modes:
        for frame_mode in ["first", "last"]:
            if frame_mode not in modes:
                continue
            frame_num = 0 if frame_mode == "first" else -1
            target_frame = os.path.join(out_dir, f"{stem}_{variant_idx}_{frame_mode}.jpg")
            extract_frame_from_video(final_video, target_frame, frame_num)
    
    # 清理临时文件
    if "video" not in modes:
        os.remove(final_video)
    shutil.rmtree(temp_media_dir, ignore_errors=True)
    os.remove(temp_json)


def render_one(json_path: str, modes: List[str], idx: int, duration: float = 3.0):
    """渲染JSON及其所有variants"""
    out_dir = os.path.dirname(json_path)
    stem = f"2dr_{idx:04d}"
    
    # 加载JSON
    cfg = load_json(json_path)
    rot_cfg = cfg.get("rotation", {})
    duration = float(rot_cfg.get("duration", duration))
    variants = cfg.get("variants", {})
    
    # 如果没有variants，说明是旧格式JSON，跳过
    if not variants:
        return
    
    # Task模式：特殊的渲染逻辑
    if "task" in modes:
        # s0: 渲染 first, last, video
        if "s0" in variants:
            render_one_variant(variants["s0"], out_dir, stem, 0, ["first", "last", "video"], duration, cfg)
        
        # s1-s4: 只渲染 last
        for i in range(1, 5):
            variant_key = f"s{i}"
            if variant_key in variants:
                render_one_variant(variants[variant_key], out_dir, stem, i, ["last"], duration, cfg)
        return
    
    # 正常模式：渲染所有variants（不包括s5，因为已被注释）
    for variant_key in sorted(variants.keys()):  # s0, s1, s2, s3, s4
        if variant_key == "s5":  # 跳过s5
            continue
        variant_obj = variants[variant_key]
        variant_idx = int(variant_key[1])  # 从s0 -> 0
        
        # 渲染所有variants
        render_one_variant(variant_obj, out_dir, stem, variant_idx, modes, duration, cfg)


def parse_range(range_str: str):
    """解析 --range 参数，返回过滤说明。
    支持：
      - 'N'        : 选取前 N 个实例（按编号排序）
      - 'A:B'      : 选取编号在 [A, B] 区间（闭区间）
      - 'A:'       : 选取编号 >= A 的所有实例
      - ':B'       : 选取编号 <= B 的所有实例
      - '[A,B]'    : 选取编号在 [A, B] 区间（与 A:B 等价）
    返回：
      - ("first_n", N)
      - ("pred", lambda idx: bool)
    """
    if not range_str:
        return None
    s = str(range_str).strip()
    try:
        # [A,B] 形式
        if s.startswith('[') and s.endswith(']'):
            parts = s.strip('[]').split(',')
            start, end = int(parts[0].strip()), int(parts[1].strip())
            return ("pred", lambda i, a=start, b=end: (i >= a and i <= b))

        # A:B / A: / :B 形式
        if ':' in s:
            left, right = s.split(':', 1)
            left = left.strip()
            right = right.strip()
            start = int(left) if left else None
            end = int(right) if right else None
            return ("pred", lambda i, a=start, b=end: (a is None or i >= a) and (b is None or i <= b))

        # 单个数字：前 N 个
        n = int(s)
        return ("first_n", n)
    except Exception:
        return None


def render_batch(batch_dir: str, modes: List[str], range_filter: str = None, duration: float = 3.0):
    """
    遍历 batch_dir 下所有 2dr_XXX/2dr_XXX.json 文件并逐个渲染
    """
    # 扫描所有2dr_XXX子目录
    json_files = []
    for subdir in sorted(os.listdir(batch_dir)):
        subdir_path = os.path.join(batch_dir, subdir)
        if os.path.isdir(subdir_path) and subdir.startswith("2dr_"):
            # 在该目录下查找2dr_XXX.json
            json_file = os.path.join(subdir_path, subdir + ".json")
            if os.path.exists(json_file):
                dir_name = os.path.basename(os.path.dirname(json_file))
                file_idx = int(dir_name.replace("2dr_", ""))
                json_files.append((file_idx, json_file))
    
    if not json_files:
        print(f"[WARN] 目录 {batch_dir} 下没有找到 JSON 文件。")
        return
    
    # 应用range过滤器
    rf = parse_range(range_filter)
    if rf:
        kind, val = rf
        if kind == "first_n":
            # 取前 N 个（已按 idx 升序排序）
            json_files = json_files[:max(0, int(val))]
        elif kind == "pred":
            pred = val
            json_files = [(idx, jp) for idx, jp in json_files if pred(idx)]
    
    if not json_files:
        print(f"[WARN] 筛选后没有找到符合条件的JSON文件。")
        return
    
    # 使用tqdm显示进度条
    total = len(json_files)
    with tqdm(total=total, desc="渲染进度", unit="个") as pbar:
        for file_idx, jp in json_files:
            name = os.path.basename(jp)
            pbar.set_postfix_str(f"当前: {name}")
            render_one(jp, modes=modes, idx=file_idx, duration=duration)
            pbar.update(1)


# -----------------------------
# CLI
# -----------------------------

def main():
    parser = argparse.ArgumentParser(description="2D Grid Manim Renderer (linear rotation, no waits).")
    parser.add_argument("target", nargs='?', type=str, help="batch目录路径（位置参数）")
    parser.add_argument("--input", type=str, default=None, help="单个 JSON 配置文件路径")
    parser.add_argument("--batch_dir", type=str, default=None, help="批量目录，遍历其中所有 *.json")
    parser.add_argument("--mode", type=str, required=True, help="渲染模式，多个用逗号分隔：first,last,video")
    parser.add_argument("--range", type=str, default=None, help="渲染范围：'5'表示前5个，'[1,5]'表示1-5")
    parser.add_argument("--duration", type=float, default=None, help="视频模式时的时长（秒），默认从JSON读取")
    args = parser.parse_args()

    # 支持位置参数作为batch_dir
    batch_dir = args.target or args.batch_dir
    
    if not args.input and not batch_dir:
        print("请提供 --input 或 batch目录路径。")
        sys.exit(1)

    # 解析模式（支持逗号分隔）
    modes = [m.strip() for m in args.mode.split(",")]
    valid_modes = ["first", "last", "video", "task"]
    for m in modes:
        if m not in valid_modes:
            print(f"错误：模式 '{m}' 不在 {valid_modes} 中")
            sys.exit(1)

    # 如果提供了duration，作为fallback
    duration = args.duration if args.duration is not None else 3.0

    if args.input:
        render_one(args.input, modes=modes, idx=1, duration=duration)
    if batch_dir:
        render_batch(batch_dir, modes=modes, range_filter=args.range, duration=duration)


if __name__ == "__main__":
    main()