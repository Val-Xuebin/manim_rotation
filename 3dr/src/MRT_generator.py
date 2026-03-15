#!/usr/bin/env python3
"""
MRT (Mental Rotation Task) config generator.

Reads chiral voxel JSON, builds voxel groups (s0=original, s1/s2=mirrors, s3=modify),
generates Easy/Hard instances with visual/rotation/video configs, and writes
per-config JSON files plus a batch meta JSON under medias/batch_<timestamp>/shape/.
"""
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

# ==================== Parameter ranges ====================
EASY_INSTANCE_NUM = 7  # per-group (e.g. 61*N)
HARD_INSTANCE_NUM = 7  # per-group

# Cube visual parameter ranges
CUBE_SIZE_RANGE = (0.8, 1.2)
SPACING_RANGE = (0.0, 0.0)
FILL_OPACITY_RANGE = (0.7, 0.9)
STROKE_WIDTH_RANGE = (1.0, 2.0)
STROKE_OPACITY_RANGE = (0.8, 1.0)

# Color pools for visual config
FILL_COLOR_POOL = ["BLUE", "RED", "GREEN", "ORANGE", "PINK", "PURPLE", "GRAY"]
STROKE_COLOR_POOL = ["WHITE", "BLACK"]

ROTATION_ANGLES_RANGE = (45, 135)  # degrees
ROTATION_SPEEDS = ["slow", "medium"]  # "slow", "medium", "fast"
CENTER_MODES = ["mass", "cube"]
CLOCKWISE_OPTIONS = [True, False]

# Video parameter ranges
PHI_RANGE = (65, 70)    # elevation (degrees)
THETA_RANGES = [(30, 60), (120, 150), (210, 240), (300, 330)]  # azimuth, 4 discrete ranges
ZOOM_RANGE = (1.2, 1.9)

# Visual elements whitelist (empty = none shown). Options: "axes", "axes_labels",
# "rotation_axis", "rotation_circle", "velocity_arrow", "labels", "bounding_box"
VISUAL_ELEMENTS_WHITELIST: List[str] = []

# Output config (720p @ 30fps)
PIXEL_WIDTHS = [1280]
PIXEL_HEIGHTS = [720]
FRAME_RATES = [30]

# ==================== Data structures ====================

@dataclass
class VoxelGroup:
    """One voxel group: s0 (original), s1, s2 (mirrors), s3 (modify)."""
    group_id: int
    voxels: List[List[List[int]]]  # s0, s1, s2, s3; each element is full voxel coords
    voxel_count: int


@dataclass
class Instance:
    """Single MRT instance (Easy or Hard) with one voxel group and rotation configs."""
    instance_id: int
    difficulty: str  # "Easy" or "Hard"
    voxel_group: VoxelGroup
    visual_config: Dict[str, Any]
    rotation_configs: List[Dict[str, Any]]  # Easy: 1; Hard: 4 (r0..r3)


@dataclass
class MRTConfig:
    """One render config: voxel index, rotation index, visual/video/output."""
    group_id: int
    instance_id: int
    voxel_index: int   # s0, s1, s2, s3
    rotation_index: int  # r0, r1, r2, r3
    voxel_data: List[int]
    visual_config: Dict[str, Any]
    rotation_config: Dict[str, Any]
    video_config: Dict[str, Any]
    output_config: Dict[str, Any]
    difficulty: str  # "Easy" or "Hard"


# ==================== MRT Generator ====================

