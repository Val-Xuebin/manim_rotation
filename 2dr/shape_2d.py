#!/usr/bin/env python3
"""
2D图形数据定义模块
生成JSON配置数据供渲染使用
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import random
import json
import os
import math
from datetime import datetime


# ============================================================================
# 参数配置 - 所有采样范围集中在这里（按层次组织）
# ============================================================================

BATCH_SIZE = 5
# ========== 1. 网格尺寸配置 ==========
GRID_SIZE_RANGE = (2, 3)  # 支持的网格尺寸：2x2, 3x3, 4x4
GRID_SCALE_RANGE = (0.5, 0.8)  # 整体网格占画幅比例：50%-80%
FRAME_HEIGHT = 8.0  # Manim默认画幅高度

# Pattern最小1的数量（针对color模式）
PATTERN_MIN_ONES = {
    1: 1,  # 1x1网格至少1个
    2: 3,  # 2x2网格至少3个
    3: 3,   # 3x3网格至少3个
    4: 4
}

# ========== 2. 颜色配置 ==========
COLOR_POOL = ["BLUE", "RED", "GREEN", "ORANGE", "PINK", "PURPLE", "GRAY", "YELLOW"]
GRID_COLOR_POOL = ["BLACK", "WHITE", "GRAY"]  # 网格颜色：黑、白、灰

# ========== 3. 纹理配置 ==========
TEXTURE_TYPE_POOL = ["line", "polygon"]  # 纹理类型（line, polygon）
LINE_DIRECTION_POOL = ["vertical", "horizontal", "left_slash", "right_slash"]  # 线条方向
POLYGON_SHAPE_POOL = ["square", "circle", "diamond"]  # 多边形形状
TEXTURE_OPACITY_RANGE = (0.85, 1.0)  # 纹理透明度范围（较不透明）
TEXTURE_COLOR_MODE = "grid"  # 选项："cell"使用cell颜色，"random"随机颜色，"grid"黑白灰

# ========== 4. 样式参数配置 ==========
FILL_OPACITY_RANGE = (0.6, 1.0)  # 填充透明度范围
STROKE_WIDTH_RANGE = (1.5, 3.0)  # 边框宽度范围
STROKE_COLOR_MODE = "grid"  # 边框颜色模式："white"固定白色，"grid"从GRID_COLOR_POOL选

# ========== 5. 模式配置 ==========
SHOW_GRID_OPTIONS = [True]  # 是否显示边线 True or False

# ========== 6. Rotation配置 ==========
ROTATION_ANGLES_RANGE = (90, 90)  # 旋转角度范围（度）
CLOCKWISE_OPTIONS = [True, False]  # 顺时针/逆时针
ROTATION_SPEED_OPTIONS = ["fast", "medium"]  # 旋转速度
ROTATION_SPEED_FACTOR = {
    "fast": 0.016,    # 快速：每秒转60度 (1/60 = 0.016)
    "medium": 0.022,  # 中等：每秒转45度 (1/45 = 0.022)
    "slow": 0.033      # 慢速：每秒转30度 (1/20 = 0.05)
}

# ========== 7. Video配置 ==========
BACKGROUND_COLORS = ["#1a1a2e", "#000000"]  # 背景色：深蓝、黑色


# ==================== 样式类型枚举 ====================

class StyleType(Enum):
    """样式类型枚举"""
    COLOR = "color"           # 纯色填充
    TEXTURE = "texture"       # 纹理填充


class TextureType(Enum):
    """纹理类型枚举"""
    LINE = "line"             # 线条
    POLYGON = "polygon"       # 多边形（包括triangle, square, circle, star）

class LineDirection(Enum):
    """线条方向枚举"""
    VERTICAL = "vertical"      # 垂直
    HORIZONTAL = "horizontal" # 水平
    LEFT_SLASH = "left_slash"  # 左斜
    RIGHT_SLASH = "right_slash" # 右斜


class PolygonShape(Enum):
    """多边形形状枚举"""
    TRIANGLE = "triangle"      # 三角形 (n=3)
    SQUARE = "square"           # 正方形 (n=4)
    CIRCLE = "circle"           # 圆形 (Circle)
    DIAMOND = "diamond"         # 菱形


# ==================== 网格单元样式配置 ====================

@dataclass
class GridCellStyle:
    """网格单元样式配置"""
    style_type: StyleType = StyleType.COLOR
    
    # color样式
    color: str = "BLUE"
    
    # texture样式
    texture_type: Optional[TextureType] = None
    line_direction: Optional[LineDirection] = None  # 当texture_type=line时使用
    polygon_shape: Optional[PolygonShape] = None  # 当texture_type=polygon时使用
    
    # 视觉参数（从顶部参数配置导入）
    fill_opacity: float = 0.8  # 默认值，可在生成时随机化
    stroke_width: float = 2.0  # 默认值，可在生成时随机化
    stroke_color: str = "WHITE"
    
    # texture专用参数
    texture_opacity: float = 1.0  # 纹理透明度（0-1）
    texture_color: Optional[str] = None  # 纹理颜色，None表示使用cell颜色
    
    def __post_init__(self):
        """初始化后处理"""
        if self.style_type == StyleType.TEXTURE:
            if self.texture_type == TextureType.LINE and self.line_direction is None:
                self.line_direction = LineDirection.VERTICAL
            if self.texture_type == TextureType.POLYGON and self.polygon_shape is None:
                self.polygon_shape = PolygonShape.TRIANGLE
    
    @classmethod
    def random_style(cls) -> 'GridCellStyle':
        """随机生成样式"""
        style_type = random.choice(list(StyleType))
        
        if style_type == StyleType.COLOR:
            return cls(
                style_type=style_type,
                color=random.choice(COLOR_POOL)
            )
        else:  # TEXTURE
            texture = random.choice(TEXTURE_TYPE_POOL)
            texture_type = TextureType(texture)
            
            # 生成texture颜色和透明度
            if TEXTURE_COLOR_MODE == "random":
                texture_color_val = random.choice(COLOR_POOL)
            elif TEXTURE_COLOR_MODE == "grid":
                texture_color_val = random.choice(GRID_COLOR_POOL)
            else:  # "cell"
                texture_color_val = None  # 使用cell颜色
            
            texture_opacity_val = random.uniform(*TEXTURE_OPACITY_RANGE)
            
            if texture_type == TextureType.LINE:
                direction = random.choice(LINE_DIRECTION_POOL)
                return cls(
                    style_type=style_type,
                    texture_type=TextureType.LINE,
                    line_direction=LineDirection(direction),
                    color=random.choice(COLOR_POOL),
                    texture_opacity=texture_opacity_val,
                    texture_color=texture_color_val
                )
            else:  # POLYGON
                shape = random.choice(POLYGON_SHAPE_POOL)
                return cls(
                    style_type=style_type,
                    texture_type=TextureType.POLYGON,
                    polygon_shape=PolygonShape(shape),
                    color=random.choice(COLOR_POOL),
                    texture_opacity=texture_opacity_val,
                    texture_color=texture_color_val
                )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "style_type": self.style_type.value,
            "color": self.color,
            "fill_opacity": self.fill_opacity,
            "stroke_width": self.stroke_width,
            "stroke_color": self.stroke_color
        }
        
        if self.style_type == StyleType.TEXTURE:
            result["texture_type"] = self.texture_type.value
            if self.line_direction:
                result["line_direction"] = self.line_direction.value
            if self.polygon_shape:
                result["polygon_shape"] = self.polygon_shape.value
            # 添加texture专用参数
            result["texture_opacity"] = self.texture_opacity
            if self.texture_color:
                result["texture_color"] = self.texture_color
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GridCellStyle':
        """从字典创建"""
        style_type = StyleType(data.get("style_type", "color"))
        
        result = cls(
            style_type=style_type,
            color=data.get("color", "BLUE"),
            fill_opacity=data.get("fill_opacity", 0.8),
            stroke_width=data.get("stroke_width", 2.0),
            stroke_color=data.get("stroke_color", "WHITE"),
            texture_opacity=data.get("texture_opacity", 1.0),
            texture_color=data.get("texture_color", None)
        )
        
        if style_type == StyleType.TEXTURE:
            texture_type = data.get("texture_type", "polygon")
            result.texture_type = TextureType(texture_type)
            
            if "line_direction" in data:
                result.line_direction = LineDirection(data["line_direction"])
            if "polygon_shape" in data:
                result.polygon_shape = PolygonShape(data["polygon_shape"])
        
        return result


# ==================== Pattern生成辅助函数 ====================

def count_ones_in_pattern(pattern: List[List[int]]) -> int:
    """统计pattern中1的数量"""
    return sum(sum(row) for row in pattern)


def is_connected_pattern(pattern: List[List[int]]) -> bool:
    """检查pattern是否连通（DFS）"""
    rows, cols = len(pattern), len(pattern[0])
    
    # 找到所有1的位置
    ones = []
    for i in range(rows):
        for j in range(cols):
            if pattern[i][j] == 1:
                ones.append((i, j))
    
    if not ones:
        return False
    
    # 从第一个1开始DFS
    visited = set()
    stack = [ones[0]]
    
    while stack:
        r, c = stack.pop()
        if (r, c) in visited:
            continue
        visited.add((r, c))
        
        # 检查相邻的1
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if pattern[nr][nc] == 1 and (nr, nc) not in visited:
                    stack.append((nr, nc))
    
    return len(visited) == len(ones)


def generate_horizontal_mirror(pattern: List[List[int]]) -> List[List[int]]:
    """生成水平镜像（上下镜像）"""
    return pattern[::-1]


def generate_vertical_mirror(pattern: List[List[int]]) -> List[List[int]]:
    """生成垂直镜像（左右镜像）"""
    return [row[::-1] for row in pattern]


def generate_horizontal_mirror_with_styles(pattern: List[List[int]], cell_colors: List[Dict[str, Any]]) -> Tuple[List[List[int]], List[Dict[str, Any]]]:
    """生成水平镜像（上下镜像）- 同时镜像pattern和cell_colors"""
    rows = len(pattern)
    cols = len(pattern[0]) if pattern else 0
    mirrored_pattern = pattern[::-1]
    
    # 创建位置映射：原pattern的(i,j)对应镜像后的(rows-1-i,j)
    # 同时翻转cell_colors的顺序
    mirrored_colors = []
    
    # 按镜像后的pattern遍历，找到对应的原cell_colors
    color_map = {}
    color_idx = 0
    for i in range(rows):
        for j in range(cols):
            if pattern[i][j] == 1:
                color_map[(i, j)] = cell_colors[color_idx]
                color_idx += 1
    
    # 按镜像后的pattern顺序重建colors
    for i in range(rows):
        for j in range(cols):
            if mirrored_pattern[i][j] == 1:
                orig_i = rows - 1 - i  # 反转到原位置
                orig_j = j
                mirrored_colors.append(color_map[(orig_i, orig_j)])
    
    return mirrored_pattern, mirrored_colors


def generate_vertical_mirror_with_styles(pattern: List[List[int]], cell_colors: List[Dict[str, Any]]) -> Tuple[List[List[int]], List[Dict[str, Any]]]:
    """生成垂直镜像（左右镜像）- 同时镜像pattern和cell_colors"""
    rows = len(pattern)
    cols = len(pattern[0]) if pattern else 0
    mirrored_pattern = [row[::-1] for row in pattern]
    
    # 创建位置映射：原pattern的(i,j)对应镜像后的(i, cols-1-j)
    # 同时翻转cell_colors的顺序
    mirrored_colors = []
    
    # 按镜像后的pattern遍历，找到对应的原cell_colors
    color_map = {}
    color_idx = 0
    for i in range(rows):
        for j in range(cols):
            if pattern[i][j] == 1:
                color_map[(i, j)] = cell_colors[color_idx]
                color_idx += 1
    
    # 按镜像后的pattern顺序重建colors
    for i in range(rows):
        for j in range(cols):
            if mirrored_pattern[i][j] == 1:
                orig_i = i
                orig_j = cols - 1 - j  # 反转到原位置
                mirrored_colors.append(color_map[(orig_i, orig_j)])
    
    return mirrored_pattern, mirrored_colors


def add_cell_to_pattern(pattern: List[List[int]], rows: int, cols: int) -> List[List[int]]:
    """添加一个连通cell到pattern（不能超出原pattern的行列范围）"""
    
    # 找到所有1的位置
    ones = [(i, j) for i in range(rows) for j in range(cols) if pattern[i][j] == 1]
    
    if not ones:
        return pattern
    
    # 找到所有0的相邻位置
    zeros = []
    for r, c in ones:
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and pattern[nr][nc] == 0:
                if (nr, nc) not in zeros:
                    zeros.append((nr, nc))
    
    if zeros:
        r, c = random.choice(zeros)
        new_pattern = [row[:] for row in pattern]
        new_pattern[r][c] = 1
        return new_pattern
    
    return pattern


def swap_cells_with_different_styles(pattern: List[List[int]], cell_colors: List[Dict[str, Any]]) -> List[List[int]]:
    """交换cells，但只交换style不同的cells"""
    rows = len(pattern)
    cols = len(pattern[0]) if pattern else 0
    
    # 找到所有1的位置及其样式
    ones_positions = []
    color_idx = 0
    for i in range(rows):
        for j in range(cols):
            if pattern[i][j] == 1:
                ones_positions.append({
                    "pos": (i, j),
                    "style": cell_colors[color_idx] if color_idx < len(cell_colors) else cell_colors[-1]
                })
                color_idx += 1
    
    # 找到所有0的位置
    zeros_positions = [(i, j) for i in range(rows) for j in range(cols) if pattern[i][j] == 0]
    
    if len(ones_positions) == 0 or len(zeros_positions) == 0:
        return pattern
    
    # 找到style不同的cell对
    different_style_pairs = []
    for i in range(len(ones_positions)):
        for j in range(i + 1, len(ones_positions)):
            style1 = ones_positions[i]["style"]
            style2 = ones_positions[j]["style"]
            if style1 != style2:
                different_style_pairs.append((i, j))
    
    # 如果找到不同的style，随机选择一个进行交换
    if different_style_pairs:
        idx1, idx2 = random.choice(different_style_pairs)
        pos1 = ones_positions[idx1]["pos"]
        pos2 = ones_positions[idx2]["pos"]
        
        new_pattern = [row[:] for row in pattern]
        new_pattern[pos1[0]][pos1[1]] = 0
        new_pattern[pos2[0]][pos2[1]] = 1
        
        return new_pattern
    
    return pattern


def remove_cell_from_pattern(pattern: List[List[int]]) -> List[List[int]]:
    """从pattern中删除一个cell（保证连通性）"""
    size = len(pattern)
    
    # 找到所有1的位置
    ones = [(i, j) for i in range(size) for j in range(size) if pattern[i][j] == 1]
    
    if len(ones) <= 1:
        return pattern
    
    # 尝试删除一个cell，检查连通性
    for r, c in random.sample(ones, min(len(ones), 10)):
        new_pattern = [row[:] for row in pattern]
        new_pattern[r][c] = 0
        
        # 检查是否连通
        if is_connected_pattern(new_pattern):
            return new_pattern
    
    return pattern


def swap_cells_in_pattern(pattern: List[List[int]]) -> List[List[int]]:
    """随机交换两个cells（保持1的总数不变）"""
    size = len(pattern)
    
    # 找到所有1的位置
    ones = [(i, j) for i in range(size) for j in range(size) if pattern[i][j] == 1]
    # 找到所有0的位置
    zeros = [(i, j) for i in range(size) for j in range(size) if pattern[i][j] == 0]
    
    if len(ones) == 0 or len(zeros) == 0:
        return pattern
    
    # 随机选择一个1和一个0，交换它们
    r1, c1 = random.choice(ones)
    r0, c0 = random.choice(zeros)
    
    new_pattern = [row[:] for row in pattern]
    new_pattern[r1][c1] = 0
    new_pattern[r0][c0] = 1
    
    # 检查连通性
    if is_connected_pattern(new_pattern):
        return new_pattern
    
    return pattern


def is_symmetric_pattern(pattern: List[List[int]]) -> bool:
    """检查pattern是否对称（水平、垂直、或都对称）
    Args:
        pattern: 网格pattern
    Returns:
        True如果pattern有任何对称性
    """
    size = len(pattern)
    
    # 检查水平对称（上下镜像）
    horizontal_sym = True
    for i in range(size):
        for j in range(size):
            if pattern[i][j] != pattern[size-1-i][j]:
                horizontal_sym = False
                break
        if not horizontal_sym:
            break
    
    # 检查垂直对称（左右镜像）
    vertical_sym = True
    for i in range(size):
        for j in range(size):
            if pattern[i][j] != pattern[i][size-1-j]:
                vertical_sym = False
                break
        if not vertical_sym:
            break
    
    return horizontal_sym or vertical_sym


def generate_random_pattern(size: int, min_ones: int) -> List[List[int]]:
    """生成随机的连通pattern（非对称）
    Args:
        size: 网格尺寸
        min_ones: 最少1的数量
    """
    total_cells = size * size
    
    # 随机确定1的数量（在min_ones和total_cells之间）
    num_ones = random.randint(min_ones, total_cells)
    
    # 生成所有位置
    all_positions = [(i, j) for i in range(size) for j in range(size)]
    
    max_attempts = 500  # 增加尝试次数以保证生成非对称pattern
    for attempt in range(max_attempts):
        # 随机选择num_ones个位置
        selected = random.sample(all_positions, num_ones)
        
        # 创建pattern
        pattern = [[0 for _ in range(size)] for _ in range(size)]
        for r, c in selected:
            pattern[r][c] = 1
        
        # 检查连通性和非对称性
        if is_connected_pattern(pattern) and not is_symmetric_pattern(pattern):
            return pattern
    
    # 如果无法生成非对称连通的，生成连通的（允许对称）
    for attempt in range(100):
        selected = random.sample(all_positions, num_ones)
        pattern = [[0 for _ in range(size)] for _ in range(size)]
        for r, c in selected:
            pattern[r][c] = 1
        if is_connected_pattern(pattern):
            return pattern
    
    # 最后返回全1
    return [[1 for _ in range(size)] for _ in range(size)]


@dataclass
class GridStyle:
    """网格样式配置"""
    rows: int = 2
    cols: int = 2
    cell_size: float = 1.0
    pattern: Optional[List[List[int]]] = None  # 0/1矩阵，None表示全1（完整网格）
    cell_styles: List[GridCellStyle] = None
    show_grid: bool = True  # 是否显示边线
    
    def __post_init__(self):
        """初始化后处理"""
        # 如果pattern为None，生成全1矩阵（完整网格）
        if self.pattern is None:
            self.pattern = [[1 for _ in range(self.cols)] for _ in range(self.rows)]
        
        # 确保pattern尺寸与rows/cols一致
        if len(self.pattern) != self.rows:
            raise ValueError(f"pattern行数({len(self.pattern)})与rows({self.rows})不一致")
        if len(self.pattern[0]) != self.cols:
            raise ValueError(f"pattern列数({len(self.pattern[0])})与cols({self.cols})不一致")
        
        if self.cell_styles is None:
            # 统计需要样式的单元格数量（pattern中为1的位置）
            total_cells = sum(sum(row) for row in self.pattern)
            self.cell_styles = [GridCellStyle.random_style() for _ in range(total_cells)]
    
    @classmethod
    def generate_random(cls, grid_size_range: Tuple[int, int] = GRID_SIZE_RANGE, global_mode: str = "texture") -> 'GridStyle':
        """生成随机网格样式
        
        生成逻辑：
        1. 确定color模式/texture模式
        2. 确定grid size: 1x1-3x3（均为居中）和对应pattern矩阵，要求是连通的：
           - texture mode: 全1矩阵
           - color mode: 进行随机采样pattern矩阵（1x1固定为1；2x2至少有两个；3x3至少有3个）
        3. 随机采样show grid: true/false
        4. 对于color mode对应pattern依次采样颜色；对于texture采样一种统一颜色然后依次采样样式
        
        Args:
            grid_size_range: 网格尺寸范围
            global_mode: 全局模式 "color" 或 "texture"
        """
        # 1. 确定grid size和cell_size（根据整体scale计算，考虑旋转对角线）
        size = random.randint(*grid_size_range)
        # 随机选择整体grid占画幅的比例
        scale = random.uniform(*GRID_SCALE_RANGE)
        # 根据整体grid大小计算每个cell的大小，考虑旋转时对角线的最大长度
        # 旋转时对角线长度为 size * cell_size * sqrt(2) ≤ FRAME_HEIGHT * scale
        # 所以：cell_size ≤ (FRAME_HEIGHT * scale) / (size * sqrt(2))
        cell_size = (FRAME_HEIGHT * scale) / (size * math.sqrt(2))
        
        # 2. 根据模式生成pattern
        if global_mode == "color":
            # COLOR模式：生成连通的pattern
            min_ones = PATTERN_MIN_ONES.get(size, 1)
            pattern = generate_random_pattern(size, min_ones)
        else:  # texture mode
            # TEXTURE模式：全1矩阵
            pattern = [[1 for _ in range(size)] for _ in range(size)]
        
        # 3. 随机采样show_grid
        show_grid = random.choice(SHOW_GRID_OPTIONS)
        
        # 4. 创建grid_style（先不创建cell_styles）
        grid_style = cls(
            rows=size,
            cols=size,
            cell_size=cell_size,
            pattern=pattern,
            show_grid=show_grid,
            cell_styles=[]
        )
        
        # 5. 统一采样样式参数（全局只采样一次）
        fill_opacity = random.uniform(*FILL_OPACITY_RANGE)
        stroke_width = random.uniform(*STROKE_WIDTH_RANGE)
        
        # 选择边框颜色
        if STROKE_COLOR_MODE == "grid":
            stroke_color_val = random.choice(GRID_COLOR_POOL)
        else:  # "white"
            stroke_color_val = "WHITE"
        
        # 6. 根据模式生成cell_styles
        num_ones = count_ones_in_pattern(pattern)
        
        if global_mode == "color":
            # COLOR模式：依次采样颜色（样式参数统一）
            for _ in range(num_ones):
                random_color = random.choice(COLOR_POOL)
                grid_style.cell_styles.append(GridCellStyle(
                    style_type=StyleType.COLOR,
                    color=random_color,
                    fill_opacity=fill_opacity,
                    stroke_width=stroke_width,
                    stroke_color=stroke_color_val
                ))
        else:  # texture mode
            # TEXTURE模式：采样一种统一颜色，然后依次采样样式
            base_color = random.choice(COLOR_POOL)
            
            # 生成texture颜色和透明度
            if TEXTURE_COLOR_MODE == "random":
                texture_color_val = random.choice(COLOR_POOL)
            elif TEXTURE_COLOR_MODE == "grid":
                # grid模式：texture颜色和边框颜色相同
                texture_color_val = stroke_color_val
            else:  # "cell"
                texture_color_val = None  # 使用cell颜色
            
            texture_opacity_val = random.uniform(*TEXTURE_OPACITY_RANGE)
            
            for _ in range(num_ones):
                # 随机选择texture类型
                texture_type = random.choice(TEXTURE_TYPE_POOL)
                
                if texture_type == "line":
                    direction = random.choice(LINE_DIRECTION_POOL)
                    grid_style.cell_styles.append(GridCellStyle(
                        style_type=StyleType.TEXTURE,
                        texture_type=TextureType.LINE,
                        line_direction=LineDirection(direction),
                        color=base_color,
                        fill_opacity=fill_opacity,
                        stroke_width=stroke_width,
                        stroke_color=stroke_color_val,
                        texture_opacity=texture_opacity_val,
                        texture_color=texture_color_val
                    ))
                else:  # polygon
                    shape = random.choice(POLYGON_SHAPE_POOL)
                    grid_style.cell_styles.append(GridCellStyle(
                        style_type=StyleType.TEXTURE,
                        texture_type=TextureType.POLYGON,
                        polygon_shape=PolygonShape(shape),
                        color=base_color,
                        fill_opacity=fill_opacity,
                        stroke_width=stroke_width,
                        stroke_color=stroke_color_val,
                        texture_opacity=texture_opacity_val,
                        texture_color=texture_color_val
                    ))
        
        return grid_style
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "rows": self.rows,
            "cols": self.cols,
            "cell_size": self.cell_size,
            "show_grid": self.show_grid,
            "cell_styles": [style.to_dict() for style in self.cell_styles]
        }
        # 如果是全1 pattern，则不保存（节省空间）
        all_ones = all(all(cell == 1 for cell in row) for row in self.pattern)
        if not all_ones:
            result["pattern"] = self.pattern
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GridStyle':
        """从字典创建"""
        cell_styles = [
            GridCellStyle.from_dict(style_data) 
            for style_data in data.get("cell_styles", [])
        ]
        
        # 如果字典中没有pattern，则为None（会自动生成全1矩阵）
        pattern = data.get("pattern", None)
        
        return cls(
            rows=data.get("rows", 2),
            cols=data.get("cols", 2),
            cell_size=data.get("cell_size", 1.0),
            pattern=pattern,
            show_grid=data.get("show_grid", True),
            cell_styles=cell_styles
        )


# ==================== JSON生成工具 ====================

def _generate_rotation_config() -> Dict[str, Any]:
    """生成rotation配置（只包含renderer实际使用的字段）"""
    speed = random.choice(ROTATION_SPEED_OPTIONS)
    angle = round(random.uniform(*ROTATION_ANGLES_RANGE), 1)
    # duration = 旋转角度 * 速度系数
    duration = angle * ROTATION_SPEED_FACTOR[speed]
    clockwise = random.choice(CLOCKWISE_OPTIONS)
    
    return {
        "rotation_angle": angle,
        "clockwise": clockwise,
        "speed": speed,
        "duration": round(duration, 2),  # 保留2位小数
        "direction": {
            "clockwise": clockwise,
            "angle": angle
        }
    }


def _generate_video_config() -> Dict[str, Any]:
    """生成video配置（精简版，只包含renderer使用的字段）"""
    return {
        "background_color": random.choice(BACKGROUND_COLORS)
    }

def generate_json_config(grid_size: int = 3, global_mode: str = "color", filename: str = "default") -> Dict[str, Any]:
    """生成单条JSON配置（包含variants）
    
    Args:
        grid_size: 网格尺寸 (1, 2, 3)
        global_mode: "color" 或 "texture"
        filename: 输出文件名
    
    Returns:
        精简的数据配置JSON（只包含object, rotation, video, variants）
    """
    grid_style = GridStyle.generate_random(
        grid_size_range=(grid_size, grid_size),
        global_mode=global_mode
    )
    
    pattern = grid_style.pattern if not all(all(cell == 1 for cell in row) for row in grid_style.pattern) else None
    
    # 提取统一的样式参数（所有cell共享）
    first_cell_style = grid_style.cell_styles[0] if grid_style.cell_styles else GridCellStyle("color", "BLUE", 0.8, 2.0, "WHITE")
    uniform_styles = {
        "fill_opacity": first_cell_style.fill_opacity,
        "stroke_width": first_cell_style.stroke_width,
        "stroke_color": first_cell_style.stroke_color,
    }
    if global_mode == "texture":
        if hasattr(first_cell_style, 'texture_opacity'):
            uniform_styles["texture_opacity"] = first_cell_style.texture_opacity
        if hasattr(first_cell_style, 'texture_color'):
            uniform_styles["texture_color"] = first_cell_style.texture_color
    
    # 生成cells（包含位置信息）
    def pattern_to_cells(p: List[List[int]]) -> List[Dict[str, Any]]:
        """将pattern转换为cells列表"""
        cells = []
        style_idx = 0
        for r in range(len(p)):
            for c in range(len(p[0])):
                if p[r][c] == 1:
                    style = grid_style.cell_styles[style_idx] if style_idx < len(grid_style.cell_styles) else grid_style.cell_styles[-1]
                    style_idx += 1
                    
                    cell = {"pos": [r, c]}
                    if global_mode == "color":
                        # color模式
                        cell["color"] = style.color
                    else:  # texture模式
                        # texture模式
                        cell["color"] = style.color
                        if style.texture_type:
                            cell["texture_type"] = style.texture_type.value
                        if style.line_direction:
                            cell["line_direction"] = style.line_direction.value
                        if style.polygon_shape:
                            cell["polygon_shape"] = style.polygon_shape.value
                    cells.append(cell)
        return cells
    
    def mirror_cells_vertical(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
        """垂直镜像cells：将每个cell的pos进行垂直镜像变换"""
        # 对于每个cell的pos=[r, c]
        # 新的行 = rows - 1 - r
        # 新的pos = [rows - 1 - r, c]
        
        mirrored_cells = []
        for cell in cells:
            r, c = cell["pos"]
            # 计算镜像位置
            mirror_r = rows - 1 - r
            # 创建新cell，保持所有内容，只变换pos
            new_cell = {**cell, "pos": [mirror_r, c]}
            
            # 统一互换slash方向（无需判断位置）
            line_dir = new_cell.get("line_direction")
            if line_dir == "left_slash":
                new_cell["line_direction"] = "right_slash"
            elif line_dir == "right_slash":
                new_cell["line_direction"] = "left_slash"
            
            mirrored_cells.append(new_cell)
        
        return mirrored_cells
    
    def mirror_cells_horizontal(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
        """水平镜像cells：将每个cell的pos进行水平镜像变换"""
        # 对于每个cell的pos=[r, c]
        # 新的列 = cols - 1 - c
        # 新的pos = [r, cols - 1 - c]
        
        mirrored_cells = []
        for cell in cells:
            r, c = cell["pos"]
            # 计算镜像位置
            mirror_c = cols - 1 - c
            # 创建新cell，保持所有内容，只变换pos
            new_cell = {**cell, "pos": [r, mirror_c]}
            
            # 统一互换slash方向（无需判断位置）
            line_dir = new_cell.get("line_direction")
            if line_dir == "left_slash":
                new_cell["line_direction"] = "right_slash"
            elif line_dir == "right_slash":
                new_cell["line_direction"] = "left_slash"
            
            mirrored_cells.append(new_cell)
        
        return mirrored_cells
    
    def add_cell_to_cells(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
        """添加一个连通cell到cells"""
        # 找到所有已占用的位置
        used_positions = set(tuple(cell["pos"]) for cell in cells)
        
        # 找到所有0的位置（邻居）
        neighbors = []
        for cell in cells:
            r, c = cell["pos"]
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in used_positions:
                    if (nr, nc) not in neighbors:
                        neighbors.append((nr, nc))
        
        if neighbors:
            # 随机添加一个
            import random as rand_module
            new_r, new_c = rand_module.choice(neighbors)
            # 使用第一个cell的样式作为新cell
            new_cell = {**cells[0], "pos": [new_r, new_c]}
            return cells + [new_cell]
        
        return cells.copy()
    
    def modify_cell_for_s4(cells: List[Dict[str, Any]], mode: str) -> Tuple[List[Dict[str, Any]], str]:
        """s4变体：根据mode进行不同处理"""
        import random as rand_module
        
        if len(cells) <= 1:
            return cells.copy(), "remove_cell"
        
        result_cells = [cell.copy() for cell in cells]
        
        if mode == "color":
            # color模式：随机改变一个cell的颜色
            idx = rand_module.randint(0, len(result_cells) - 1)
            modified_cell = result_cells[idx].copy()
            # 随机选择一个新的color
            new_color = rand_module.choice(["BLUE", "RED", "GREEN", "ORANGE", "PINK", "PURPLE", "YELLOW"])
            modified_cell["color"] = new_color
            result_cells[idx] = modified_cell
            return result_cells, "modify_color"
        
        else:  # texture模式
            # 找到所有斜线cells
            slash_cells = []
            for i, cell in enumerate(result_cells):
                line_dir = cell.get("line_direction")
                if line_dir in ["left_slash", "right_slash"]:
                    slash_cells.append((i, cell, line_dir))
            
            if slash_cells:
                # 有斜线，随机选择一个改变方向
                idx, cell, line_dir = rand_module.choice(slash_cells)
                modified_cell = cell.copy()
                # 切换斜线方向
                new_dir = "right_slash" if line_dir == "left_slash" else "left_slash"
                modified_cell["line_direction"] = new_dir
                result_cells[idx] = modified_cell
                return result_cells, "modify_slash"
            
            # 没有斜线，找方向线
            direction_cells = []
            for i, cell in enumerate(result_cells):
                line_dir = cell.get("line_direction")
                if line_dir in ["vertical", "horizontal"]:
                    direction_cells.append((i, cell, line_dir))
            
            if direction_cells:
                # 有方向线，随机选择一个改变方向
                idx, cell, line_dir = rand_module.choice(direction_cells)
                modified_cell = cell.copy()
                # 切换方向
                new_dir = "horizontal" if line_dir == "vertical" else "vertical"
                modified_cell["line_direction"] = new_dir
                result_cells[idx] = modified_cell
                return result_cells, "modify_direction"
            
            # 都没有，随机删除一个cell
            idx_to_remove = rand_module.choice(range(1, len(result_cells)))
            removed_cells = result_cells[:idx_to_remove] + result_cells[idx_to_remove+1:]
            return removed_cells, "remove_cell"
    
    def swap_cells_positions(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
        """交换两个不同样式的cells的pos"""
        if len(cells) <= 1:
            return cells.copy()
        
        import random as rand_module
        
        # 找到不同样式的cells对
        different_pairs = []
        for i in range(len(cells)):
            for j in range(i + 1, len(cells)):
                c1, c2 = cells[i], cells[j]
                
                # 检查是否不同（color, texture_type, line_direction, polygon_shape）
                color_diff = c1.get("color") != c2.get("color")
                texture_diff = c1.get("texture_type") != c2.get("texture_type")
                line_diff = c1.get("line_direction") != c2.get("line_direction")
                polygon_diff = c1.get("polygon_shape") != c2.get("polygon_shape")
                
                if color_diff or texture_diff or line_diff or polygon_diff:
                    different_pairs.append((i, j))
        
        cells_copy = [cell.copy() for cell in cells]
        
        if different_pairs:
            idx1, idx2 = rand_module.choice(different_pairs)
            # 交换pos
            cells_copy[idx1]["pos"], cells_copy[idx2]["pos"] = cells_copy[idx2]["pos"], cells_copy[idx1]["pos"]
        else:
            # 所有cells样式相同，随机交换两个
            if len(cells) > 1:
                idx1, idx2 = rand_module.sample(range(len(cells)), 2)
                cells_copy[idx1]["pos"], cells_copy[idx2]["pos"] = cells_copy[idx2]["pos"], cells_copy[idx1]["pos"]
        
        return cells_copy
    
    # 旧版cell_colors保留以兼容
    cell_colors = []
    for style in grid_style.cell_styles:
        if global_mode == "color":
            color_dict = {"color": style.color}
        else:
            color_dict = {"color": style.color}
            if style.texture_type:
                color_dict["texture_type"] = style.texture_type.value
            if style.line_direction:
                color_dict["line_direction"] = style.line_direction.value
            if style.polygon_shape:
                color_dict["polygon_shape"] = style.polygon_shape.value
        cell_colors.append(color_dict)
    
    # 生成visual参数（统一视觉参数）
    visual_params = {
        **uniform_styles,
        "cell_size": grid_style.cell_size,
        "show_grid": grid_style.show_grid
    }
    
    # 生成variants的基础结构
    variants = {}
    
    # 将pattern转换为cells
    if pattern and not all(all(cell == 1 for cell in row) for row in pattern):
        base_cells = pattern_to_cells(pattern)
    else:
        # 全1矩阵
        base_cells = pattern_to_cells([[1 for _ in range(grid_style.cols)] for _ in range(grid_style.rows)])
    
    # s0: original
    variants["s0"] = {
        "cells": base_cells,
        "description": "original"
    }
    
    # 生成其他variants
    # s1: vertical mirror
    s1_cells = mirror_cells_vertical(base_cells, grid_style.rows, grid_style.cols)
    variants["s1"] = {
        "cells": s1_cells,
        "description": "vertical_mirror"
    }
    
    # s2: horizontal mirror
    s2_cells = mirror_cells_horizontal(base_cells, grid_style.rows, grid_style.cols)
    variants["s2"] = {
        "cells": s2_cells,
        "description": "horizontal_mirror"
    }
    
    # s3: swap cells（交换pos，原来是s5的逻辑）
    s3_cells = swap_cells_positions(base_cells, grid_style.rows, grid_style.cols)
    variants["s3"] = {
        "cells": s3_cells,
        "description": "swap"
    }
    
    # s4: 根据mode修改cell
    s4_cells, s4_description = modify_cell_for_s4(base_cells, global_mode)
    variants["s4"] = {
        "cells": s4_cells,
        "description": s4_description
    }
    
    # s5: add cell（原来是s3的逻辑，暂且注释掉不启用）
    # if len(base_cells) >= grid_style.rows * grid_style.cols:
    #     # 已经满了，不做操作
    #     s5_cells = base_cells
    #     s5_description = None
    # else:
    #     s5_cells = add_cell_to_cells(base_cells, grid_style.rows, grid_style.cols)
    #     # 检查是否真的添加了cell
    #     if len(s5_cells) > len(base_cells):
    #         s5_description = "add"
    #     else:
    #         # 添加失败，不做操作
    #         s5_description = None
    
    # variants["s5"] = {
    #     "cells": s5_cells,
    #     "description": s5_description
    # }
    
    return {
        "shape_id": int(filename.replace("2dr_", "").replace(".json", "")) if filename.replace("2dr_", "").replace(".json", "").isdigit() else 0,
        "type": "grid",
        "rows": grid_style.rows,
        "cols": grid_style.cols,
        "mode": global_mode,
        "visual": visual_params,
        "rotation": _generate_rotation_config(),
        "video": _generate_video_config(),
        "variants": variants
    }


def generate_batch_json_configs(
    num_configs: int = 10,
    grid_size_range: Tuple[int, int] = (1, 3),
    global_mode: str = "color",
    filename_prefix: str = "config"
) -> List[Dict[str, Any]]:
    """批量生成JSON配置
    
    Args:
        num_configs: 生成配置数量
        grid_size_range: 网格尺寸范围
        global_mode: 全局模式
        filename_prefix: 文件名前缀
    """
    configs = []
    for i in range(num_configs):
        grid_size = random.randint(*grid_size_range)
        filename = f"{filename_prefix}_{i:04d}"
        config = generate_json_config(grid_size, global_mode, filename)
        configs.append(config)
    return configs


def save_json_config(config: Dict[str, Any], filename: str):
    """保存JSON配置到文件"""
    with open(filename, 'w') as f:
        json.dump(config, f, indent=2)


def load_json_config(filename: str) -> Dict[str, Any]:
    """从文件加载JSON配置"""
    with open(filename, 'r') as f:
        return json.load(f)


def json_to_grid_style(config: Dict[str, Any]) -> GridStyle:
    """从JSON配置创建GridStyle对象"""
    obj_data = config.get("object", {})
    
    return GridStyle.from_dict({
        "rows": obj_data.get("rows", 3),
        "cols": obj_data.get("cols", 3),
        "cell_size": obj_data.get("cell_size", 1.0),
        "pattern": obj_data.get("pattern", None),
        "show_grid": obj_data.get("show_grid", True),
        "cell_styles": obj_data.get("cell_styles", [])
    })


def generate_batch_to_directory(
    batch_size: int = 10,
    grid_size_range: Tuple[int, int] = (1, 3),
    global_mode: str = "color",
    output_dir: str = "medias"
) -> str:
    """批量生成JSON配置并保存到带时间戳的目录
    
    Args:
        batch_size: 生成数量
        grid_size_range: 网格尺寸范围
        global_mode: 全局模式
        output_dir: 输出基础目录
    
    Returns:
        创建的批次目录路径
    """
    # 创建批次目录名（带时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = os.path.join(output_dir, f"batch_{timestamp}")
    
    # 创建目录
    os.makedirs(batch_dir, exist_ok=True)
    
    print(f"📁 创建批次目录: {batch_dir}")
    print(f"📝 生成 {batch_size} 个配置...")
    
    # 批量生成并保存
    for i in range(batch_size):
        grid_size = random.randint(*grid_size_range)
        # 随机选择 color 或 texture 模式
        mode = global_mode if global_mode in ["color", "texture"] else random.choice(["color", "texture"])
        config = generate_json_config(grid_size, mode)
        
        # 创建子目录：batch_datetime/2dr_XXX/
        sub_dir_name = f"2dr_{i+1:04d}"
        sub_dir = os.path.join(batch_dir, sub_dir_name)
        os.makedirs(sub_dir, exist_ok=True)
        
        # 保存为 2dr_XXX.json
        filename = f"{sub_dir_name}.json"
        filepath = os.path.join(sub_dir, filename)
        save_json_config(config, filepath)
        
        if (i + 1) % 10 == 0:
            print(f"  已生成 {i + 1}/{batch_size} 个配置")
    
    print(f"✓ 完成！所有配置已保存到: {batch_dir}")
    
    return batch_dir

if __name__ == "__main__":
    print("=" * 60)
    print("2DR 批量JSON配置生成器")
    print("=" * 60)
    
    # 生成配置（混合 color 和 texture 模式）
    batch_dir = generate_batch_to_directory(
        batch_size=BATCH_SIZE,           # 生成10个配置
        grid_size_range=GRID_SIZE_RANGE, # 使用配置文件中的grid尺寸范围
        global_mode="mixed",             # 混合模式
        output_dir="medias"              # 保存到2DR/medias/
    )
    
    print(f"\n生成的批次目录: {batch_dir}")
    print("\n查看文件列表:")
    import os
    files = os.listdir(batch_dir)
    print(f"  共 {len(files)} 个文件")
    print(f"  示例: {files[0]}, {files[1]}")