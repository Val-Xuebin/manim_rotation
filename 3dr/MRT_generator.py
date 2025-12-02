#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
import itertools
import numpy as np

# ==================== 参数范围配置 ====================
EASY_INSTANCE_NUM = 7 # 61*N
HARD_INSTANCE_NUM = 7 # 61*N

# Cube visual 参数范围
CUBE_SIZE_RANGE = (0.8, 1.2)
SPACING_RANGE = (0.0, 0.0)
FILL_OPACITY_RANGE = (0.7, 0.9)
STROKE_WIDTH_RANGE = (1.0, 2.0)
STROKE_OPACITY_RANGE = (0.8, 1.0)

# 颜色池（用于 visual 配置）
FILL_COLOR_POOL = ["BLUE", "RED", "GREEN", "ORANGE", "PINK", "PURPLE", "GRAY"]
STROKE_COLOR_POOL = ["WHITE", "BLACK"]
        
ROTATION_ANGLES_RANGE = (45, 135)  # 度数范围
ROTATION_SPEEDS = ["slow", "medium"] # "slow", "medium", "fast"
CENTER_MODES = ["mass", "cube"]  # 保持离散选择: "mass", "cube"
CLOCKWISE_OPTIONS = [True, False]  # 保持离散选择
    
# Video 参数范围
PHI_RANGE = (65, 70)    # 仰角范围
THETA_RANGES = [(30, 60), (120, 150), (210, 240), (300, 330)]  # 方位角范围，4个离散范围
ZOOM_RANGE = (1.2 ,1.9)

# 可视化元素白名单（固定，不随机；为空则全部不显示）
# 可选项："axes", "axes_labels", "rotation_axis", "rotation_circle", "velocity_arrow", "labels", "bounding_box"
VISUAL_ELEMENTS_WHITELIST: List[str] = []
    
    # Output 配置
PIXEL_WIDTHS = [1280]  # 720p (1280x720)
PIXEL_HEIGHTS = [720]  # 720p
FRAME_RATES = [30]  # 30fps

# ==================== 数据结构定义 ====================

@dataclass
class VoxelGroup:
    """一组voxel数据"""
    group_id: int
    voxels: List[List[List[int]]]  # s0, s1, s2, s3（每个元素是一整个体素结构：坐标列表）
    voxel_count: int

@dataclass
class Instance:
    """一个实例"""
    instance_id: int
    difficulty: str  # "Easy" or "Hard"
    voxel_group: VoxelGroup
    visual_config: Dict[str, Any]
    rotation_configs: List[Dict[str, Any]]  # Easy: 1个, Hard: 3个

@dataclass
class MRTConfig:
    """MRT配置"""
    group_id: int
    instance_id: int
    voxel_index: int  # s0, s1, s2, s3
    rotation_index: int  # r0, r1, r2, r3
    voxel_data: List[int]
    visual_config: Dict[str, Any]
    rotation_config: Dict[str, Any]
    video_config: Dict[str, Any]
    output_config: Dict[str, Any]
    difficulty: str  # Easy 或 Hard

# ==================== MRT Generator ====================