class MRTGenerator:
    """Builds instances and per-config JSON from chiral voxel JSON."""

    def __init__(self, chiral_json_path: str):
        self.chiral_json_path = chiral_json_path
        self.chiral_data = None
        self.voxel_groups = []
        self.instances = []
        self.configs = []

    def load_chiral_data(self):
        """Load chiral JSON (list of shapes with variants)."""
        with open(self.chiral_json_path, 'r', encoding='utf-8') as f:
            self.chiral_data = json.load(f)
        print(f"Loaded chiral data: {len(self.chiral_data)} shapes")

    def extract_voxel_groups(self):
        """Extract voxel groups from chiral data; each group has 4 voxels (s0, s1, s2, s3)."""
        if not self.chiral_data:
            raise ValueError("Load chiral data first (call load_chiral_data)")
        shapes = self.chiral_data
        group_id = 0
        
        
        for shape in shapes:
            variants = shape['variants']
            
            # s0: original full structure (coordinate list)
            s0 = variants['original']['voxels']
            # s1: pick one of three mirror variants at random
            mirror_variants = ['xoy_mirror', 'xoz_mirror', 'yoz_mirror']
            available_mirrors = [v for v in mirror_variants if v in variants]
            if available_mirrors:
                selected_mirror_s1 = random.choice(available_mirrors)
                s1 = variants[selected_mirror_s1]['voxels']
            else:
                s1 = s0.copy()
                selected_mirror_s1 = None
            # s2: pick one of the remaining two mirrors
            remaining_mirrors = [v for v in available_mirrors if v != selected_mirror_s1]
            if remaining_mirrors:
                selected_mirror_s2 = random.choice(remaining_mirrors)
                s2 = variants[selected_mirror_s2]['voxels']
            else:
                s2 = s0.copy()
            # s3: pick one of remove/move variants
            modify_variants = ['remove', 'move']
            available_modifies = [v for v in modify_variants if v in variants]
            if available_modifies:
                selected_modify = random.choice(available_modifies)
                s3 = variants[selected_modify]['voxels']
            else:
                s3 = s0.copy()

            group_voxels = [s0, s1, s2, s3]
            voxel_group = VoxelGroup(
                group_id=group_id,
                voxels=group_voxels,
                voxel_count=4
            )
            self.voxel_groups.append(voxel_group)
            group_id += 1

        print(f"Extracted {len(self.voxel_groups)} voxel groups")

    def generate_instances(self, easy_instances_per_group: int = 1, hard_instances_per_group: int = 1):
        """Generate easy and hard instances per voxel group."""
        for group in self.voxel_groups:
            instance_id = 0
            for _ in range(easy_instances_per_group):
                new_group = self._resample_voxel_group(group)
                visual_config = self._generate_visual_config()
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
            for _ in range(hard_instances_per_group):
                new_group = self._resample_voxel_group(group)
                visual_config = self._generate_visual_config()
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
        print(f"Generated {len(self.instances)} instances")
        print(f"  Easy: {easy_instances_per_group * len(self.voxel_groups)}, Hard: {hard_instances_per_group * len(self.voxel_groups)}")

    def _resample_voxel_group(self, original_group):
        """Resample s1, s2, s3 for the group; keep s0 unchanged."""
        shape = self.chiral_data[original_group.group_id]
        variants = shape['variants']
        s0 = original_group.voxels[0]
        mirror_variants = ['xoy_mirror', 'xoz_mirror', 'yoz_mirror']
        available_mirrors = [v for v in mirror_variants if v in variants]
        if available_mirrors:
            selected_mirror_s1 = random.choice(available_mirrors)
            s1 = variants[selected_mirror_s1]['voxels']
        else:
            s1 = s0.copy()
            selected_mirror_s1 = None
        remaining_mirrors = [v for v in available_mirrors if v != selected_mirror_s1]
        if remaining_mirrors:
            selected_mirror_s2 = random.choice(remaining_mirrors)
            s2 = variants[selected_mirror_s2]['voxels']
        else:
            s2 = s0.copy()
        modify_variants = ['remove', 'move']
        available_modifies = [v for v in modify_variants if v in variants]
        if available_modifies:
            selected_modify = random.choice(available_modifies)
            s3 = variants[selected_modify]['voxels']
        else:
            s3 = s0.copy()
        new_group = VoxelGroup(
            group_id=original_group.group_id,
            voxels=[s0, s1, s2, s3],
            voxel_count=4
        )
        
        return new_group
        
    def generate_configs(self):
        """Build all MRT configs (one per voxel/rotation combination)."""
        for instance in self.instances:
            group_id = instance.voxel_group.group_id
            instance_id = instance.instance_id
            difficulty = instance.difficulty
            voxels = instance.voxel_group.voxels
            visual_config = instance.visual_config
            rotation_configs = instance.rotation_configs
            video_config = self._generate_video_config()
            if difficulty == "Easy":
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
                    
            else:  # Hard: (s0,r0)(s1,r1)(s2,r2)(s3,r3)(s0,r1)(s0,r2)(s0,r3)
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
        print(f"Generated {len(self.configs)} MRT configs")

    def _generate_visual_config(self) -> Dict[str, Any]:
        """Return visual config dict (fields match CubeVisualConfig)."""
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
        """Return rotation config: axis or random unit vector, angle, speed, center mode."""
        rotation_mode = random.choice(["axis", "random"])
        if rotation_mode == "axis":
            axis_vectors = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            rotation_vector = random.choice(axis_vectors)
        else:
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
        """Return video config; visual elements controlled by VISUAL_ELEMENTS_WHITELIST."""
        whitelist = set(VISUAL_ELEMENTS_WHITELIST)
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
        """Return output config; filename uses global index within difficulty (e001, h001, ...)."""
        if difficulty == "Easy":
            easy_instances = [i for i in self.instances if i.difficulty == "Easy"]
            current_easy_index = next(i for i, inst in enumerate(easy_instances) if inst.voxel_group.group_id == group_id and inst.instance_id == instance_id)
            global_id = current_easy_index + 1
        else:
            hard_instances = [i for i in self.instances if i.difficulty == "Hard"]
            current_hard_index = next(i for i, inst in enumerate(hard_instances) if inst.voxel_group.group_id == group_id and inst.instance_id == instance_id)
            global_id = current_hard_index + 1
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
        """Write all config JSONs and batch meta to medias/batch_<timestamp>/shape/."""
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # batch under project root (3dr/medias/), 2dr-style: shape (meta), img (task), video (guidance)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        batch_dir = os.path.join(project_root, "medias", f"batch_{timestamp}")
        os.makedirs(batch_dir, exist_ok=True)
        shape_dir = os.path.join(batch_dir, "shape")
        img_dir = os.path.join(batch_dir, "images")
        video_dir = os.path.join(batch_dir, "video")
        tex_dir = os.path.join(shape_dir, "tex")
        os.makedirs(shape_dir, exist_ok=True)
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(video_dir, exist_ok=True)

        batch_dir_abs = os.path.abspath(batch_dir)
        shape_dir_abs = os.path.abspath(shape_dir)
        tex_dir_abs = os.path.abspath(tex_dir)
        image_dir_abs = os.path.abspath(img_dir)
        video_dir_abs = os.path.abspath(video_dir)

        config_files = []
        meta_records = []

        for idx, config in enumerate(self.configs, 1):
            prefix = "e" if config.difficulty == "Easy" else "h"
            if config.difficulty == "Easy":
                easy_instances = [i for i in self.instances if i.difficulty == "Easy"]
                current_easy_index = next(i for i, inst in enumerate(easy_instances) if inst.voxel_group.group_id == config.group_id and inst.instance_id == config.instance_id)
                global_id = current_easy_index + 1
            else:
                hard_instances = [i for i in self.instances if i.difficulty == "Hard"]
                current_hard_index = next(i for i, inst in enumerate(hard_instances) if inst.voxel_group.group_id == config.group_id and inst.instance_id == config.instance_id)
                global_id = current_hard_index + 1

            filename = f"mrt_{prefix}{global_id:03d}_{config.group_id}_{config.instance_id}_s{config.voxel_index}_r{config.rotation_index}.json"
            filepath = os.path.join(shape_dir, filename)

            config_dict = {
                "voxel": {
                    "type": "coordinates",
                    "data": config.voxel_data,
                    "grid_size": [4] * 3,
                    "visual": config.visual_config
                },
                "rotation": config.rotation_config,
                "video": config.video_config,
                "output": {
                    **config.output_config,
                    "media_dir": batch_dir_abs,
                    "video_dir": video_dir_abs,
                    "image_dir": image_dir_abs,
                    "tex_dir": tex_dir_abs,
                    "meta_dir": shape_dir_abs,
                }
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

            config_files.append(filepath)
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
        
        meta_path = os.path.join(shape_dir, f"meta_mrt_{timestamp}.json")
        
        batch_meta = {
            "timestamp": timestamp,
            "total_configs": len(config_files),
            "total_groups": len(self.voxel_groups),
            "total_instances": len(self.instances),
            "configs": meta_records
        }
        
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(batch_meta, f, indent=2, ensure_ascii=False)
        print(f"MRT configs saved to: {batch_dir}")
        print(f"Meta file: {meta_path}")
        print(f"  Total configs: {len(config_files)}, Groups: {len(self.voxel_groups)}, Instances: {len(self.instances)}")
        return batch_dir, config_files


# ==================== Batch renderer ====================

class MRTBatchRenderer:
    """Renders all MRT config JSONs in a shape directory to videos."""

    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.results = []

    def render_all(self, parallel: bool = False):
        """Render all mrt_*.json configs in config_dir."""
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from cube_stack_animation import create_video_from_config
        config_files = sorted(Path(self.config_dir).glob("mrt_*.json"))
        print(f"\nRendering {len(config_files)} MRT configs...")
        for idx, config_file in enumerate(config_files, 1):
            print(f"[{idx}/{len(config_files)}] {config_file.name}")
            try:
                result = create_video_from_config(str(config_file))
                self.results.append({"config": str(config_file), "output": result, "status": "success"})
                print(f"  Done: {result}")
            except Exception as e:
                print(f"  Failed: {e}")
                self.results.append({"config": str(config_file), "error": str(e), "status": "failed"})
        success_count = sum(1 for r in self.results if r["status"] == "success")
        print(f"\nBatch done: success {success_count}/{len(config_files)}, failed {len(config_files) - success_count}/{len(config_files)}")


# ==================== Main API ====================

def create_mrt_configs(chiral_json_path: str,
                      easy_instances_per_group: int = 1,
                      hard_instances_per_group: int = 1) -> Tuple[str, List[str]]:
    """
    Create MRT configs from chiral JSON and save to medias/batch_<timestamp>/shape/.

    Args:
        chiral_json_path: Path to chiral voxel variants JSON.
        easy_instances_per_group: Number of Easy instances per voxel group.
        hard_instances_per_group: Number of Hard instances per voxel group.

    Returns:
        (batch_dir, list of config file paths).
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
    """Render all MRT configs in batch_dir (expects shape/ with mrt_*.json)."""
    renderer = MRTBatchRenderer(batch_dir)
    renderer.render_all()
    return renderer.results


if __name__ == "__main__":
    print("MRT Generator — build configs from chiral JSON")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    chiral_json_path = os.path.join(project_root, "chiral_voxels_variants.json")
    print(f"Chiral JSON: {chiral_json_path}")
    print(f"Output: {os.path.join(project_root, 'medias', 'batch_<timestamp>')}")
    batch_dir, config_files = create_mrt_configs(
        chiral_json_path=chiral_json_path,
        easy_instances_per_group=EASY_INSTANCE_NUM,
        hard_instances_per_group=HARD_INSTANCE_NUM
    )
    print(f"Configs written to: {batch_dir} ({len(config_files)} files)")