#!/usr/bin/env python3
"""
MRT-Cube Stack 旋转动画系统
基于Manim的3D方块堆叠旋转动画

负责：
1. 旋转动画参数配置（速度、角度、方向）
2. 相机角度和视觉效果配置
3. 动画场景的渲染和输出
4. Meta 数据的记录和管理
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

from voxel_space import (
    VoxelSpace, VoxelData, 
    CubeVisualConfig
)

# ==================== 渲染配置 ====================

# 默认媒体路径配置（相对于脚本所在目录）
DEFAULT_MEDIA_DIR = "medias"           # 媒体根目录
DEFAULT_OUTPUT_DIR = "medias/videos"   # 视频输出目录
DEFAULT_IMAGES_DIR = "medias/images"   # 图片输出目录
DEFAULT_TEX_DIR = "medias/Tex"         # LaTeX输出目录
DEFAULT_META_DIR = "meta"              # Meta数据目录

# 兼容旧路径（向后兼容）
MEDIA_DIR = DEFAULT_MEDIA_DIR
OUTPUT_DIR = DEFAULT_OUTPUT_DIR
IMAGES_DIR = DEFAULT_IMAGES_DIR
TEX_DIR = DEFAULT_TEX_DIR
META_DIR = DEFAULT_META_DIR

# Voxel空间配置
VOXEL_CONFIG = {
    "size": (10, 10, 10),        # 3D网格尺寸 (x, y, z)
    "cube_size": 1.0,            # 单个方块尺寸（默认）
    "spacing": 0.0,              # 方块间距（默认：无间距）
    "default_style": {           # 默认方块样式
        "fill_color": BLUE,
        "fill_opacity": 0.8,
        "stroke_color": WHITE,
        "stroke_width": 1,
        "stroke_opacity": 1.0
    }
}

# ==================== 旋转动画配置（参考 rotation_animation.py）====================

# 旋转速度枚举
class RotationSpeed(Enum):
    """旋转速度枚举"""
    SLOW = "slow"      # 慢速
    MEDIUM = "medium"  # 中速
    FAST = "fast"      # 快速

# 旋转速度配置
ROTATION_SPEED_CONFIG = {
    RotationSpeed.SLOW: {
        "name": "慢速",
        "base_duration": 4.0,    # 基础持续时间（秒）
        "angle_factor": 0.5,     # 角度因子
        "description": "慢速旋转，适合观察细节"
    },
    RotationSpeed.MEDIUM: {
        "name": "中速", 
        "base_duration": 2.0,    # 基础持续时间（秒）
        "angle_factor": 1.0,     # 角度因子
        "description": "中等速度旋转，平衡观察和效率"
    },
    RotationSpeed.FAST: {
        "name": "快速",
        "base_duration": 1.0,    # 基础持续时间（秒）
        "angle_factor": 2.0,     # 角度因子
        "description": "快速旋转，适合快速预览"
    }
}

# 预设旋转向量（参考 rotation_animation.py）
PRESET_ROTATION_VECTORS = {
    "x_axis": (1.0, 0.0, 0.0),           # X轴
    "y_axis": (0.0, 1.0, 0.0),           # Y轴
    "z_axis": (0.0, 0.0, 1.0),           # Z轴
    "diagonal_xy": (1.0, 1.0, 0.0),      # XY对角线
    "diagonal_xz": (1.0, 0.0, 1.0),      # XZ对角线
    "diagonal_yz": (0.0, 1.0, 1.0),      # YZ对角线
    "diagonal_xyz": (1.0, 1.0, 1.0),     # XYZ对角线
}

# 预设角度
PRESET_ANGLES = {
    "quarter": 90,                # 90度
    "half": 180,                  # 180度
    "three_quarter": 270,         # 270度
    "full": 360,                  # 360度
    "small": 45,                  # 45度
    "medium": 120,                # 120度
    "large": 300                  # 300度
}

@dataclass
class RotationParams:
    """
    统一的旋转参数格式（参考 rotation_animation.py）
    """
    rotation_vector: Tuple[float, float, float] = (0.0, 0.0, 1.0)  # 旋转轴
    rotation_angle: float = 90.0                                    # 旋转角度（度）
    clockwise: bool = False                                         # 是否顺时针
    duration: Optional[float] = None                                # 持续时间（秒）
    rotation_speed: RotationSpeed = RotationSpeed.MEDIUM           # 旋转速度
    rate_func: str = "linear"                                       # 速率函数
    center_mode: str = "mass"                                       # 旋转中心模式：mass=质心，cube=最中心方块
    
    @classmethod
    def from_preset(cls, vector_name: str, angle_name: str, 
                   clockwise: bool = False, 
                   speed: RotationSpeed = RotationSpeed.MEDIUM) -> 'RotationParams':
        """从预设创建"""
        vector = PRESET_ROTATION_VECTORS.get(vector_name, (0, 0, 1))
        angle = PRESET_ANGLES.get(angle_name, 90)
        return cls(
            rotation_vector=vector,
            rotation_angle=angle,
            clockwise=clockwise,
            rotation_speed=speed
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RotationParams':
        """从字典创建"""
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
        """转换为字典"""
        return {
            "rotation_vector": list(self.rotation_vector),
            "rotation_angle": self.rotation_angle,
            "clockwise": self.clockwise,
            "duration": self.duration,
            "rotation_speed": self.rotation_speed.value,
            "rate_func": self.rate_func,
            "center_mode": self.center_mode
        }

# ==================== 输出路径配置 ====================

@dataclass
class OutputConfig:
    """
    输出配置
    
    包括：路径、分辨率、帧率等视频渲染参数
    """
    # 路径配置
    media_dir: str = DEFAULT_MEDIA_DIR        # 媒体根目录
    video_dir: str = DEFAULT_OUTPUT_DIR       # 视频输出目录
    image_dir: str = DEFAULT_IMAGES_DIR       # 图片输出目录
    tex_dir: str = DEFAULT_TEX_DIR            # LaTeX输出目录
    meta_dir: str = DEFAULT_META_DIR          # Meta数据目录
    filename: Optional[str] = None            # 自定义文件名（不含扩展名）
    
    # 视频渲染参数
    pixel_width: Optional[int] = None         # 视频宽度（像素），默认 1920
    pixel_height: Optional[int] = None        # 视频高度（像素），默认 1080
    frame_rate: Optional[int] = None          # 帧率（fps），默认 60
    quality: Optional[str] = None             # 画质：low_quality, medium_quality, high_quality, production_quality
    format: str = "mp4"                       # 输出格式：mp4, mov, gif等
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutputConfig':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    

# ==================== 视频元素配置 ====================

@dataclass
class VideoConfig:
    """
    统一的视频元素配置
    
    包括：相机、可视化元素、画幅等
    """
    # 相机配置
    phi: float = 75                      # 仰角 (0-180度)
    theta: float = 30                    # 方位角 (0-360度)
    gamma: float = 0                     # 滚转角 (0-360度)
    distance: Optional[float] = None     # 相机距离
    zoom: float = 1.0                    # 缩放倍数
    
    # 画幅配置
    frame_width: Optional[float] = None  # 帧宽度（场景单位）
    frame_height: Optional[float] = None # 帧高度（场景单位）
    
    # 可视化元素
    show_axes: bool = True               # 显示坐标轴
    show_axes_labels: bool = True        # 显示坐标轴标签
    show_rotation_axis: bool = True      # 显示旋转轴箭头
    show_rotation_circle: bool = False   # 显示旋转轨迹圆
    show_velocity_arrow: bool = False    # 显示速度向量
    show_labels: bool = False            # 显示各种标签
    show_bounding_box: bool = False      # 显示边界框
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VideoConfig':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
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

# ==================== 统一配置加载接口 ====================

def load_config_from_file(filepath: Union[str, Path]) -> Tuple[VoxelData, RotationParams, VideoConfig, CubeVisualConfig, OutputConfig]:
    """
    从文件加载所有配置
    
    Args:
        filepath: 配置文件路径（JSON格式）
        
    Returns:
        (voxel_data, rotation_params, video_config, visual_config, output_config)
    
    grid_size 说明：
    - grid_size = [x_max, y_max, z_max] 定义了3D网格的边界
    - 坐标范围：x ∈ [0, x_max), y ∈ [0, y_max), z ∈ [0, z_max)
    - 例如 grid_size=[5,5,5] 表示可以放置坐标在 (0-4, 0-4, 0-4) 范围内的方块
    - 超出范围的坐标会被忽略并显示警告
    """
    filepath = Path(filepath)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 1. 加载 Voxel 数据
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
        raise ValueError(f"未知的 voxel type: {voxel_type}")
    
    # 2. 加载旋转参数
    rotation_config = config.get("rotation", {})
    rotation_params = RotationParams.from_dict(rotation_config)
    
    # 3. 加载视频配置
    video_config_data = config.get("video", {})
    video_config = VideoConfig.from_dict(video_config_data)
    
    # 4. 加载立方体视觉配置（从 voxel.visual 或独立的 cube_visual）
    cube_visual_data = voxel_config.get("visual", config.get("cube_visual", {}))
    cube_visual_config = CubeVisualConfig.from_dict(cube_visual_data)
    
    # 5. 加载输出路径配置
    output_data = config.get("output", {})
    output_config = OutputConfig.from_dict(output_data)
    
    return voxel_data, rotation_params, video_config, cube_visual_config, output_config

# ==================== 函数定义 ====================

def calculate_duration_from_speed(rotation_angle: float, speed: RotationSpeed) -> float:
    """
    根据旋转角度和速度计算动画持续时间
    
    Args:
        rotation_angle: 旋转角度（弧度）
        speed: 旋转速度
        
    Returns:
        计算出的持续时间（秒）
    """
    config = ROTATION_SPEED_CONFIG[speed]
    base_duration = config["base_duration"]
    angle_factor = config["angle_factor"]
    
    # 线性映射：duration = base_duration * (angle_factor * angle_ratio)
    # angle_ratio = 当前角度 / 完整旋转角度(2π)
    angle_ratio = abs(rotation_angle) / (2 * np.pi)
    duration = base_duration * (angle_factor * angle_ratio + (1 - angle_factor))
    
    # 确保最小持续时间为0.5秒，最大持续时间为10秒
    duration = max(0.5, min(10.0, duration))
    
    return duration


def generate_filename(voxel_data, rotation_vector, rotation_angle, clockwise, rotation_speed=None):
    """
    生成基于日期的文件名
    格式：YYYY-MM-DD.mp4
    """
    from datetime import datetime
    
    # 使用当前日期和时间作为文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 生成文件名：日期时间.mp4
    filename = f"{timestamp}.mp4"
    
    return filename

class CubeStackRotation(ThreeDScene):
    """
    创建一个3D方块堆叠旋转动画类
    接受voxel数据、旋转向量、旋转角度和顺逆时针方向参数
    """
    
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
        """
        初始化方块堆叠旋转动画参数
        
        Args:
            voxel_data: 3D方块数据 [[[x,y,z], ...], ...]
            rotation_vector: 旋转轴向量 (x, y, z)
            rotation_angle: 旋转角度（弧度）
            clockwise: 是否顺时针旋转
            duration: 动画持续时间（秒），如果为None则根据rotation_speed自动计算
            rotation_speed: 旋转速度（SLOW/MEDIUM/FAST）
            voxel_offset: voxel数据的偏移量
        """
        super().__init__(**kwargs)
        
        # 转换为 VoxelData 对象
        if voxel_data is None:
            # 默认voxel数据（简单的L形）
            default_array = [
                [[1, 1, 1], [1, 1, 0], [1, 0, 0]],
                [[1, 1, 0], [1, 1, 0], [1, 0, 0]],
                [[1, 1, 0], [1, 1, 0], [1, 0, 0]]
            ]
            voxel_data = VoxelData.from_array(default_array)
        elif isinstance(voxel_data, list):
            # 如果是数组格式，转换为 VoxelData
            voxel_data = VoxelData.from_array(voxel_data)
        
        self.voxel_data_obj = voxel_data
        self.rotation_vector = np.array(rotation_vector)
        self.rotation_angle = rotation_angle
        self.clockwise = clockwise
        self.rotation_speed = rotation_speed
        self.voxel_offset = voxel_offset
        self.center_mode = center_mode
        
        # 保存配置
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
        
        # 标准化旋转向量
        self.rotation_vector = self.rotation_vector / np.linalg.norm(self.rotation_vector)
        
        # 根据顺时针/逆时针调整角度
        if clockwise:
            self.rotation_angle = -self.rotation_angle
        
        # 计算持续时间
        if duration is None:
            self.duration = calculate_duration_from_speed(abs(self.rotation_angle), rotation_speed)
        else:
            self.duration = duration
        
        # 创建voxel空间（使用传入的配置）
        self.voxel_space = VoxelSpace(voxel_data=self.voxel_data_obj, visual_config=self.cube_visual_config)
    
    def construct(self):
        """构建方块堆叠旋转动画场景"""
        # 应用画幅配置
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
            
            # 添加坐标轴标签
            if self.video_config.show_axes_labels:
                axes_labels = axes.get_axis_labels(x_label="X", y_label="Y", z_label="Z")
                self.add(axes_labels)
        
        # 获取所有方块（VoxelSpace 已自动加载）
        cubes = self.voxel_space.get_all_cubes()
        
        # 计算旋转中心
        if cubes:
            if self.center_mode == "cube":
                rotation_center = self.voxel_space.get_center_cube()
            else:
                rotation_center = self.voxel_space.get_center_of_mass()
            
            # 将所有方块平移，使旋转中心对齐到原点
            for cube in cubes:
                cube.shift(-rotation_center)
            
            self.add(*cubes)
        
        # 设置3D视角（使用video_config）
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
    # 使用输出配置
    if output_config is None:
        output_config = OutputConfig()
    
    # 转换角度为弧度
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
    
    # 设置媒体路径（使用绝对路径）
    config.media_dir = media_dir_abs  # 使用 media_dir 作为根目录
    config.video_dir = video_dir_abs  # 直接设置视频输出目录
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
    
    # 渲染视频
    scene.render()
    
    # 检查视频文件是否已生成（使用绝对路径）
    target_path = os.path.join(video_dir_abs, output_file)
    
    # 检查各种可能的路径（包括分辨率子目录）
    possible_paths = [
        target_path,
        os.path.join(media_dir_abs, "videos", "1080p60", output_file),
        os.path.join(media_dir_abs, "videos", "720p30", output_file),
        os.path.join(media_dir_abs, "videos", "480p15", output_file),
        os.path.join(media_dir_abs, "videos", "360p30", output_file),
        os.path.join(media_dir_abs, f"{output_file.replace('.mp4', '')}.mp4")
    ]
    
    actual_path = None
    for path in possible_paths:
        if os.path.exists(path):
            actual_path = path
            break
    
    if actual_path and actual_path != target_path:
        import shutil
        shutil.move(actual_path, target_path)
        print(f"✓ 方块堆叠旋转视频已保存为: {target_path}")
    elif os.path.exists(target_path):
        print(f"✓ 方块堆叠旋转视频已保存为: {target_path}")
    else:
        print(f"⚠ 视频文件未找到，请检查路径: {target_path}")
        print("可能的路径:")
        for path in possible_paths:
            print(f"  - {path}")
    
    # 保存meta文件（可选）
    if save_meta and os.path.exists(target_path):
        try:
            # 创建简化的meta记录
            # 处理 voxel_data（可能是 VoxelData 对象或数组）
            if isinstance(voxel_data, VoxelData):
                voxel_meta = {
                    "coordinates": voxel_data.coordinates,
                    "colors": {str(k): v for k, v in voxel_data.colors.items()},  # 转换 tuple 为 str
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
            
            # 保存到meta目录，使用时间戳命名
            from datetime import datetime
            
            # 生成带时间戳的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            meta_file = os.path.join(meta_dir_abs, f"meta_{timestamp}.json")
            
            # 直接保存单个配置（不追加到数组）
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ 参数已保存到: {meta_file}")
        except Exception as e:
            print(f"⚠ 保存meta文件失败: {e}")
    
    return target_path

def create_video_from_config(config_file: Union[str, Path], save_meta: bool = True) -> str:
    """
    从配置文件创建视频（统一接口）
    
    Args:
        config_file: 配置文件路径
        save_meta: 是否保存meta文件
        
    Returns:
        视频文件路径
    """
    print(f"\n从配置文件加载: {config_file}")
    
    # 加载配置
    voxel_data, rotation_params, video_config, cube_visual_config, output_config = load_config_from_file(config_file)
    
    print(f"  Voxel: {len(voxel_data.coordinates)} 个方块")
    if voxel_data.colors:
        print(f"  颜色: {len(voxel_data.colors)} 个彩色方块")
    print(f"  旋转: {rotation_params.rotation_vector} @ {rotation_params.rotation_angle}°")
    print(f"  视频: phi={video_config.phi}°, theta={video_config.theta}°")
    print(f"  输出: {output_config.video_dir}")
    
    # 创建视频（传递所有配置，保留 VoxelData 对象以保留颜色信息）
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
    批量渲染文件夹中的所有配置文件
    
    Args:
        batch_folder: 批量配置文件夹路径
        
    Returns:
        渲染结果列表
    """
    batch_folder = Path(batch_folder)
    
    if not batch_folder.exists():
        raise FileNotFoundError(f"批量文件夹不存在: {batch_folder}")
    
    # 获取所有配置文件
    config_files = sorted(batch_folder.glob("batch_*.json"))
    
    if not config_files:
        print(f"⚠ 未找到配置文件在: {batch_folder}")
        return []
    
    print("=" * 80)
    print(f"批量渲染: {batch_folder.name}")
    print("=" * 80)
    print(f"找到 {len(config_files)} 个配置文件\n")
    
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
            print(f"✓ 完成: {result}")
        except Exception as e:
            print(f"✗ 失败: {e}")
            results.append({
                "index": idx,
                "config": str(config_file),
                "error": str(e),
                "status": "failed"
            })
    
    # 统计结果
    success_count = sum(1 for r in results if r["status"] == "success")
    print("\n" + "=" * 80)
    print(f"批量渲染完成:")
    print(f"  成功: {success_count}/{len(config_files)}")
    print(f"  失败: {len(config_files) - success_count}/{len(config_files)}")
    print("=" * 80)
    
    return results

if __name__ == "__main__":
    import sys
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 批量渲染模式
        batch_folder = sys.argv[1]
        
        # 支持相对路径和绝对路径
        if not os.path.isabs(batch_folder):
            batch_folder = os.path.join(script_dir, batch_folder)
        
        results = render_batch_folder(batch_folder)
    else:
        # 单个配置文件模式
        print("=" * 80)
        print("MRT-CubeStack: 从配置文件生成旋转动画")
        print("=" * 80)
        
        print("\n【示例】从配置文件生成视频")
        config_file = os.path.join(script_dir, "example_colorful_config.json")
        
        if Path(config_file).exists():
            result = create_video_from_config(config_file)
            print(f"\n✓ 已保存: {result}")
        else:
            print(f"⚠ 配置文件不存在: {config_file}")
            print("  请先创建配置文件，参考 example_config.json 格式")
            
            # 使用默认参数生成
            print("\n使用默认参数生成...")
            # 创建默认的L形方块数据
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
            print(f"✓ 已保存: {result}")