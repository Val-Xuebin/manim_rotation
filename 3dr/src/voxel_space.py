#!/usr/bin/env python3
"""
Voxel space and data types for 3D cube stacks.

Provides: unified voxel input (coordinates, array, file, colored), visual config
(cube size, stroke, style), and output suitable for Manim (VoxelSpace -> cubes).
"""

from __future__ import annotations

import numpy as np
from typing import List, Tuple, Dict, Any, Optional, Union
from manim import *
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ==================== Voxel data ====================

@dataclass
class VoxelData:
    """Unified voxel format: coordinates, grid_size, optional per-cube colors."""
    coordinates: List[Tuple[int, int, int]] = field(default_factory=list)
    grid_size: Tuple[int, int, int] = (10, 10, 10)
    colors: Dict[Tuple[int, int, int], str] = field(default_factory=dict)

    @classmethod
    def from_coordinates(cls, coords: Union[List[Tuple[int, int, int]], List[Dict[str, Any]]],
                        grid_size: Tuple[int, int, int] = (10, 10, 10)) -> 'VoxelData':
        """Build from coordinate list: [(x,y,z), ...] or [{"pos": [x,y,z], "color": "BLUE"}, ...]."""
        coordinates = []
        colors = {}
        
        for item in coords:
            if isinstance(item, dict):
                # 带颜色的格式
                pos = tuple(item["pos"])
                coordinates.append(pos)
                if "color" in item:
                    colors[pos] = item["color"]
            else:
                # 简单坐标格式
                coordinates.append(tuple(item))
        
        return cls(coordinates=coordinates, grid_size=grid_size, colors=colors)
    
    @classmethod
    def from_array(cls, array: List[List[List[int]]],
                   grid_size: Optional[Tuple[int, int, int]] = None) -> 'VoxelData':
        """Build from 3D array; non-zero cells become coordinates."""
        coords = []
        for x, layer in enumerate(array):
            for y, row in enumerate(layer):
                for z, value in enumerate(row):
                    if value != 0:
                        coords.append((x, y, z))
        
        if grid_size is None:
            grid_size = (len(array), 
                        len(array[0]) if array else 0,
                        len(array[0][0]) if array and array[0] else 0)
        
        return cls(coordinates=coords, grid_size=grid_size)
    
    
    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> 'VoxelData':
        """从文件加载"""
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"文件不存在: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 支持多种文件格式
        if "coordinates" in data:
            coords = [tuple(c) for c in data["coordinates"]]
            grid_size = tuple(data.get("grid_size", (10, 10, 10)))
            return cls(coordinates=coords, grid_size=grid_size)
        elif "array" in data:
            return cls.from_array(data["array"], 
                                 tuple(data.get("grid_size", None)))
        elif "template" in data:
            return cls.from_template(data["template"])
        else:
            raise ValueError("文件格式不支持，需要包含 'coordinates', 'array' 字段")
    
    def to_array(self) -> List[List[List[int]]]:
        """转换为3D数组格式"""
        array = np.zeros(self.grid_size, dtype=int)
        for x, y, z in self.coordinates:
            if 0 <= x < self.grid_size[0] and \
               0 <= y < self.grid_size[1] and \
               0 <= z < self.grid_size[2]:
                array[x, y, z] = 1
        return array.tolist()
    
    def to_file(self, filepath: Union[str, Path]) -> None:
        """保存到文件"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "coordinates": self.coordinates,
            "grid_size": self.grid_size,
            "array": self.to_array()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ==================== 2. 视觉元素配置接口 ====================

@dataclass
class CubeVisualConfig:
    """
    立方体视觉元素配置
    
    控制方块的外观：大小、颜色、边框等
    """
    cube_size: float = 0.25                    # 方块尺寸
    spacing: float = 0.0                       # 方块间距
    fill_color: ManimColor = BLUE             # 填充颜色
    fill_opacity: float = 0.8                  # 填充透明度
    stroke_color: ManimColor = WHITE          # 边框颜色
    stroke_width: float = 1.0                  # 边框宽度
    stroke_opacity: float = 1.0                # 边框透明度
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "cube_size": self.cube_size,
            "spacing": self.spacing,
            "fill_color": str(self.fill_color),
            "fill_opacity": self.fill_opacity,
            "stroke_color": str(self.stroke_color),
            "stroke_width": self.stroke_width,
            "stroke_opacity": self.stroke_opacity
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CubeVisualConfig':
        """从字典创建"""
        # 处理颜色字符串
        config = cls()
        for key, value in data.items():
            if key in ['fill_color', 'stroke_color']:
                # 从字符串解析颜色
                if isinstance(value, str):
                    color_map = {
                        "BLUE": BLUE, "RED": RED, "GREEN": GREEN, "YELLOW": YELLOW,
                        "ORANGE": ORANGE, "PINK": PINK, "PURPLE": PURPLE, "GRAY": GRAY, "WHITE": WHITE, "BLACK": BLACK
                    }
                    setattr(config, key, color_map.get(value, BLUE))
                else:
                    setattr(config, key, value)
            else:
                setattr(config, key, value)
        return config
    

# ==================== 3. Voxel 空间类（输出接口）====================

class VoxelSpace:
    """
    Voxel空间类，管理3D网格中的方块
    
    提供 Manim Animation 可直接使用的输出接口
    """
    
    def __init__(self, 
                 voxel_data: Optional[VoxelData] = None,
                 visual_config: Optional[CubeVisualConfig] = None):
        """
        初始化Voxel空间
        
        Args:
            voxel_data: VoxelData 对象（统一输入接口）
            visual_config: CubeVisualConfig 对象（视觉配置）
        """
        # 使用新的接口
        if voxel_data is None:
            voxel_data = VoxelData.from_template("l_shape")
        
        if visual_config is None:
            visual_config = CubeVisualConfig()
        
        self.voxel_data = voxel_data
        self.visual_config = visual_config
        
        # 兼容旧接口
        self.size = voxel_data.grid_size
        self.cube_size = visual_config.cube_size
        self.spacing = visual_config.spacing
        
        # 初始化3D网格
        self.grid = np.zeros(self.size, dtype=int)
        
        # 存储方块对象
        self.cubes = {}  # {(x,y,z): cube_object}
        
        # 方块样式配置（兼容旧接口）
        self.cube_style = {
            "fill_color": visual_config.fill_color,
            "fill_opacity": visual_config.fill_opacity,
            "stroke_color": visual_config.stroke_color,
            "stroke_width": visual_config.stroke_width,
            "stroke_opacity": visual_config.stroke_opacity
        }
        
        # 自动添加 voxel 数据
        self._load_voxel_data()
    
    def _load_voxel_data(self) -> None:
        """从 VoxelData 加载方块（支持不同颜色）"""
        # 颜色字符串到 Manim 颜色的映射
        color_map = {
            "BLUE": BLUE,
            "RED": RED,
            "GREEN": GREEN,
            "YELLOW": YELLOW,
            "ORANGE": ORANGE,
            "PINK": PINK,
            "PURPLE": PURPLE,
            "GRAY": GRAY,
            "WHITE": WHITE,
            "BLACK": BLACK,
        }
        
        for coord in self.voxel_data.coordinates:
            # 检查是否有自定义颜色
            if coord in self.voxel_data.colors:
                color_name = self.voxel_data.colors[coord]
                custom_style = self.cube_style.copy()
                custom_style["fill_color"] = color_map.get(color_name, self.cube_style["fill_color"])
                self.add_cube(coord, custom_style)
            else:
                self.add_cube(coord)
    
    def add_cube(self, position: Tuple[int, int, int], 
                style: Optional[Dict[str, Any]] = None) -> bool:
        """
        在指定位置添加方块
        
        Args:
            position: 位置坐标 (x, y, z)
            style: 方块样式，如果为None则使用默认样式
            
        Returns:
            bool: 是否成功添加
        """
        x, y, z = position
        
        # 检查位置是否有效
        if not self._is_valid_position(position):
            return False
        
        # 检查位置是否已被占用
        if self.grid[x, y, z] == 1:
            return False
        
        # 在网格中标记
        self.grid[x, y, z] = 1
        
        # 创建方块对象
        cube_style = style if style else self.cube_style.copy()
        cube = Cube(
            side_length=self.cube_size,
            fill_color=cube_style.get("fill_color", BLUE),
            fill_opacity=cube_style.get("fill_opacity", 0.8),
            stroke_color=cube_style.get("stroke_color", WHITE),
            stroke_width=cube_style.get("stroke_width", 1),
            stroke_opacity=cube_style.get("stroke_opacity", 1.0)
        )
        
        # 计算世界坐标
        world_pos = self._grid_to_world(position)
        cube.move_to(world_pos)
        
        # 存储方块对象
        self.cubes[position] = cube
        
        return True
    
    def remove_cube(self, position: Tuple[int, int, int]) -> bool:
        """
        移除指定位置的方块
        
        Args:
            position: 位置坐标 (x, y, z)
            
        Returns:
            bool: 是否成功移除
        """
        if not self._is_valid_position(position):
            return False
        
        if self.grid[position] == 0:
            return False
        
        # 从网格中移除标记
        self.grid[position] = 0
        
        # 从存储中移除方块对象
        if position in self.cubes:
            del self.cubes[position]
        
        return True
    
    def add_cube_stack(self, data: List[List[List[int]]], 
                      offset: Tuple[int, int, int] = (0, 0, 0),
                      style_map: Optional[Dict[int, Dict[str, Any]]] = None):
        """
        批量添加方块堆叠
        
        Args:
            data: 3D数组，1表示有方块，0表示空
            offset: 偏移量 (x, y, z)
            style_map: 不同值的样式映射 {value: style_dict}
        """
        for z, layer in enumerate(data):
            for y, row in enumerate(layer):
                for x, value in enumerate(row):
                    if value != 0:  # 非零值表示有方块
                        pos = (x + offset[0], y + offset[1], z + offset[2])
                        
                        # 获取样式
                        style = None
                        if style_map and value in style_map:
                            style = style_map[value]
                        
                        self.add_cube(pos, style)
    
    def get_all_cubes(self) -> List[Cube]:
        """
        获取所有方块对象
        
        Returns:
            List[Cube]: 所有方块对象的列表
        """
        return list(self.cubes.values())
    
    def get_cube_positions(self) -> List[Tuple[int, int, int]]:
        """
        获取所有方块的位置
        
        Returns:
            List[Tuple[int, int, int]]: 所有方块位置的列表
        """
        return list(self.cubes.keys())
    
    def get_center_of_mass(self) -> np.ndarray:
        """
        计算方块堆叠的质心（所有方块位置的平均值）
        
        Returns:
            np.ndarray: 质心坐标
        """
        if not self.cubes:
            return np.array([0.0, 0.0, 0.0])
        
        positions = np.array(list(self.cubes.keys()), dtype=float)
        center = np.mean(positions, axis=0)
        return self._grid_to_world(center)
    
    def get_center_cube(self) -> np.ndarray:
        """
        找到最中心的方块，并返回其世界坐标
        
        逻辑：
        1. 计算所有方块的几何中心（平均位置）
        2. 找到距离几何中心最近的方块
        3. 返回该方块的世界坐标作为旋转中心
        
        Returns:
            np.ndarray: 最中心方块的世界坐标
        """
        if not self.cubes:
            return np.array([0.0, 0.0, 0.0])
        
        # 计算几何中心（网格坐标）
        positions = np.array(list(self.cubes.keys()), dtype=float)
        geometric_center = np.mean(positions, axis=0)
        
        # 找到距离几何中心最近的方块
        min_distance = float('inf')
        center_cube_pos = positions[0]
        
        for pos in positions:
            distance = np.linalg.norm(pos - geometric_center)
            if distance < min_distance:
                min_distance = distance
                center_cube_pos = pos
        
        # 转换为世界坐标
        return self._grid_to_world(center_cube_pos)
    
    def get_bounding_box(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        获取方块堆叠的边界框
        
        Returns:
            Tuple[np.ndarray, np.ndarray]: (最小坐标, 最大坐标)
        """
        if not self.cubes:
            return np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0])
        
        positions = np.array(list(self.cubes.keys()), dtype=float)
        min_pos = np.min(positions, axis=0)
        max_pos = np.max(positions, axis=0)
        
        return self._grid_to_world(min_pos), self._grid_to_world(max_pos)
    
    def _is_valid_position(self, position: Tuple[int, int, int]) -> bool:
        """检查位置是否在有效范围内"""
        x, y, z = position
        return (0 <= x < self.size[0] and 
                0 <= y < self.size[1] and 
                0 <= z < self.size[2])
    
    def _grid_to_world(self, grid_pos: np.ndarray) -> np.ndarray:
        """将网格坐标转换为世界坐标"""
        step = self.cube_size + self.spacing
        center_offset = np.array(self.size, dtype=float) * step / 2
        
        # 确保grid_pos是numpy数组
        grid_pos = np.array(grid_pos, dtype=float)
        world_pos = grid_pos * step - center_offset
        return world_pos
    
    def clear(self) -> None:
        """清空所有方块"""
        self.grid.fill(0)
        self.cubes.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取方块堆叠统计信息"""
        total_cubes = len(self.cubes)
        occupied_positions = np.sum(self.grid)
        
        return {
            "total_cubes": total_cubes,
            "occupied_positions": occupied_positions,
            "grid_size": self.size,
            "cube_size": self.cube_size,
            "spacing": self.spacing,
            "center_of_mass": self.get_center_of_mass().tolist(),
            "bounding_box": {
                "min": self.get_bounding_box()[0].tolist(),
                "max": self.get_bounding_box()[1].tolist()
            }
        }
    
    def export_data(self) -> Dict[str, Any]:
        """导出方块数据"""
        # 获取所有方块位置
        positions = []
        for pos in self.cubes.keys():
            positions.append(list(pos))
        
        return {
            "grid_size": list(self.size),
            "cube_size": self.cube_size,
            "spacing": self.spacing,
            "cube_positions": positions,
            "cube_style": self.cube_style,
            "stats": self.get_stats()
        }
    
    def import_data(self, data: Dict[str, Any]) -> bool:
        """导入方块数据"""
        try:
            # 清空当前数据
            self.clear()
            
            # 设置基本参数
            if "grid_size" in data:
                self.size = tuple(data["grid_size"])
                self.grid = np.zeros(self.size, dtype=int)
            
            if "cube_size" in data:
                self.cube_size = data["cube_size"]
            
            if "spacing" in data:
                self.spacing = data["spacing"]
            
            if "cube_style" in data:
                self.cube_style.update(data["cube_style"])
            
            # 添加方块
            if "cube_positions" in data:
                for pos in data["cube_positions"]:
                    self.add_cube(tuple(pos))
            
            return True
            
        except Exception as e:
            print(f"导入数据失败: {e}")
            return False