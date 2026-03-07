#!/usr/bin/env python3
# Meta: grid + variant (s0–s4) JSON generation. Rotation-group checks keep options distinct. See README.md.

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import random
import json
import os
import math
from datetime import datetime


# --- Config (grid, color, texture, rotation) ---

SAMPLES = 5
# --- 1. Grid size ---
GRID_SIZE_RANGE = (2, 3)
GRID_SCALE_RANGE = (0.5, 0.8)
FRAME_HEIGHT = 8.0

# Min ones per pattern (color mode)
PATTERN_MIN_ONES = {
    1: 1,
    2: 3,
    3: 3,
    4: 4
}

# --- 2. Colors ---
COLOR_POOL = ["BLUE", "RED", "GREEN", "ORANGE", "PINK", "PURPLE", "GRAY", "YELLOW"]
GRID_COLOR_POOL = ["BLACK", "WHITE", "GRAY"]

# --- 3. Texture ---
TEXTURE_TYPE_POOL = ["line", "polygon"]
LINE_DIRECTION_POOL = ["vertical", "horizontal", "left_slash", "right_slash"]
POLYGON_SHAPE_POOL = ["square", "circle", "diamond"]
TEXTURE_OPACITY_RANGE = (0.85, 1.0)
TEXTURE_COLOR_MODE = "grid"

# --- 4. Style ---
FILL_OPACITY_RANGE = (0.6, 1.0)
STROKE_WIDTH_RANGE = (1.5, 3.0)
STROKE_COLOR_MODE = "grid"

# --- 5. Mode ---
SHOW_GRID_OPTIONS = [True]

# --- 6. Rotation ---
ROTATION_ANGLES_RANGE = (90, 90)
CLOCKWISE_OPTIONS = [True, False]
ROTATION_SPEED_OPTIONS = ["fast", "medium"]
ROTATION_SPEED_FACTOR = {
    "fast": 0.016,
    "medium": 0.022,
    "slow": 0.033
}

# --- 7. Video ---
BACKGROUND_COLORS = ["#1a1a2e", "#000000"]


# --- Style / texture enums ---

class StyleType(Enum):
    COLOR = "color"
    TEXTURE = "texture"


class TextureType(Enum):
    LINE = "line"
    POLYGON = "polygon"

