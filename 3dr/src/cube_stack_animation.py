#!/usr/bin/env python3
"""
MRT cube-stack rotation animation (Manim-based).

Handles: rotation params (speed, angle, direction), camera and visual config,
scene render and output paths, and optional meta recording.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path

import json
import os

import numpy as np
from manim import *  # noqa: F401,F403 - Manim expects star imports in scenes

from .voxel_space import (
    VoxelSpace, VoxelData, 
    CubeVisualConfig
)

# ==================== Render paths ====================

DEFAULT_MEDIA_DIR = "medias"
DEFAULT_OUTPUT_DIR = "medias/videos"
DEFAULT_IMAGES_DIR = "medias/images"
DEFAULT_TEX_DIR = "medias/Tex"
DEFAULT_META_DIR = "meta"

MEDIA_DIR = DEFAULT_MEDIA_DIR
OUTPUT_DIR = DEFAULT_OUTPUT_DIR
IMAGES_DIR = DEFAULT_IMAGES_DIR
TEX_DIR = DEFAULT_TEX_DIR
META_DIR = DEFAULT_META_DIR

VOXEL_CONFIG = {
    "size": (10, 10, 10),
    "cube_size": 1.0,
    "spacing": 0.0,
    "default_style": {
        "fill_color": BLUE,
        "fill_opacity": 0.8,
        "stroke_color": WHITE,
        "stroke_width": 1,
        "stroke_opacity": 1.0
    }
}

# ==================== Rotation config ====================

class RotationSpeed(Enum):
    """Rotation speed presets for animation duration."""
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"

ROTATION_SPEED_CONFIG = {
    RotationSpeed.SLOW: {"name": "slow", "base_duration": 4.0, "angle_factor": 0.5, "description": "Slow rotation"},
    RotationSpeed.MEDIUM: {"name": "medium", "base_duration": 2.0, "angle_factor": 1.0, "description": "Medium rotation"},
    RotationSpeed.FAST: {"name": "fast", "base_duration": 1.0, "angle_factor": 2.0, "description": "Fast rotation"},
}

PRESET_ROTATION_VECTORS = {
    "x_axis": (1.0, 0.0, 0.0),
    "y_axis": (0.0, 1.0, 0.0),
    "z_axis": (0.0, 0.0, 1.0),
    "diagonal_xy": (1.0, 1.0, 0.0),
    "diagonal_xz": (1.0, 0.0, 1.0),
    "diagonal_yz": (0.0, 1.0, 1.0),
    "diagonal_xyz": (1.0, 1.0, 1.0),
}

PRESET_ANGLES = {
    "quarter": 90,
    "half": 180,
    "three_quarter": 270,
    "full": 360,
    "small": 45,
    "medium": 120,
    "large": 300,
}

@dataclass
class RotationParams:
    """Unified rotation parameters: axis, angle (degrees), clockwise, duration, speed, center_mode (mass/cube)."""
    rotation_vector: Tuple[float, float, float] = (0.0, 0.0, 1.0)
    rotation_angle: float = 90.0
    clockwise: bool = False
    duration: Optional[float] = None
    rotation_speed: RotationSpeed = RotationSpeed.MEDIUM
    rate_func: str = "linear"
    center_mode: str = "mass"

    @classmethod
    def from_preset(cls, vector_name: str, angle_name: str,
                   clockwise: bool = False,
                   speed: RotationSpeed = RotationSpeed.MEDIUM) -> 'RotationParams':
        """Build from preset vector and angle names."""
        vector = PRESET_ROTATION_VECTORS.get(vector_name, (0, 0, 1))
        angle = PRESET_ANGLES.get(angle_name, 90)
        return cls(rotation_vector=vector, rotation_angle=angle, clockwise=clockwise, rotation_speed=speed)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RotationParams':
        """Build from config dict."""
        return cls(
            rotation_vector=tuple(data.get("rotation_vector", [0, 0, 1])),
            rotation_angle=data.get("rotation_angle", 90),
            clockwise=data.get("clockwise", False),
            duration=data.get("duration"),
            rotation_speed=RotationSpeed(data.get("rotation_speed", "medium")),
            rate_func=data.get("rate_func", "linear"),
            center_mode=data.get("center_mode", "mass")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rotation_vector": list(self.rotation_vector),
            "rotation_angle": self.rotation_angle,
            "clockwise": self.clockwise,
            "duration": self.duration,
            "rotation_speed": self.rotation_speed.value,
            "rate_func": self.rate_func,
            "center_mode": self.center_mode
        }


# ==================== Output paths ====================

@dataclass
class OutputConfig:
    """Output paths and video render params: media_dir, video_dir, image_dir, tex_dir, meta_dir, filename, resolution, frame_rate."""
    media_dir: str = DEFAULT_MEDIA_DIR
    video_dir: str = DEFAULT_OUTPUT_DIR
    image_dir: str = DEFAULT_IMAGES_DIR
    tex_dir: str = DEFAULT_TEX_DIR
    meta_dir: str = DEFAULT_META_DIR
    filename: Optional[str] = None
    pixel_width: Optional[int] = None
    pixel_height: Optional[int] = None
    frame_rate: Optional[int] = None
    quality: Optional[str] = None
    format: str = "mp4"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutputConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==================== Video / camera config ====================

@dataclass
class VideoConfig:
    """Camera (phi, theta, gamma, distance, zoom) and visual toggles (axes, rotation_axis, etc.)."""
    phi: float = 75
    theta: float = 30
    gamma: float = 0
    distance: Optional[float] = None
    zoom: float = 1.0
    frame_width: Optional[float] = None
    frame_height: Optional[float] = None
    show_axes: bool = True
    show_axes_labels: bool = True
    show_rotation_axis: bool = True
    show_rotation_circle: bool = False
    show_velocity_arrow: bool = False
    show_labels: bool = False
    show_bounding_box: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VideoConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    

VISUAL_CONFIG = {
    "show_axes": True,
    "show_axes_labels": True,
    "show_rotation_axis": True,
    "show_rotation_circle": False,
    "show_velocity_arrow": False,
    "show_labels": False,
    "show_bounding_box": False,
}

CAMERA_CONFIG = {
    "phi": 75,
    "theta": 30,
    "gamma": 0,
    "distance": None,
    "zoom": 1.0,
}

# ==================== Config loading ====================

def load_config_from_file(filepath: Union[str, Path]) -> Tuple[VoxelData, RotationParams, VideoConfig, CubeVisualConfig, OutputConfig]:
    """
    Load full config from JSON: voxel, rotation, video, cube visual, output.
    grid_size [x_max, y_max, z_max] defines grid bounds; coords in [0, x_max) etc.; out-of-range coords are ignored with a warning.
    """
    filepath = Path(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        config = json.load(f)
    voxel_config = config.get("voxel", {})
    voxel_type = voxel_config.get("type", "template")
    
    if voxel_type == "coordinates":
        # 支持简单坐标或带颜色的坐标
        raw_data = voxel_config["data"]
        coords = []
        
        # 检测数据格式
        if raw_data and isinstance(raw_data[0], dict):
            # 带颜色格式：[{"pos": [x,y,z], "color": "BLUE"}, ...]
            coords = raw_data
        else:
            # 简单坐标格式：[[x,y,z], ...]
            coords = [tuple(c) if isinstance(c, list) else c for c in raw_data]
        
        grid_size = tuple(voxel_config.get("grid_size", (10, 10, 10)))
        voxel_data = VoxelData.from_coordinates(coords, grid_size)
    elif voxel_type == "array":
        voxel_data = VoxelData.from_array(voxel_config["data"])
    elif voxel_type == "template":
        voxel_data = VoxelData.from_template(voxel_config.get("data", "l_shape"))
    elif voxel_type == "file":
        voxel_data = VoxelData.from_file(voxel_config["data"])
    else:
        raise ValueError(f"Unknown voxel type: {voxel_type}")

    rotation_config = config.get("rotation", {})
    rotation_params = RotationParams.from_dict(rotation_config)
    video_config_data = config.get("video", {})
    video_config = VideoConfig.from_dict(video_config_data)
    cube_visual_data = voxel_config.get("visual", config.get("cube_visual", {}))
    cube_visual_config = CubeVisualConfig.from_dict(cube_visual_data)
    output_data = config.get("output", {})
    output_config = OutputConfig.from_dict(output_data)
    return voxel_data, rotation_params, video_config, cube_visual_config, output_config


def calculate_duration_from_speed(rotation_angle: float, speed: RotationSpeed) -> float:
    """Compute animation duration (seconds) from rotation angle (radians) and speed preset. Clamped to [0.5, 10]."""
    config = ROTATION_SPEED_CONFIG[speed]
    base_duration = config["base_duration"]
    angle_factor = config["angle_factor"]
    angle_ratio = abs(rotation_angle) / (2 * np.pi)
    duration = base_duration * (angle_factor * angle_ratio + (1 - angle_factor))
    return max(0.5, min(10.0, duration))


def generate_filename(voxel_data, rotation_vector, rotation_angle, clockwise, rotation_speed=None):
    """Generate timestamp-based filename (YYYYMMDD_HHMMSS.mp4)."""
    from datetime import datetime
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"


class CubeStackRotation(ThreeDScene):
    """Manim 3D scene: voxel stack rotating by given axis, angle, and direction."""

    def __init__(self, voxel_data: Union[List[List[List[int]]], VoxelData] = None,
                 rotation_vector: Tuple[float, float, float] = (0, 0, 1),
                 rotation_angle: float = 2 * PI,
                 clockwise: bool = False,
                 duration: float = None,
                 rotation_speed: RotationSpeed = RotationSpeed.MEDIUM,
                 voxel_offset: Tuple[int, int, int] = (0, 0, 0),
                 center_mode: str = "mass",
                 video_config: Optional[VideoConfig] = None,
                 cube_visual_config: Optional[CubeVisualConfig] = None,
                 **kwargs):
        """voxel_data: 3D voxel coords. rotation_vector/angle/clockwise define rotation. duration from speed if None."""
        super().__init__(**kwargs)
        if voxel_data is None:
            default_array = [
                [[1, 1, 1], [1, 1, 0], [1, 0, 0]],
                [[1, 1, 0], [1, 1, 0], [1, 0, 0]],
                [[1, 1, 0], [1, 1, 0], [1, 0, 0]]
            ]
            voxel_data = VoxelData.from_array(default_array)
        elif isinstance(voxel_data, list):
            voxel_data = VoxelData.from_array(voxel_data)

        self.voxel_data_obj = voxel_data
        self.rotation_vector = np.array(rotation_vector)
        self.rotation_angle = rotation_angle
        self.clockwise = clockwise
        self.rotation_speed = rotation_speed
        self.voxel_offset = voxel_offset
        self.center_mode = center_mode
        self.video_config = video_config if video_config else VideoConfig()
        self.cube_visual_config = cube_visual_config if cube_visual_config else CubeVisualConfig(
            cube_size=VOXEL_CONFIG["cube_size"],
            spacing=VOXEL_CONFIG["spacing"],
            fill_color=VOXEL_CONFIG["default_style"]["fill_color"],
            fill_opacity=VOXEL_CONFIG["default_style"]["fill_opacity"],
            stroke_color=VOXEL_CONFIG["default_style"]["stroke_color"],
            stroke_width=VOXEL_CONFIG["default_style"]["stroke_width"],
            stroke_opacity=VOXEL_CONFIG["default_style"]["stroke_opacity"]
        )
        self.rotation_vector = self.rotation_vector / np.linalg.norm(self.rotation_vector)
        if clockwise:
            self.rotation_angle = -self.rotation_angle
        if duration is None:
            self.duration = calculate_duration_from_speed(abs(self.rotation_angle), rotation_speed)
        else:
            self.duration = duration
        self.voxel_space = VoxelSpace(voxel_data=self.voxel_data_obj, visual_config=self.cube_visual_config)

    def construct(self):
        """Build the rotation animation scene."""
        if self.video_config.frame_width is not None:
            self.camera.frame_width = self.video_config.frame_width
        if self.video_config.frame_height is not None:
            self.camera.frame_height = self.video_config.frame_height
        
        # 创建3D坐标轴（使用video_config）
        if self.video_config.show_axes:
            axes = ThreeDAxes(
                x_range=[-3, 3, 1],
                y_range=[-3, 3, 1],
                z_range=[-3, 3, 1],
                x_length=6,
                y_length=6,
                z_length=6
            )
            self.add(axes)
            
            if self.video_config.show_axes_labels:
                axes_labels = axes.get_axis_labels(x_label="X", y_label="Y", z_label="Z")
                self.add(axes_labels)
        
        cubes = self.voxel_space.get_all_cubes()
        if cubes:
            if self.center_mode == "cube":
                rotation_center = self.voxel_space.get_center_cube()
            else:
                rotation_center = self.voxel_space.get_center_of_mass()
            for cube in cubes:
                cube.shift(-rotation_center)
            
            self.add(*cubes)
        
        self.set_camera_orientation(
            phi=self.video_config.phi * DEGREES,
            theta=self.video_config.theta * DEGREES,
            gamma=self.video_config.gamma * DEGREES
        )
        
        # 设置相机距离和缩放
        if self.video_config.distance is not None:
            self.camera.set_distance(self.video_config.distance)
        
        if self.video_config.zoom != 1.0:
            self.camera.set_zoom(self.video_config.zoom)
        
        # 显示旋转轴箭头
        if self.video_config.show_rotation_axis:
            rotation_axis_arrow = Arrow3D(
                start=ORIGIN,
                end=self.rotation_vector * 2,
                color=RED,
                thickness=0.02
            )
            self.add(rotation_axis_arrow)
        
        # 显示边界框
        if self.video_config.show_bounding_box:
            min_pos, max_pos = self.voxel_space.get_bounding_box()
            bounding_box = Cube(
                side_length=max(max_pos - min_pos),
                fill_opacity=0,
                stroke_color=YELLOW,
                stroke_width=1
            )
            bounding_box.move_to((min_pos + max_pos) / 2)
            self.add(bounding_box)
        
        # 创建旋转动画
        if cubes:
            # 旋转中心已经对齐到原点，绕原点旋转
            rotation_animations = []
            for cube in cubes:
                rotation_anim = Rotate(
                    cube,
                    angle=self.rotation_angle,
                    axis=self.rotation_vector,
                    about_point=ORIGIN,  # 绕原点旋转
                    run_time=self.duration,
                    rate_func=linear  # 线性速度
                )
                rotation_animations.append(rotation_anim)
            
            # 同时执行所有方块的旋转动画
            self.play(AnimationGroup(*rotation_animations, lag_ratio=0))
        
        # 暂停一下
        # self.wait(1)

# 使用示例函数
def create_cube_stack_video(voxel_data: Union[List[List[List[int]]], VoxelData] = None,
                           rotation_vector=(0, 0, 1), 
                           rotation_angle=90,  # 度数
                           clockwise=False, 
                           duration=None,
                           rotation_speed=RotationSpeed.MEDIUM,
                           voxel_offset=(0, 0, 0),
                           center_mode="mass",
                           output_file=None,
                           video_config: Optional[VideoConfig] = None,
                           cube_visual_config: Optional[CubeVisualConfig] = None,
                           output_config: Optional[OutputConfig] = None,
                           save_meta: bool = True):
    """
    创建方块堆叠旋转视频的便捷函数
    
    Args:
        voxel_data: 3D方块数据
        rotation_vector: 旋转轴向量 (x, y, z)
        rotation_angle: 旋转角度（度）
        clockwise: 是否顺时针旋转
        duration: 动画持续时间（秒），如果为None则根据rotation_speed自动计算
        rotation_speed: 旋转速度（SLOW/MEDIUM/FAST）
        voxel_offset: voxel数据的偏移量
        output_file: 输出文件名（如果为None则自动生成）
    """
    if output_config is None:
        output_config = OutputConfig()
    rotation_angle_rad = rotation_angle * np.pi / 180
    
    # 如果没有指定输出文件名，则自动生成
    if output_file is None and output_config.filename is None:
        output_file = generate_filename(voxel_data, rotation_vector, rotation_angle_rad, clockwise, rotation_speed)
    elif output_config.filename is not None:
        output_file = f"{output_config.filename}.mp4"
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 确保所有媒体目录存在（正确处理绝对路径和相对路径）
    media_dir_abs = output_config.media_dir if os.path.isabs(output_config.media_dir) else os.path.join(script_dir, output_config.media_dir)
    video_dir_abs = output_config.video_dir if os.path.isabs(output_config.video_dir) else os.path.join(script_dir, output_config.video_dir)
    image_dir_abs = output_config.image_dir if os.path.isabs(output_config.image_dir) else os.path.join(script_dir, output_config.image_dir)
    tex_dir_abs = output_config.tex_dir if os.path.isabs(output_config.tex_dir) else os.path.join(script_dir, output_config.tex_dir)
    meta_dir_abs = output_config.meta_dir if os.path.isabs(output_config.meta_dir) else os.path.join(script_dir, output_config.meta_dir)
    
    os.makedirs(media_dir_abs, exist_ok=True)
    os.makedirs(video_dir_abs, exist_ok=True)
    os.makedirs(image_dir_abs, exist_ok=True)
    os.makedirs(tex_dir_abs, exist_ok=True)
    os.makedirs(meta_dir_abs, exist_ok=True)
    
    # 设置媒体路径（使用绝对路径），避免 Manim 在 media_dir 下创建默认的 images/
    config.media_dir = media_dir_abs
    config.video_dir = video_dir_abs
    config.image_dir = image_dir_abs
    config.output_file = output_file.replace(".mp4", "")
    
    # 应用视频渲染参数
    if output_config.pixel_width is not None:
        config.pixel_width = output_config.pixel_width
    if output_config.pixel_height is not None:
        config.pixel_height = output_config.pixel_height
    if output_config.frame_rate is not None:
        config.frame_rate = output_config.frame_rate
    if output_config.quality is not None:
        # 设置画质预设
        quality_map = {
            "low_quality": "low_quality",
            "medium_quality": "medium_quality", 
            "high_quality": "high_quality",
            "production_quality": "production_quality"
        }
        if output_config.quality in quality_map:
            config.quality = quality_map[output_config.quality]
    
    scene = CubeStackRotation(
        voxel_data=voxel_data,
        rotation_vector=rotation_vector,
        rotation_angle=rotation_angle_rad,
        clockwise=clockwise,
        duration=duration,
        rotation_speed=rotation_speed,
        voxel_offset=voxel_offset,
        center_mode=center_mode,
        video_config=video_config,
        cube_visual_config=cube_visual_config
    )
    
    scene.render()
    target_path = os.path.join(video_dir_abs, output_file)
    possible_paths = [
        target_path,
        os.path.join(video_dir_abs, "720p30", output_file),
        os.path.join(video_dir_abs, "1080p60", output_file),
        os.path.join(video_dir_abs, "480p15", output_file),
        os.path.join(video_dir_abs, "360p30", output_file),
        os.path.join(media_dir_abs, "videos", "720p30", output_file),
        os.path.join(media_dir_abs, "videos", "1080p60", output_file),
        os.path.join(media_dir_abs, "videos", "480p15", output_file),
        os.path.join(media_dir_abs, "videos", "360p30", output_file),
        os.path.join(media_dir_abs, f"{output_file.replace('.mp4', '')}.mp4"),
    ]
    
    actual_path = None
    for path in possible_paths:
        if os.path.exists(path):
            actual_path = path
            break
    
    if actual_path and actual_path != target_path:
        import shutil
        shutil.move(actual_path, target_path)
        print(f"Video saved: {target_path}")
    elif os.path.exists(target_path):
        print(f"Video saved: {target_path}")
    else:
        print(f"Video file not found: {target_path}")
        for path in possible_paths:
            print(f"  - {path}")

    if save_meta and os.path.exists(target_path):
        try:
            if isinstance(voxel_data, VoxelData):
                voxel_meta = {
                    "coordinates": voxel_data.coordinates,
                    "colors": {str(k): v for k, v in voxel_data.colors.items()},
                    "grid_size": voxel_data.grid_size
                }
            else:
                voxel_meta = voxel_data
            
            meta_data = {
                "video_name": f"CubeStack_{rotation_vector}_Angle_{rotation_angle:.1f}_{'Clockwise' if clockwise else 'CounterClockwise'}_{rotation_speed.value}",
                "rotation_vector": list(rotation_vector),
                "rotation_angle": rotation_angle_rad,
                "clockwise": clockwise,
                "duration": scene.duration,
                "rotation_speed": rotation_speed.value,
                "center_mode": center_mode,
                "voxel_data": voxel_meta,
                "voxel_offset": list(voxel_offset),
                "camera_config": CAMERA_CONFIG.copy(),
                "visual_elements": VISUAL_CONFIG.copy(),
                "output_file": target_path
            }
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            meta_file = os.path.join(meta_dir_abs, f"meta_{timestamp}.json")
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, indent=2, ensure_ascii=False)
            print(f"Meta saved: {meta_file}")
        except Exception as e:
            print(f"Meta save failed: {e}")
    return target_path


def create_video_from_config(config_file: Union[str, Path], save_meta: bool = True) -> str:
    """Load JSON config and render one MRT rotation video. Returns path to output video file."""
    print(f"\nLoading config: {config_file}")
    voxel_data, rotation_params, video_config, cube_visual_config, output_config = load_config_from_file(config_file)
    print(f"  Voxel: {len(voxel_data.coordinates)} cubes")
    if voxel_data.colors:
        print(f"  Colors: {len(voxel_data.colors)}")
    print(f"  Rotation: {rotation_params.rotation_vector} @ {rotation_params.rotation_angle}°")
    print(f"  Video: phi={video_config.phi}°, theta={video_config.theta}°")
    print(f"  Output: {output_config.video_dir}")
    result = create_cube_stack_video(
        voxel_data=voxel_data,  # 直接传递 VoxelData 对象
        rotation_vector=rotation_params.rotation_vector,
        rotation_angle=rotation_params.rotation_angle,
        clockwise=rotation_params.clockwise,
        duration=rotation_params.duration,
        rotation_speed=rotation_params.rotation_speed,
        voxel_offset=(0, 0, 0),
        center_mode=rotation_params.center_mode,
        video_config=video_config,
        cube_visual_config=cube_visual_config,
        output_config=output_config,
        save_meta=save_meta
    )
    
    return result

def render_batch_folder(batch_folder: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Render all JSON configs in a folder to videos.
    
    Args:
        batch_folder: Path to folder containing mrt_*.json configs.
        
    Returns:
        List of result dicts (config, output, status).
    """
    batch_folder = Path(batch_folder)
    if not batch_folder.exists():
        raise FileNotFoundError(f"Folder not found: {batch_folder}")
    
    config_files = sorted(batch_folder.glob("mrt_*.json"))
    
    if not config_files:
        print(f"No config files found in: {batch_folder}")
        return []
    
    print(f"Batch render: {batch_folder.name}")
    print(f"Found {len(config_files)} configs\n")
    
    results = []
    for idx, config_file in enumerate(config_files, 1):
        print(f"\n[{idx}/{len(config_files)}] 渲染: {config_file.name}")
        print("-" * 60)
        
        try:
            result = create_video_from_config(str(config_file))
            results.append({
                "index": idx,
                "config": str(config_file),
                "output": result,
                "status": "success"
            })
            print(f"Done: {result}")
        except Exception as e:
            print(f"Failed: {e}")
            results.append({
                "index": idx,
                "config": str(config_file),
                "error": str(e),
                "status": "failed"
            })
    
    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"\nBatch done: success {success_count}/{len(config_files)}, failed {len(config_files) - success_count}/{len(config_files)}")
    return results


if __name__ == "__main__":
    import sys
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        batch_folder = sys.argv[1]
        if not os.path.isabs(batch_folder):
            batch_folder = os.path.join(script_dir, batch_folder)
        render_batch_folder(batch_folder)
    else:
        print("MRT-CubeStack: render rotation animation from config")
        config_file = os.path.join(script_dir, "example_colorful_config.json")
        if Path(config_file).exists():
            result = create_video_from_config(config_file)
            print(f"Saved: {result}")
        else:
            print(f"Config not found: {config_file}")
            print("Using default L-shape...")
            default_array = [
                [[1, 1, 1], [1, 1, 0], [1, 0, 0]],
                [[1, 1, 0], [1, 1, 0], [1, 0, 0]],
                [[1, 1, 0], [1, 1, 0], [1, 0, 0]]
            ]
            voxel_data = VoxelData.from_array(default_array)
            result = create_cube_stack_video(
                voxel_data=voxel_data,
                rotation_vector=(0, 0, 1),
                rotation_angle=90,
                clockwise=False,
                rotation_speed=RotationSpeed.MEDIUM
            )
            print(f"Saved: {result}")