class MRTGenerator:
    """MRT生成器 - 从chiral JSON读取voxel数据并生成配置"""
    
    def __init__(self, chiral_json_path: str):
        self.chiral_json_path = chiral_json_path
        self.chiral_data = None
        self.voxel_groups = []
        self.instances = []
        self.configs = []
        
    def load_chiral_data(self):
        """加载chiral JSON数据"""
        with open(self.chiral_json_path, 'r', encoding='utf-8') as f:
            self.chiral_data = json.load(f)
        print(f"✓ 已加载chiral数据: {len(self.chiral_data)} 个形状")
        
    def extract_voxel_groups(self):
        """从chiral数据中提取voxel组，每组4个voxel (s0, s1, s2, s3)"""
        if not self.chiral_data:
            raise ValueError("请先加载chiral数据")
            
        # 新格式：直接是数组，每个元素包含shape_id, voxel_count, variants
        shapes = self.chiral_data
        group_id = 0
        
        
        for shape in shapes:
            variants = shape['variants']
            
            # s0: original 的整结构（坐标列表）
            s0 = variants['original']['voxels']
            
            # s1: 从3个mirror中随机选择一个
            mirror_variants = ['xoy_mirror', 'xoz_mirror', 'yoz_mirror']
            available_mirrors = [v for v in mirror_variants if v in variants]
            if available_mirrors:
                selected_mirror_s1 = random.choice(available_mirrors)
                s1 = variants[selected_mirror_s1]['voxels']
            else:
                # 如果没有镜像变体，使用original作为fallback
                s1 = s0.copy()
                selected_mirror_s1 = None
            
            # s2: 从除了s1的两个mirror中随机选择一个
            remaining_mirrors = [v for v in available_mirrors if v != selected_mirror_s1]
            if remaining_mirrors:
                selected_mirror_s2 = random.choice(remaining_mirrors)
                s2 = variants[selected_mirror_s2]['voxels']
            else:
                # 如果没有剩余的镜像变体，使用original作为fallback
                s2 = s0.copy()
            
            # s3: 从remove/move变体中随机选择一个
            modify_variants = ['remove', 'move']
            available_modifies = [v for v in modify_variants if v in variants]
            if available_modifies:
                selected_modify = random.choice(available_modifies)
                s3 = variants[selected_modify]['voxels']
            else:
                # 如果没有修改变体，使用original作为fallback
                s3 = s0.copy()

            group_voxels = [s0, s1, s2, s3]
            voxel_group = VoxelGroup(
                group_id=group_id,
                voxels=group_voxels,
                voxel_count=4  # 现在有4个voxel组
            )
            self.voxel_groups.append(voxel_group)
            group_id += 1
                
        print(f"✓ 已提取 {len(self.voxel_groups)} 个voxel组")
        
    def generate_instances(self, easy_instances_per_group: int = 1, hard_instances_per_group: int = 1):
        """为每个voxel组生成指定数量的easy和hard实例"""
        for group in self.voxel_groups:
            instance_id = 0
            
            # 生成Easy实例
            for _ in range(easy_instances_per_group):
                # 重新采样s1和s2
                new_group = self._resample_voxel_group(group)
                
                # 生成visual配置（每个instance固定）
                visual_config = self._generate_visual_config()
                
                # Easy: 1个rotation配置
                rotation_configs = [self._generate_rotation_config()]
                
                instance = Instance(
                    instance_id=instance_id,
                    difficulty="Easy",
                    voxel_group=new_group,
                    visual_config=visual_config,
                    rotation_configs=rotation_configs
                )
                self.instances.append(instance)
                instance_id += 1
            
            # 生成Hard实例
            for _ in range(hard_instances_per_group):
                # 重新采样s1和s2
                new_group = self._resample_voxel_group(group)
                
                # 生成visual配置（每个instance固定）
                visual_config = self._generate_visual_config()
                
                # Hard: 4个rotation配置 (r0, r1, r2, r3)
                rotation_configs = [self._generate_rotation_config() for _ in range(4)]
                
                instance = Instance(
                    instance_id=instance_id,
                    difficulty="Hard",
                    voxel_group=new_group,
                    visual_config=visual_config,
                    rotation_configs=rotation_configs
                )
                self.instances.append(instance)
                instance_id += 1
                
        print(f"✓ 已生成 {len(self.instances)} 个实例")
        print(f"  - Easy实例: {easy_instances_per_group * len(self.voxel_groups)} 个")
        print(f"  - Hard实例: {hard_instances_per_group * len(self.voxel_groups)} 个")
    
    def _resample_voxel_group(self, original_group):
        """为给定组重新采样s1、s2和s3，保持s0不变"""
        # 获取对应的原始形状数据
        shape = self.chiral_data[original_group.group_id]
        variants = shape['variants']
        
        # s0保持不变
        s0 = original_group.voxels[0]
        
        # 重新采样s1: 从3个mirror中随机选择一个
        mirror_variants = ['xoy_mirror', 'xoz_mirror', 'yoz_mirror']
        available_mirrors = [v for v in mirror_variants if v in variants]
        if available_mirrors:
            selected_mirror_s1 = random.choice(available_mirrors)
            s1 = variants[selected_mirror_s1]['voxels']
        else:
            s1 = s0.copy()
            selected_mirror_s1 = None
        
        # 重新采样s2: 从除了s1的两个mirror中随机选择一个
        remaining_mirrors = [v for v in available_mirrors if v != selected_mirror_s1]
        if remaining_mirrors:
            selected_mirror_s2 = random.choice(remaining_mirrors)
            s2 = variants[selected_mirror_s2]['voxels']
        else:
            s2 = s0.copy()
        
        # 重新采样s3: 从remove/move变体中随机选择一个
        modify_variants = ['remove', 'move']
        available_modifies = [v for v in modify_variants if v in variants]
        if available_modifies:
            selected_modify = random.choice(available_modifies)
            s3 = variants[selected_modify]['voxels']
        else:
            s3 = s0.copy()
        
        # 创建新的voxel组
        new_group = VoxelGroup(
            group_id=original_group.group_id,
            voxels=[s0, s1, s2, s3],
            voxel_count=4
        )
        
        return new_group
        
    def generate_configs(self):
        """生成所有MRT配置"""
        for instance in self.instances:
            group_id = instance.voxel_group.group_id
            instance_id = instance.instance_id
            difficulty = instance.difficulty
            voxels = instance.voxel_group.voxels
            visual_config = instance.visual_config
            rotation_configs = instance.rotation_configs
            
            # 生成video配置（每个instance固定）
            video_config = self._generate_video_config()
            
            if difficulty == "Easy":
                # Easy: 所有voxel + 1个rotation
                rotation_config = rotation_configs[0]
                for voxel_idx, voxel_data in enumerate(voxels):
                    config = MRTConfig(
                        group_id=group_id,
                        instance_id=instance_id,
                        voxel_index=voxel_idx,
                        rotation_index=0,
                        voxel_data=voxel_data,
                        visual_config=visual_config,
                        rotation_config=rotation_config,
                        video_config=video_config,
                        output_config=self._generate_output_config(group_id, instance_id, voxel_idx, 0, difficulty),
                        difficulty=difficulty
                    )
                    self.configs.append(config)
                    
            else:  # Hard
                # Hard: (0,0)(1,1)(2,2)(3,3)(0,1)(0,2)(0,3)
                hard_combinations = [
                    (0, 0),  # s0r0
                    (1, 1),  # s1r1
                    (2, 2),  # s2r2
                    (3, 3),  # s3r3
                    (0, 1),  # s0r1
                    (0, 2),  # s0r2
                    (0, 3),  # s0r3
                ]
                
                for voxel_idx, rotation_idx in hard_combinations:
                    if voxel_idx < len(voxels) and rotation_idx < len(rotation_configs):
                        config = MRTConfig(
                            group_id=group_id,
                            instance_id=instance_id,
                            voxel_index=voxel_idx,
                            rotation_index=rotation_idx,
                            voxel_data=voxels[voxel_idx],
                            visual_config=visual_config,
                            rotation_config=rotation_configs[rotation_idx],
                            video_config=video_config,
                            output_config=self._generate_output_config(group_id, instance_id, voxel_idx, rotation_idx, difficulty),
                            difficulty=difficulty
                        )
                        self.configs.append(config)
                        
        print(f"✓ 已生成 {len(self.configs)} 个MRT配置")
        
    def _generate_visual_config(self) -> Dict[str, Any]:
        """生成visual配置（标准字段，匹配 CubeVisualConfig）"""
        return {
            "cube_size": round(random.uniform(*CUBE_SIZE_RANGE), 2),
            "spacing": round(random.uniform(*SPACING_RANGE), 2),
            "fill_color": random.choice(FILL_COLOR_POOL),
            "fill_opacity": round(random.uniform(*FILL_OPACITY_RANGE), 2),
            "stroke_color": random.choice(STROKE_COLOR_POOL),
            "stroke_width": round(random.uniform(*STROKE_WIDTH_RANGE), 2),
            "stroke_opacity": round(random.uniform(*STROKE_OPACITY_RANGE), 2)
        }
        
    def _generate_rotation_config(self) -> Dict[str, Any]:
        """生成rotation配置"""
        # 先随机选择旋转模式
        rotation_mode = random.choice(["axis", "random"])
        
        if rotation_mode == "axis":
            # axis模式：从xyz轴单位向量中随机选择
            axis_vectors = [
                [1, 0, 0],  # x轴
                [0, 1, 0],  # y轴
                [0, 0, 1]   # z轴
            ]
            rotation_vector = random.choice(axis_vectors)
        else:
            # random模式：生成随机单位旋转向量
            rotation_vector = np.random.randn(3)
            rotation_vector = rotation_vector / np.linalg.norm(rotation_vector)
            rotation_vector = list(rotation_vector)
        
        return {
            "rotation_vector": rotation_vector,
            "rotation_angle": round(random.uniform(*ROTATION_ANGLES_RANGE), 1),
            "clockwise": random.choice(CLOCKWISE_OPTIONS),
            "rotation_speed": random.choice(ROTATION_SPEEDS),
            "rate_func": "linear",
            "center_mode": random.choice(CENTER_MODES),
            "duration": None
        }
        
    def _generate_video_config(self) -> Dict[str, Any]:
        """生成video配置（可视化元素由白名单固定控制）"""
        whitelist = set(VISUAL_ELEMENTS_WHITELIST)
        
        # 从4个离散的theta范围中随机选择一个，然后在该范围内随机采样
        selected_range = random.choice(THETA_RANGES)
        theta = random.randint(*selected_range)
        
        return {
            "phi": random.randint(*PHI_RANGE),
            "theta": theta,
            "gamma": 0,
            "distance": None,
            "zoom": round(random.uniform(*ZOOM_RANGE), 2),
            "frame_width": None,
            "frame_height": None,
            "show_axes": "axes" in whitelist,
            "show_axes_labels": "axes_labels" in whitelist,
            "show_rotation_axis": "rotation_axis" in whitelist,
            "show_rotation_circle": "rotation_circle" in whitelist,
            "show_velocity_arrow": "velocity_arrow" in whitelist,
            "show_labels": "labels" in whitelist,
            "show_bounding_box": "bounding_box" in whitelist
        }
        
    def _generate_output_config(self, group_id: int, instance_id: int, voxel_idx: int, rotation_idx: int, difficulty: str) -> Dict[str, Any]:
        """生成output配置"""
        # 生成全局ID（基于实例在各自难度类型中的位置）
        # 对于Easy实例：global_id = 当前Easy实例在Easy实例中的序号 + 1
        # 对于Hard实例：global_id = 当前Hard实例在Hard实例中的序号 + 1
        
        # 计算当前实例在各自难度类型中的序号
        if difficulty == "Easy":
            # 计算当前Easy实例是第几个Easy实例
            easy_instances = [i for i in self.instances if i.difficulty == "Easy"]
            current_easy_index = next(i for i, inst in enumerate(easy_instances) if inst.voxel_group.group_id == group_id and inst.instance_id == instance_id)
            global_id = current_easy_index + 1
        else:  # Hard
            # 计算当前Hard实例是第几个Hard实例
            hard_instances = [i for i in self.instances if i.difficulty == "Hard"]
            current_hard_index = next(i for i, inst in enumerate(hard_instances) if inst.voxel_group.group_id == group_id and inst.instance_id == instance_id)
            global_id = current_hard_index + 1
        
        # 根据难度选择前缀
        prefix = "e" if difficulty == "Easy" else "h"
        
        return {
            "media_dir": ".",
            "video_dir": "videos",
            "image_dir": "images", 
            "tex_dir": "Tex",
            "meta_dir": ".",
            "filename": f"{prefix}{global_id:03d}_{group_id}_{instance_id}_s{voxel_idx}_r{rotation_idx}",
            "pixel_width": random.choice(PIXEL_WIDTHS),
            "pixel_height": random.choice(PIXEL_HEIGHTS),
            "frame_rate": random.choice(FRAME_RATES),
            "quality": None,
            "format": "mp4"
        }
        
    def save_configs(self, timestamp: str = None) -> Tuple[str, List[str]]:
        """保存所有配置文件"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 基于3dr目录的相对路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        batch_dir = os.path.join(script_dir, "medias", f"batch_{timestamp}")
        os.makedirs(batch_dir, exist_ok=True)
        
        # 创建子目录
        os.makedirs(os.path.join(batch_dir, "videos"), exist_ok=True)
        os.makedirs(os.path.join(batch_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(batch_dir, "Tex"), exist_ok=True)
        os.makedirs(os.path.join(batch_dir, "meta"), exist_ok=True)
        
        config_files = []
        meta_records = []
        
        for idx, config in enumerate(self.configs, 1):
            # 生成配置文件名 - 使用与_generate_output_config相同的全局ID逻辑
            prefix = "e" if config.difficulty == "Easy" else "h"
            
            # 计算全局ID（与_generate_output_config中的逻辑一致）
            if config.difficulty == "Easy":
                # 计算当前Easy实例是第几个Easy实例
                easy_instances = [i for i in self.instances if i.difficulty == "Easy"]
                current_easy_index = next(i for i, inst in enumerate(easy_instances) if inst.voxel_group.group_id == config.group_id and inst.instance_id == config.instance_id)
                global_id = current_easy_index + 1
            else:  # Hard
                # 计算当前Hard实例是第几个Hard实例
                hard_instances = [i for i in self.instances if i.difficulty == "Hard"]
                current_hard_index = next(i for i, inst in enumerate(hard_instances) if inst.voxel_group.group_id == config.group_id and inst.instance_id == config.instance_id)
                global_id = current_hard_index + 1
            
            filename = f"mrt_{prefix}{global_id:03d}_{config.group_id}_{config.instance_id}_s{config.voxel_index}_r{config.rotation_index}.json"
            filepath = os.path.join(batch_dir, filename)
            
            # 绝对路径输出到当前批次目录
            batch_dir_abs = os.path.abspath(batch_dir)
            media_dir_abs = batch_dir_abs
            video_dir_abs = os.path.join(batch_dir_abs, "videos")
            image_dir_abs = os.path.join(batch_dir_abs, "images")
            tex_dir_abs = os.path.join(batch_dir_abs, "Tex")
            meta_dir_abs = os.path.join(batch_dir_abs, "meta")

            # 转换为字典格式
            config_dict = {
                "voxel": {
                    "type": "coordinates",
                    "data": config.voxel_data,
                    "grid_size": [4] * 3,  # 固定为4x4x4网格
                    "visual": config.visual_config
                },
                "rotation": config.rotation_config,
                "video": config.video_config,
                "output": {
                    **config.output_config,
                    "media_dir": media_dir_abs,
                    "video_dir": video_dir_abs,
                    "image_dir": image_dir_abs,
                    "tex_dir": tex_dir_abs,
                    "meta_dir": meta_dir_abs,
                }
            }
            
            # 保存配置文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            config_files.append(filepath)
            
            # 记录元数据
            meta_record = {
                "config_id": idx,
                "config_file": filename,
                "group_id": config.group_id,
                "instance_id": config.instance_id,
                "voxel_index": config.voxel_index,
                "rotation_index": config.rotation_index,
                "voxel_data": config.voxel_data,
                "rotation_vector": config.rotation_config["rotation_vector"],
                "rotation_angle": config.rotation_config["rotation_angle"],
                "rotation_speed": config.rotation_config["rotation_speed"],
                "center_mode": config.rotation_config["center_mode"],
                "phi": config.video_config["phi"],
                "theta": config.video_config["theta"],
                "pixel_width": config.output_config["pixel_width"],
                "pixel_height": config.output_config["pixel_height"],
                "frame_rate": config.output_config["frame_rate"]
            }
            meta_records.append(meta_record)
        
        # 保存批量 meta 文件到 batch 目录下的 meta 文件夹
        meta_path = os.path.join(batch_dir, "meta", f"meta_mrt_{timestamp}.json")
        
        batch_meta = {
            "timestamp": timestamp,
            "total_configs": len(config_files),
            "total_groups": len(self.voxel_groups),
            "total_instances": len(self.instances),
            "configs": meta_records
        }
        
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(batch_meta, f, indent=2, ensure_ascii=False)
        
        print(f"✓ MRT配置已保存到: {batch_dir}")
        print(f"✓ Meta 文件已保存到: {meta_path}")
        print(f"  总计: {len(config_files)} 个配置文件")
        print(f"  Groups: {len(self.voxel_groups)}, Instances: {len(self.instances)}")
        
        return batch_dir, config_files

# ==================== 批量渲染器 ====================

class MRTBatchRenderer:
    """MRT批量渲染器"""
    
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.results = []
    
    def render_all(self, parallel: bool = False):
        """渲染所有配置"""
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from cube_stack_animation import create_video_from_config
        
        # 获取所有配置文件
        config_files = sorted(Path(self.config_dir).glob("mrt_*.json"))
        
        print(f"\n开始批量渲染 {len(config_files)} 个MRT配置...")
        
        for idx, config_file in enumerate(config_files, 1):
            print(f"\n[{idx}/{len(config_files)}] 渲染: {config_file.name}")
            try:
                result = create_video_from_config(str(config_file))
                self.results.append({
                    "config": str(config_file),
                    "output": result,
                    "status": "success"
                })
                print(f"  ✓ 完成: {result}")
            except Exception as e:
                print(f"  ✗ 失败: {e}")
                self.results.append({
                    "config": str(config_file),
                    "error": str(e),
                    "status": "failed"
                })
        
        # 统计结果
        success_count = sum(1 for r in self.results if r["status"] == "success")
        print(f"\n批量渲染完成:")
        print(f"  成功: {success_count}/{len(config_files)}")
        print(f"  失败: {len(config_files) - success_count}/{len(config_files)}")

# ==================== 主函数 ====================

def create_mrt_configs(chiral_json_path: str, 
                      easy_instances_per_group: int = 1,
                      hard_instances_per_group: int = 1) -> Tuple[str, List[str]]:
    """
    创建MRT配置文件
    
    Args:
        chiral_json_path: chiral JSON文件路径
        easy_instances_per_group: 每组生成的Easy实例数量
        hard_instances_per_group: 每组生成的Hard实例数量
        
    Returns:
        (batch_dir, config_files)
    """
    generator = MRTGenerator(chiral_json_path)
    
    # 加载数据并生成配置
    generator.load_chiral_data()
    generator.extract_voxel_groups()
    generator.generate_instances(easy_instances_per_group, hard_instances_per_group)
    generator.generate_configs()
    
    # 保存配置
    batch_dir, config_files = generator.save_configs()
    
    return batch_dir, config_files

def render_mrt_batch(batch_dir: str):
    """渲染MRT批量配置"""
    renderer = MRTBatchRenderer(batch_dir)
    renderer.render_all()
    return renderer.results

# ==================== 使用示例 ====================

if __name__ == "__main__":
    print("=" * 80)
    print("MRT Generator - 从Chiral JSON生成配置")
    print("=" * 80)
    
    # 设置路径 - 基于3dr目录的相对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    chiral_json_path = os.path.join(script_dir, "chiral_voxels_variants.json")
    
    print(f"\n【示例】从chiral JSON生成MRT配置")
    print(f"Chiral JSON: {chiral_json_path}")
    print(f"输出目录: {os.path.join(script_dir, 'medias', 'batch_<timestamp>')}")
    
    # 生成配置
    batch_dir, config_files = create_mrt_configs(
        chiral_json_path=chiral_json_path,
        easy_instances_per_group=EASY_INSTANCE_NUM, 
        hard_instances_per_group=HARD_INSTANCE_NUM  
    )
    
    print(f"\n✓ 配置文件已生成在: {batch_dir}")
    print(f"  共 {len(config_files)} 个配置文件")
    
    # 可选：渲染所有配置
    # print("\n开始批量渲染...")
    # results = render_mrt_batch(batch_dir)
    
    # print("\n" + "=" * 80)
    # print("✓ MRT配置生成完成")
    # print("=" * 80)
    # print("\n生成规则：")
    # print("  - Easy实例: 所有voxel(s0,s1,s2,s3) + 1个rotation(r0)")
    # print("  - Hard实例: s0r1, s0r2, s1r2, s2r3")
    # print("  - 命名格式: group_id_instance_id_sx_rx.mp4")
    # print("=" * 80)