class LineDirection(Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    LEFT_SLASH = "left_slash"
    RIGHT_SLASH = "right_slash"


class PolygonShape(Enum):
    TRIANGLE = "triangle"
    SQUARE = "square"
    CIRCLE = "circle"
    DIAMOND = "diamond"


# --- Grid cell style ---

@dataclass
class GridCellStyle:
    style_type: StyleType = StyleType.COLOR
    color: str = "BLUE"
    texture_type: Optional[TextureType] = None
    line_direction: Optional[LineDirection] = None
    polygon_shape: Optional[PolygonShape] = None
    fill_opacity: float = 0.8
    stroke_width: float = 2.0
    stroke_color: str = "WHITE"
    texture_opacity: float = 1.0
    texture_color: Optional[str] = None
    
    def __post_init__(self):
        if self.style_type == StyleType.TEXTURE:
            if self.texture_type == TextureType.LINE and self.line_direction is None:
                self.line_direction = LineDirection.VERTICAL
            if self.texture_type == TextureType.POLYGON and self.polygon_shape is None:
                self.polygon_shape = PolygonShape.TRIANGLE
    
    @classmethod
    def random_style(cls) -> 'GridCellStyle':
        style_type = random.choice(list(StyleType))
        
        if style_type == StyleType.COLOR:
            return cls(
                style_type=style_type,
                color=random.choice(COLOR_POOL)
            )
        else:
            texture = random.choice(TEXTURE_TYPE_POOL)
            texture_type = TextureType(texture)
            if TEXTURE_COLOR_MODE == "random":
                texture_color_val = random.choice(COLOR_POOL)
            elif TEXTURE_COLOR_MODE == "grid":
                texture_color_val = random.choice(GRID_COLOR_POOL)
            else:
                texture_color_val = None
            
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
            else:
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
        '''Convert to dict.'''
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
            result["texture_opacity"] = self.texture_opacity
            if self.texture_color:
                result["texture_color"] = self.texture_color
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GridCellStyle':
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


# --- Pattern helpers ---

def count_ones_in_pattern(pattern: List[List[int]]) -> int:
    return sum(sum(row) for row in pattern)


def is_connected_pattern(pattern: List[List[int]]) -> bool:
    rows, cols = len(pattern), len(pattern[0])
    ones = []
    for i in range(rows):
        for j in range(cols):
            if pattern[i][j] == 1:
                ones.append((i, j))
    if not ones:
        return False
    visited = set()
    stack = [ones[0]]
    while stack:
        r, c = stack.pop()
        if (r, c) in visited:
            continue
        visited.add((r, c))
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if pattern[nr][nc] == 1 and (nr, nc) not in visited:
                    stack.append((nr, nc))
    
    return len(visited) == len(ones)


def generate_horizontal_mirror(pattern: List[List[int]]) -> List[List[int]]:
    '''Horizontal mirror (flip up-down).'''
    return pattern[::-1]


def generate_vertical_mirror(pattern: List[List[int]]) -> List[List[int]]:
    '''Vertical mirror (flip left-right).'''
    return [row[::-1] for row in pattern]


def generate_horizontal_mirror_with_styles(pattern: List[List[int]], cell_colors: List[Dict[str, Any]]) -> Tuple[List[List[int]], List[Dict[str, Any]]]:
    '''Horizontal mirror for pattern and cell_colors.'''
    rows = len(pattern)
    cols = len(pattern[0]) if pattern else 0
    mirrored_pattern = pattern[::-1]
    mirrored_colors = []
    color_map = {}
    color_idx = 0
    for i in range(rows):
        for j in range(cols):
            if pattern[i][j] == 1:
                color_map[(i, j)] = cell_colors[color_idx]
                color_idx += 1
    
    # Rebuild colors in mirrored order
    for i in range(rows):
        for j in range(cols):
            if mirrored_pattern[i][j] == 1:
                orig_i = rows - 1 - i
                orig_j = j
                mirrored_colors.append(color_map[(orig_i, orig_j)])
    
    return mirrored_pattern, mirrored_colors


def generate_vertical_mirror_with_styles(pattern: List[List[int]], cell_colors: List[Dict[str, Any]]) -> Tuple[List[List[int]], List[Dict[str, Any]]]:
    '''Vertical mirror for pattern and cell_colors.'''
    rows = len(pattern)
    cols = len(pattern[0]) if pattern else 0
    mirrored_pattern = [row[::-1] for row in pattern]
    mirrored_colors = []
    color_map = {}
    color_idx = 0
    for i in range(rows):
        for j in range(cols):
            if pattern[i][j] == 1:
                color_map[(i, j)] = cell_colors[color_idx]
                color_idx += 1
    
    # Rebuild colors in mirrored order
    for i in range(rows):
        for j in range(cols):
            if mirrored_pattern[i][j] == 1:
                orig_i = i
                orig_j = cols - 1 - j
                mirrored_colors.append(color_map[(orig_i, orig_j)])
    
    return mirrored_pattern, mirrored_colors


def add_cell_to_pattern(pattern: List[List[int]], rows: int, cols: int) -> List[List[int]]:
    '''Add one connected cell to pattern (within grid bounds).'''
    
    # Collect ones
    ones = [(i, j) for i in range(rows) for j in range(cols) if pattern[i][j] == 1]
    
    if not ones:
        return pattern
    
    # Neighbors of ones
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
    '''Swap cells with different styles only.'''
    rows = len(pattern)
    cols = len(pattern[0]) if pattern else 0
    
    # Ones with styles
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
    
    # Zeros
    zeros_positions = [(i, j) for i in range(rows) for j in range(cols) if pattern[i][j] == 0]
    
    if len(ones_positions) == 0 or len(zeros_positions) == 0:
        return pattern
    
    # Pairs with different style
    different_style_pairs = []
    for i in range(len(ones_positions)):
        for j in range(i + 1, len(ones_positions)):
            style1 = ones_positions[i]["style"]
            style2 = ones_positions[j]["style"]
            if style1 != style2:
                different_style_pairs.append((i, j))
    
    # Swap one pair
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
    '''Remove one cell from pattern (keep connected).'''
    size = len(pattern)
    
    # Collect ones
    ones = [(i, j) for i in range(size) for j in range(size) if pattern[i][j] == 1]
    
    if len(ones) <= 1:
        return pattern
    
    # Try remove, keep connected
    for r, c in random.sample(ones, min(len(ones), 10)):
        new_pattern = [row[:] for row in pattern]
        new_pattern[r][c] = 0
        
        # Check connected
        if is_connected_pattern(new_pattern):
            return new_pattern
    
    return pattern


def swap_cells_in_pattern(pattern: List[List[int]]) -> List[List[int]]:
    '''Randomly swap two cells (keep total ones).'''
    size = len(pattern)
    
    # Collect ones
    ones = [(i, j) for i in range(size) for j in range(size) if pattern[i][j] == 1]
    # Zeros
    zeros = [(i, j) for i in range(size) for j in range(size) if pattern[i][j] == 0]
    
    if len(ones) == 0 or len(zeros) == 0:
        return pattern
    
    # Swap one 1 and one 0
    r1, c1 = random.choice(ones)
    r0, c0 = random.choice(zeros)
    
    new_pattern = [row[:] for row in pattern]
    new_pattern[r1][c1] = 0
    new_pattern[r0][c0] = 1
    
    # Check connected
    if is_connected_pattern(new_pattern):
        return new_pattern
    
    return pattern


def is_symmetric_pattern(pattern: List[List[int]]) -> bool:
    '''Check if pattern is symmetric (H, V, or both). Returns True if any.'''
    size = len(pattern)
    
    # Horizontal symmetry
    horizontal_sym = True
    for i in range(size):
        for j in range(size):
            if pattern[i][j] != pattern[size-1-i][j]:
                horizontal_sym = False
                break
        if not horizontal_sym:
            break
    
    # Vertical symmetry
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
    '''Generate random connected asymmetric pattern. Args: size, min_ones.'''
    total_cells = size * size
    
    # Num ones
    num_ones = random.randint(min_ones, total_cells)
    
    # All positions
    all_positions = [(i, j) for i in range(size) for j in range(size)]
    
    max_attempts = 500
    for attempt in range(max_attempts):
        # Pick positions
        selected = random.sample(all_positions, num_ones)
        
        # Build pattern
        pattern = [[0 for _ in range(size)] for _ in range(size)]
        for r, c in selected:
            pattern[r][c] = 1
        
        # Check connected and asymmetric
        if is_connected_pattern(pattern) and not is_symmetric_pattern(pattern):
            return pattern
    
    # Fallback: connected only
    for attempt in range(100):
        selected = random.sample(all_positions, num_ones)
        pattern = [[0 for _ in range(size)] for _ in range(size)]
        for r, c in selected:
            pattern[r][c] = 1
        if is_connected_pattern(pattern):
            return pattern
    
    # Fallback: all ones
    return [[1 for _ in range(size)] for _ in range(size)]


@dataclass
class GridStyle:
    '''Grid style config.'''
    rows: int = 2
    cols: int = 2
    cell_size: float = 1.0
    pattern: Optional[List[List[int]]] = None
    cell_styles: List[GridCellStyle] = None
    show_grid: bool = True
    
    def __post_init__(self):
        '''Post-init validation.'''
        # Default full grid
        if self.pattern is None:
            self.pattern = [[1 for _ in range(self.cols)] for _ in range(self.rows)]
        
        if len(self.pattern) != self.rows:
            raise ValueError(f"pattern rows {len(self.pattern)} != rows {self.rows}")
        if len(self.pattern[0]) != self.cols:
            raise ValueError(f"pattern cols {len(self.pattern[0])} != cols {self.cols}")
        
        if self.cell_styles is None:
            total_cells = sum(sum(row) for row in self.pattern)
            self.cell_styles = [GridCellStyle.random_style() for _ in range(total_cells)]
    
    @classmethod
    def generate_random(cls, grid_size_range: Tuple[int, int] = GRID_SIZE_RANGE, global_mode: str = "texture") -> 'GridStyle':
        '''Generate random grid style (color/texture, grid size, pattern, show_grid, colors/styles).'''
        # 1. Grid size and cell_size
        size = random.randint(*grid_size_range)

        scale = random.uniform(*GRID_SCALE_RANGE)
        # cell_size so that size*cell_size*sqrt(2) <= FRAME_HEIGHT*scale
        cell_size = (FRAME_HEIGHT * scale) / (size * math.sqrt(2))
        
        # 2. Pattern
        if global_mode == "color":

            min_ones = PATTERN_MIN_ONES.get(size, 1)
            pattern = generate_random_pattern(size, min_ones)
        else:  # texture mode

            pattern = [[1 for _ in range(size)] for _ in range(size)]
        
        # 3. show_grid
        show_grid = random.choice(SHOW_GRID_OPTIONS)
        
        # 4. grid_style
        grid_style = cls(
            rows=size,
            cols=size,
            cell_size=cell_size,
            pattern=pattern,
            show_grid=show_grid,
            cell_styles=[]
        )
        
        # 5. Style params (global, sampled once)
        fill_opacity = random.uniform(*FILL_OPACITY_RANGE)
        stroke_width = random.uniform(*STROKE_WIDTH_RANGE)
        

        if STROKE_COLOR_MODE == "grid":
            stroke_color_val = random.choice(GRID_COLOR_POOL)
        else:  # "white"
            stroke_color_val = "WHITE"
        
        # 6. cell_styles
        num_ones = count_ones_in_pattern(pattern)
        
        if global_mode == "color":
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
            base_color = random.choice(COLOR_POOL)
            

            if TEXTURE_COLOR_MODE == "random":
                texture_color_val = random.choice(COLOR_POOL)
            elif TEXTURE_COLOR_MODE == "grid":

                texture_color_val = stroke_color_val
            else:  # "cell"
                texture_color_val = None
            
            texture_opacity_val = random.uniform(*TEXTURE_OPACITY_RANGE)
            
            for _ in range(num_ones):

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
        '''Convert to dict.'''
        result = {
            "rows": self.rows,
            "cols": self.cols,
            "cell_size": self.cell_size,
            "show_grid": self.show_grid,
            "cell_styles": [style.to_dict() for style in self.cell_styles]
        }
        # Skip pattern if all ones
        all_ones = all(all(cell == 1 for cell in row) for row in self.pattern)
        if not all_ones:
            result["pattern"] = self.pattern
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GridStyle':
        '''Create from dict.'''
        cell_styles = [
            GridCellStyle.from_dict(style_data) 
            for style_data in data.get("cell_styles", [])
        ]
        
        # pattern default
        pattern = data.get("pattern", None)
        
        return cls(
            rows=data.get("rows", 2),
            cols=data.get("cols", 2),
            cell_size=data.get("cell_size", 1.0),
            pattern=pattern,
            show_grid=data.get("show_grid", True),
            cell_styles=cell_styles
        )


# --- JSON generation ---

def _cells_canonical(cells: List[Dict[str, Any]]) -> Tuple[Tuple[Any, ...], ...]:
    '''Canonical comparable form of cells (sorted by (r,c), appearance keys only).'''
    key = lambda c: (c["pos"][0], c["pos"][1])
    out = []
    for cell in sorted(cells, key=key):
        r, c = cell["pos"]
        out.append((
            r, c,
            cell.get("color"),
            cell.get("texture_type"),
            cell.get("line_direction"),
            cell.get("polygon_shape"),
        ))
    return tuple(out)


def _rotate_cells_90_cw(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
    '''90 deg CW: (r,c)->(c,rows-1-r); line dirs swapped.'''
    result = []
    for cell in cells:
        r, c = cell["pos"]
        new_r, new_c = c, rows - 1 - r
        new_cell = {**cell, "pos": [new_r, new_c]}
        ld = new_cell.get("line_direction")
        if ld == "vertical":
            new_cell["line_direction"] = "horizontal"
        elif ld == "horizontal":
            new_cell["line_direction"] = "vertical"
        elif ld == "left_slash":
            new_cell["line_direction"] = "right_slash"
        elif ld == "right_slash":
            new_cell["line_direction"] = "left_slash"
        result.append(new_cell)
    return result


def _rotate_cells_90_ccw(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
    '''90 deg CCW: (r,c)->(cols-1-c,r); line dirs swapped.'''
    result = []
    for cell in cells:
        r, c = cell["pos"]
        new_r, new_c = cols - 1 - c, r
        new_cell = {**cell, "pos": [new_r, new_c]}
        ld = new_cell.get("line_direction")
        if ld == "vertical":
            new_cell["line_direction"] = "horizontal"
        elif ld == "horizontal":
            new_cell["line_direction"] = "vertical"
        elif ld == "left_slash":
            new_cell["line_direction"] = "right_slash"
        elif ld == "right_slash":
            new_cell["line_direction"] = "left_slash"
        result.append(new_cell)
    return result


def _mirror_cells_diag_main(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
    '''Main diagonal mirror (r,c)->(c,r); slash dirs swapped.'''
    result = []
    for cell in cells:
        r, c = cell["pos"]
        new_cell = {**cell, "pos": [c, r]}
        ld = new_cell.get("line_direction")
        if ld == "left_slash":
            new_cell["line_direction"] = "right_slash"
        elif ld == "right_slash":
            new_cell["line_direction"] = "left_slash"
        result.append(new_cell)
    return result


def _mirror_cells_diag_anti(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
    '''Anti diagonal mirror (r,c)->(cols-1-c,rows-1-r); slash dirs swapped.'''
    result = []
    for cell in cells:
        r, c = cell["pos"]
        new_cell = {**cell, "pos": [cols - 1 - c, rows - 1 - r]}
        ld = new_cell.get("line_direction")
        if ld == "left_slash":
            new_cell["line_direction"] = "right_slash"
        elif ld == "right_slash":
            new_cell["line_direction"] = "left_slash"
        result.append(new_cell)
    return result


def _generate_rotation_config() -> Dict[str, Any]:
    '''Build rotation config (fields used by renderer).'''
    speed = random.choice(ROTATION_SPEED_OPTIONS)
    angle = round(random.uniform(*ROTATION_ANGLES_RANGE), 1)

    duration = angle * ROTATION_SPEED_FACTOR[speed]
    clockwise = random.choice(CLOCKWISE_OPTIONS)
    
    return {
        "rotation_angle": angle,
        "clockwise": clockwise,
        "speed": speed,
        "duration": round(duration, 2),
        "direction": {
            "clockwise": clockwise,
            "angle": angle
        }
    }


def _generate_video_config() -> Dict[str, Any]:
    '''Build video config for renderer.'''
    return {
        "background_color": random.choice(BACKGROUND_COLORS)
    }

def generate_json_config(grid_size: int = 3, global_mode: str = "color", filename: str = "default", _retry: int = 0) -> Dict[str, Any]:
    '''Generate single JSON config with variants.'''
    max_retries = 50
    grid_style = GridStyle.generate_random(
        grid_size_range=(grid_size, grid_size),
        global_mode=global_mode
    )
    rotation_config = _generate_rotation_config()
    clockwise = rotation_config["direction"]["clockwise"]
    rows, cols = grid_style.rows, grid_style.cols
    
    pattern = grid_style.pattern if not all(all(cell == 1 for cell in row) for row in grid_style.pattern) else None
    
# Uniform style
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
    
# pattern_to_cells
    def pattern_to_cells(p: List[List[int]]) -> List[Dict[str, Any]]:
        '''Convert pattern to cells list.'''
        cells = []
        style_idx = 0
        for r in range(len(p)):
            for c in range(len(p[0])):
                if p[r][c] == 1:
                    style = grid_style.cell_styles[style_idx] if style_idx < len(grid_style.cell_styles) else grid_style.cell_styles[-1]
                    style_idx += 1
                    
                    cell = {"pos": [r, c]}
                    if global_mode == "color":

                        cell["color"] = style.color
                    else:

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
        '''Vertical mirror: mirror each cell pos.'''



        
        mirrored_cells = []
        for cell in cells:
            r, c = cell["pos"]

            mirror_r = rows - 1 - r

            new_cell = {**cell, "pos": [mirror_r, c]}
            

            line_dir = new_cell.get("line_direction")
            if line_dir == "left_slash":
                new_cell["line_direction"] = "right_slash"
            elif line_dir == "right_slash":
                new_cell["line_direction"] = "left_slash"
            
            mirrored_cells.append(new_cell)
        
        return mirrored_cells
    
    def mirror_cells_horizontal(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
        '''Horizontal mirror: mirror each cell pos.'''

        # new col = cols - 1 - c, new pos = [r, cols-1-c]
        
        mirrored_cells = []
        for cell in cells:
            r, c = cell["pos"]

            mirror_c = cols - 1 - c

            new_cell = {**cell, "pos": [r, mirror_c]}
            

            line_dir = new_cell.get("line_direction")
            if line_dir == "left_slash":
                new_cell["line_direction"] = "right_slash"
            elif line_dir == "right_slash":
                new_cell["line_direction"] = "left_slash"
            
            mirrored_cells.append(new_cell)
        
        return mirrored_cells
    
    def add_cell_to_cells(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
        '''Add one connected cell to cells.'''
# Used positions
        used_positions = set(tuple(cell["pos"]) for cell in cells)
        
        # Neighbors
        neighbors = []
        for cell in cells:
            r, c = cell["pos"]
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in used_positions:
                    if (nr, nc) not in neighbors:
                        neighbors.append((nr, nc))
        
        if neighbors:

            import random as rand_module
            new_r, new_c = rand_module.choice(neighbors)

            new_cell = {**cells[0], "pos": [new_r, new_c]}
            return cells + [new_cell]
        
        return cells.copy()
    
    def modify_cell_for_s4(cells: List[Dict[str, Any]], mode: str) -> Tuple[List[Dict[str, Any]], str]:
        '''s4 variant: handle by mode (color/texture/etc).'''
        import random as rand_module
        
        if len(cells) <= 1:
            return cells.copy(), "remove_cell"
        
        result_cells = [cell.copy() for cell in cells]
        
        if mode == "color":

            idx = rand_module.randint(0, len(result_cells) - 1)
            modified_cell = result_cells[idx].copy()

            new_color = rand_module.choice(["BLUE", "RED", "GREEN", "ORANGE", "PINK", "PURPLE", "YELLOW"])
            modified_cell["color"] = new_color
            result_cells[idx] = modified_cell
            return result_cells, "modify_color"
        
        else:
# Slash cells
            slash_cells = []
            for i, cell in enumerate(result_cells):
                line_dir = cell.get("line_direction")
                if line_dir in ["left_slash", "right_slash"]:
                    slash_cells.append((i, cell, line_dir))
            
            if slash_cells:

                idx, cell, line_dir = rand_module.choice(slash_cells)
                modified_cell = cell.copy()

                new_dir = "right_slash" if line_dir == "left_slash" else "left_slash"
                modified_cell["line_direction"] = new_dir
                result_cells[idx] = modified_cell
                return result_cells, "modify_slash"
            
# Direction lines
            direction_cells = []
            for i, cell in enumerate(result_cells):
                line_dir = cell.get("line_direction")
                if line_dir in ["vertical", "horizontal"]:
                    direction_cells.append((i, cell, line_dir))
            
            if direction_cells:

                idx, cell, line_dir = rand_module.choice(direction_cells)
                modified_cell = cell.copy()

                new_dir = "horizontal" if line_dir == "vertical" else "vertical"
                modified_cell["line_direction"] = new_dir
                result_cells[idx] = modified_cell
                return result_cells, "modify_direction"
            
# Remove cell
            idx_to_remove = rand_module.choice(range(1, len(result_cells)))
            removed_cells = result_cells[:idx_to_remove] + result_cells[idx_to_remove+1:]
            return removed_cells, "remove_cell"
    
    def swap_cells_positions(cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
        '''Swap pos of two cells with different styles.'''
        if len(cells) <= 1:
            return cells.copy()
        
        import random as rand_module
        
# Different-style pairs
        different_pairs = []
        for i in range(len(cells)):
            for j in range(i + 1, len(cells)):
                c1, c2 = cells[i], cells[j]
                
# Diff check, texture_type, line_direction, polygon_shape）
                color_diff = c1.get("color") != c2.get("color")
                texture_diff = c1.get("texture_type") != c2.get("texture_type")
                line_diff = c1.get("line_direction") != c2.get("line_direction")
                polygon_diff = c1.get("polygon_shape") != c2.get("polygon_shape")
                
                if color_diff or texture_diff or line_diff or polygon_diff:
                    different_pairs.append((i, j))
        
        cells_copy = [cell.copy() for cell in cells]
        
        if different_pairs:
            idx1, idx2 = rand_module.choice(different_pairs)

            cells_copy[idx1]["pos"], cells_copy[idx2]["pos"] = cells_copy[idx2]["pos"], cells_copy[idx1]["pos"]
        else:

            if len(cells) > 1:
                idx1, idx2 = rand_module.sample(range(len(cells)), 2)
                cells_copy[idx1]["pos"], cells_copy[idx2]["pos"] = cells_copy[idx2]["pos"], cells_copy[idx1]["pos"]
        
        return cells_copy
    
# visual_params
    visual_params = {
        **uniform_styles,
        "cell_size": grid_style.cell_size,
        "show_grid": grid_style.show_grid
    }
    
# variants
    variants = {}
    
# base_cells
    if pattern and not all(all(cell == 1 for cell in row) for row in pattern):
        base_cells = pattern_to_cells(pattern)
    else:

        base_cells = pattern_to_cells([[1 for _ in range(grid_style.cols)] for _ in range(grid_style.rows)])
    
# s0
    variants["s0"] = {
        "cells": base_cells,
        "description": "original"
    }
    
# s1-s4
# s1
    s1_cells = mirror_cells_vertical(base_cells, grid_style.rows, grid_style.cols)
    variants["s1"] = {
        "cells": s1_cells,
        "description": "vertical_mirror"
    }
    
# s2
    s2_cells = mirror_cells_horizontal(base_cells, grid_style.rows, grid_style.cols)
    variants["s2"] = {
        "cells": s2_cells,
        "description": "horizontal_mirror"
    }
    
    # s3: swap (was s5)
    s3_cells = swap_cells_positions(base_cells, grid_style.rows, grid_style.cols)
    variants["s3"] = {
        "cells": s3_cells,
        "description": "swap"
    }
    
# s4
    s4_cells, s4_description = modify_cell_for_s4(base_cells, global_mode)
    
# Rotation-group checks
    def _apply_rotation(cells_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return _rotate_cells_90_cw(cells_list, rows, cols) if clockwise else _rotate_cells_90_ccw(cells_list, rows, cols)
    R_s0 = _apply_rotation(base_cells)
    R_s1 = _apply_rotation(s1_cells)
    R_s2 = _apply_rotation(s2_cells)
    R_s3 = _apply_rotation(s3_cells)
    R_s4 = _apply_rotation(s4_cells)
    canonicals = [_cells_canonical(R_s0), _cells_canonical(R_s1), _cells_canonical(R_s2), _cells_canonical(R_s3), _cells_canonical(R_s4)]
    if len(set(canonicals)) != 5 and _retry < max_retries:
        return generate_json_config(grid_size, global_mode, filename, _retry + 1)
    mirror_H = _cells_canonical(mirror_cells_horizontal(base_cells, rows, cols))
    mirror_V = _cells_canonical(mirror_cells_vertical(base_cells, rows, cols))
    mirror_D1 = _cells_canonical(_mirror_cells_diag_main(base_cells, rows, cols))
    mirror_D2 = _cells_canonical(_mirror_cells_diag_anti(base_cells, rows, cols))
    mirrors = {mirror_H, mirror_V, mirror_D1, mirror_D2}
    r1, r2 = _apply_rotation(base_cells), _apply_rotation(_apply_rotation(base_cells))
    r3 = _apply_rotation(r2)
    for rot_canon in (_cells_canonical(r1), _cells_canonical(r2), _cells_canonical(r3)):
        if rot_canon in mirrors:
            if _retry < max_retries:
                return generate_json_config(grid_size, global_mode, filename, _retry + 1)
            break
    
    variants["s4"] = {
        "cells": s4_cells,
        "description": s4_description
    }
    
    # s5 add cell (commented out)
    # if len(base_cells) >= grid_style.rows * grid_style.cols:

    #     s5_cells = base_cells
    #     s5_description = None
    # else:
    #     s5_cells = add_cell_to_cells(base_cells, grid_style.rows, grid_style.cols)

    #     if len(s5_cells) > len(base_cells):
    #         s5_description = "add"
    #     else:
    #         # add failed
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
        "rotation": rotation_config,
        "video": _generate_video_config(),
        "variants": variants
    }


def generate_batch_json_configs(
    num_configs: int = 10,
    grid_size_range: Tuple[int, int] = (1, 3),
    global_mode: str = "color",
    filename_prefix: str = "config"
) -> List[Dict[str, Any]]:
    '''Batch generate JSON configs.'''
    configs = []
    for i in range(num_configs):
        grid_size = random.randint(*grid_size_range)
        filename = f"{filename_prefix}_{i:04d}"
        config = generate_json_config(grid_size, global_mode, filename)
        configs.append(config)
    return configs


def save_json_config(config: Dict[str, Any], filename: str):
    '''Save JSON config to file.'''
    with open(filename, 'w') as f:
        json.dump(config, f, indent=2)


def load_json_config(filename: str) -> Dict[str, Any]:
    '''Load JSON config from file.'''
    with open(filename, 'r') as f:
        return json.load(f)


def json_to_grid_style(config: Dict[str, Any]) -> GridStyle:
    '''Create GridStyle from JSON config.'''
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
    samples: int = 10,
    grid_size_range: Tuple[int, int] = (1, 3),
    global_mode: str = "color",
    output_dir: str = "medias"
) -> str:
    '''Generate batch to timestamped dir. Returns batch dir path.'''
# Batch dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = os.path.join(output_dir, f"batch_{timestamp}")
    shape_dir = os.path.join(batch_dir, "shape")
    

    os.makedirs(shape_dir, exist_ok=True)
    
    print(f"Batch dir: {batch_dir}")
    print(f"Generating {samples} configs to shape/ ...")
    
    for i in range(samples):
        grid_size = random.randint(*grid_size_range)

        mode = global_mode if global_mode in ["color", "texture"] else random.choice(["color", "texture"])
        config = generate_json_config(grid_size, mode)
        
        sub_dir_name = f"2dr_{i+1:04d}"
        filename = f"{sub_dir_name}.json"
        filepath = os.path.join(shape_dir, filename)
        save_json_config(config, filepath)
        
        if (i + 1) % 10 == 0:
            print(f"  Generated {i + 1}/{samples}")
    
    print(f"Done. Configs saved to: {shape_dir}")
    
    return batch_dir


def main():
    '''Entry: batch generate JSON to batch_dir/shape/.'''
    print("=" * 60)
    print("2DR batch JSON config generator")
    print("=" * 60)
    batch_dir = generate_batch_to_directory(
        samples=SAMPLES,
        grid_size_range=GRID_SIZE_RANGE,
        global_mode="mixed",
        output_dir="medias",
    )
    print(f"\nBatch dir: {batch_dir}")
    shape_dir = os.path.join(batch_dir, "shape")
    if os.path.isdir(shape_dir):
        files = os.listdir(shape_dir)
        print(f"  shape/ has {len(files)} JSON files: {files[:3]}{'...' if len(files) > 3 else ''}")


if __name__ == "__main__":
    main()