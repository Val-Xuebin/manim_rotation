#!/usr/bin/env python3
"""
Assign Template Generator for MRT Tasks
Generates text data for MCQ tasks based on rendered images and guidance videos.
"""

import json
import random
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

# Text templates
# QUESTION_TEMPLATE = """Given the original cubestack <image1>, which cubestack shown in the following images can be obtained by rotating or spining the original cubestack?\nA. <image2> B. <image3> C. <image4> D. <image5>. Answer with one letter: A, B, C or D."""
QUESTION_TEMPLATE = """Given the original cubestack <visual>, which cubestack shown in the following images can be obtained by rotating or spining the original cubestack?\nA. <visual> B. <visual> C. <visual> D. <visual>. Answer with one letter: A, B, C or D."""

# Path configuration: visual paths in assign_data.jsonl use batch_dir as prefix (batch_dir/images/, batch_dir/video/).
DEFAULT_FPS = 30
DEFAULT_VIDEO_START = 0.0

# Reasoning templates
# EASY_REASONING_TEMPLATE = '''<think>For Choice A, I need to visually imagine the rotation in the given cubestack to judge whether they are the same cubestack. {reason_a}; Choice B {reason_b}, Choice C {reason_c}, Choice D {reason_d}
EASY_REASONING_TEMPLATE = '''<think>Based on the initial observation, the original cubestack appears to be posed differently from the options. I will mentally rotate it to align its orientation with rest of the cubestacks and determine their equivalence.<visual>
Option A {reason_a};\nOption B {reason_b};\nOption C {reason_c};\nOption D {reason_d}.
</think><answer>{answer}</answer>'''

HARD_REASONING_TEMPLATE = '''Based on the initial observation, the original cubestack appears to be posed differently from the options. I will mentally rotate it to align its orientation with each candidate cubestack and determine if they are the same cubestack.
Option A {reason_a};\nOption B {reason_b};\nOption C {reason_c};\nOption D {reason_d}.
</think><answer>{answer}</answer>'''

# Reason templates for different option types
# EASY_REASONS = {
#     'answer': 'matches the rotated original cube in my imagination',
#     'mirror1': 'based on the rotation imagination, the cubestack is mirror-symmetric to the original and can not be obtained by rotating the original cube',
#     'mirror2': 'based on the rotation imagination, the cubestack is mirror-symmetric to the original and can not be obtained by rotating the original cube',
#     'move': 'is obtained by moving one cube\'s position',
#     'remove': 'misses one cube compared to the original cube, so it can not be obtained by rotating the original.'
# }

EASY_REASONS = {
    'answer': 'matches the rotated original structure in my imagination',
    'mirror1': 'based on my imagination, the cubestack is mirror-symmetric to the original and cannot be produced by any rotation',
    'mirror2': 'based on my imagination, the cubestack is mirror-symmetric to the original and cannot be obtained via rotating the original cube',
    'move': "structure is obtained by moving one cube from the original cubestack, so they aren't the same structure",
    'remove': 'misses one cube compared to the original structure so they aren’t the same cube and rotation-equivalent'
}

# HARD_REASONS = {
#     'answer': '<guidance_answer>\nAfter visually rotating the original cube, it matches the cubestack structure in the choice B;',
#     'mirror1': '<guidance_mirror1>\nAfter visually rotating the original, the cubestack of this option is mirror-symmetric to the original and cannot be obtained by rotating the original cubestack',
#     'mirror2': '<guidance_mirror2>\n the cubestack is mirror-symmetric to the original under my imagination rotation and cannot be obtained by rotating the original cubestack',
#     'move': {
#         'under_guidance': "<guidance_move> After visually imagine the original cubastack rotating to the same pose as the option, it is obvious that the option structure is obtained by moving one cube from the original structure, so it can't be produced through rotating the original",
#         'no_guidance': "structure is obtained by moving one cube from the original structure, so it can't be produced through rotating the original"
#     },
#     'remove': {
#         'under_guidance': '<guidance_remove> After visually imagine the original cubastack rotating to the same pose, I can notice that the option misses one cube compared to the original cubestack, so it cannot be obtained by rotating the original',
#         'no_guidance': 'misses one cube compared to the original cubestack, so it cannot be obtained by rotating the original'
#     },
# }

HARD_REASONS = {
    'answer': '<visual>\nAfter visually rotating the original cube, it matches the cubestack structure in the choice B',
    'mirror1': '<visual>\nAfter visually rotating the original, the cubestack of this option is mirror-symmetric to the original and cannot be obtained by rotating the original cubestack',
    'mirror2': '<visual>\n the cubestack is mirror-symmetric to the original under my imagination rotation and cannot be obtained by rotating the original cubestack',
    'move': {
        'under_guidance': "<visual> After visually imagine the original cubastack rotating to the same pose as the option, it is obvious that the option structure is obtained by moving one cube from the original structure, so it can't be produced through rotating the original",
        'no_guidance': "structure is obtained by moving one cube from the original structure, so it can't be produced through rotating the original"
    },
    'remove': {
        'under_guidance': '<visual> After visually imagine the original cubastack rotating to the same pose, I can notice that the option misses one cube compared to the original cubestack, so it cannot be obtained by rotating the original',
        'no_guidance': 'misses one cube compared to the original cubestack, so it cannot be obtained by rotating the original'
    },
}

@dataclass
class TaskData:
    """Task data structure"""
    category: str  # 'easy' or 'hard'
    id: str  # instance ID like 'mrt_h001'
    text_input: str
    assign: Dict[str, str]  # {'A': 'answer', 'B': 'mirror1', ...}
    visual_input: List[Dict[str, str]]
    visual_output: List[Dict[str, Any]]
    answer: str
    text_output: str


def generate_assign_choices(category: str, modify_type: str = "modify") -> Dict[str, str]:
    """
    Generate random ABCD assignment for images and guidance videos.
    
    Args:
        category: 'easy' or 'hard'
        modify_type: 'move' or 'remove' based on voxel count analysis
    
    Returns:
        Dictionary mapping A,B,C,D to image types
    """
    if category == 'easy':
        # Easy: answer, mirror1, mirror2, modify
        options = ['answer', 'mirror1', 'mirror2', modify_type]
        random.shuffle(options)
        return {
            'A': options[0],
            'B': options[1], 
            'C': options[2],
            'D': options[3]
        }
    else:  # hard
        # Hard: answer, mirror1, mirror2, modify
        options = ['answer', 'mirror1', 'mirror2', modify_type]
        random.shuffle(options)
        return {
            'A': options[0],
            'B': options[1],
            'C': options[2], 
            'D': options[3]
        }


def get_image_order(assign: Dict[str, str], instance_id: str) -> List[str]:
    """
    Get ordered list of image filenames based on assignment.
    
    Args:
        assign: ABCD assignment dictionary
        instance_id: Instance ID like 'mrt_h001'
    
    Returns:
        List of image filenames in order A,B,C,D
    """
    image_mapping = {
        'answer': f'{instance_id}_answer.jpg',
        'mirror1': f'{instance_id}_mirror1.jpg', 
        'mirror2': f'{instance_id}_mirror2.jpg',
        'move': f'{instance_id}_move.jpg',
        'remove': f'{instance_id}_remove.jpg',
        'modify': f'{instance_id}_modify.jpg'  # fallback
    }
    
    return [image_mapping[assign[key]] for key in ['A', 'B', 'C', 'D']]


def get_guidance_order(assign: Dict[str, str], instance_id: str, category: str, modify_type: str) -> List[str]:
    """
    Get ordered list of guidance video filenames based on assignment.
    
    Args:
        assign: ABCD assignment dictionary
        instance_id: Instance ID like 'mrt_h001'
        category: 'easy' or 'hard'
        modify_type: 'move' or 'remove'
    
    Returns:
        List of guidance filenames or '<no_guidance>' placeholders
    """
    if category == 'easy':
        # Easy only has one guidance video
        return [f'{instance_id}_guidance_easy.mp4']
    else:
        # Hard has guidance for each option
        guidance_mapping = {
            'answer': f'{instance_id}_guidance_answer.mp4',
            'mirror1': f'{instance_id}_guidance_mirror1.mp4',
            'mirror2': f'{instance_id}_guidance_mirror2.mp4',
            'move': f'{instance_id}_guidance_move.mp4',
            'remove': f'{instance_id}_guidance_remove.mp4',
            'modify': f'{instance_id}_guidance_modify.mp4'  # fallback
        }
        
        guidance_list = []
        for key in ['A', 'B', 'C', 'D']:
            option = assign[key]
            if option == modify_type:
                # For modify options, randomly choose guidance or no_guidance
                if random.choice([True, False]):
                    guidance_list.append(guidance_mapping[option])
                else:
                    guidance_list.append('<no_guidance>')
            else:
                guidance_list.append(guidance_mapping[option])
        
        return guidance_list


def determine_answer(assign: Dict[str, str]) -> str:
    """
    Determine the correct answer based on assignment.
    The answer is always the option that maps to 'answer'.
    
    Args:
        assign: ABCD assignment dictionary
    
    Returns:
        Answer string like 'A.' or 'B.'
    """
    for key, value in assign.items():
        if value == 'answer':
            return f'{key}.'
    return 'A.'  # fallback


def generate_reasoning(answer: str, category: str, assign: Dict[str, str], guidance: List[str]) -> str:
    """
    Generate reasoning text using appropriate template based on category and assignment.
    
    Args:
        answer: Answer string like 'A.'
        category: 'easy' or 'hard'
        assign: Dictionary mapping A,B,C,D to option types
        guidance: List of guidance videos or '<no_guidance>' placeholders
    
    Returns:
        Reasoning text
    """
    # Get reason templates based on category
    reasons_dict = EASY_REASONS if category == 'easy' else HARD_REASONS
    
    # Generate reasons for each choice
    reason_a = _get_reason_for_choice(assign['A'], reasons_dict, guidance[0] if len(guidance) > 0 else None)
    reason_b = _get_reason_for_choice(assign['B'], reasons_dict, guidance[1] if len(guidance) > 1 else None)
    reason_c = _get_reason_for_choice(assign['C'], reasons_dict, guidance[2] if len(guidance) > 2 else None)
    reason_d = _get_reason_for_choice(assign['D'], reasons_dict, guidance[3] if len(guidance) > 3 else None)
    
    # Choose template based on category
    template = EASY_REASONING_TEMPLATE if category == 'easy' else HARD_REASONING_TEMPLATE
    
    return template.format(
        answer=answer,
        reason_a=reason_a,
        reason_b=reason_b,
        reason_c=reason_c,
        reason_d=reason_d
    )


def _get_reason_for_choice(option_type: str, reasons_dict: Dict, guidance_item: str = None) -> str:
    """
    Get reason text for a specific option type.
    
    Args:
        option_type: Type of option ('answer', 'mirror1', 'mirror2', 'move', 'remove')
        reasons_dict: Dictionary containing reason templates
        guidance_item: Guidance video filename or '<no_guidance>'
    
    Returns:
        Reason text for the option
    """
    if option_type not in reasons_dict:
        return f"unknown option type: {option_type}"
    
    reason_template = reasons_dict[option_type]
    
    # For move/remove in hard mode, check if guidance is available
    if isinstance(reason_template, dict):
        if guidance_item == '<no_guidance>':
            return reason_template['no_guidance']
        else:
            return reason_template['under_guidance']
    else:
        return reason_template



def get_video_duration(video_path: Path) -> float:
    """
    Get video duration in seconds using ffprobe.
    
    Args:
        video_path: Path to video file
    
    Returns:
        Duration in seconds, or 2.0 as default if unavailable
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return 2.0  # Default duration


def _task_dir(instance_dir: Path) -> Path:
    """Task dir: instance_dir/task (legacy) or instance_dir (nested img/<id>)."""
    if (instance_dir / "task").is_dir():
        return instance_dir / "task"
    return instance_dir


def detect_modify_type(instance_dir: Path = None, batch_dir: Path = None, instance_id: str = None) -> str:
    """Detect move/remove by file existence. Use (batch_dir, instance_id) for flat layout."""
    if instance_id and batch_dir:
        img_dir = batch_dir / "images"
        if (img_dir / f"{instance_id}_move.jpg").exists():
            return "move"
        if (img_dir / f"{instance_id}_remove.jpg").exists():
            return "remove"
        return "modify"
    if instance_dir:
        task_dir = _task_dir(instance_dir)
        if (task_dir / f"{instance_dir.name}_move.jpg").exists():
            return "move"
        if (task_dir / f"{instance_dir.name}_remove.jpg").exists():
            return "remove"
    return "modify"


def generate_task_data(
    instance_dir: Path = None,
    batch_dir: Path = None,
    instance_id: str = None,
) -> Optional[TaskData]:
    """
    Generate task data. Flat (2dr-style): pass batch_dir + instance_id. Legacy: pass instance_dir.
    Visual paths use batch_dir as prefix (batch_dir/images/, batch_dir/video/).
    """
    if instance_id and batch_dir:
        pass
    elif instance_dir:
        instance_id = instance_dir.name
        batch_dir = instance_dir.parent.parent if (instance_dir.parent.name == "images") else instance_dir.parent
    else:
        return None

    prefix = str(batch_dir.resolve())

    if instance_id.startswith("mrt_e"):
        category = "easy"
    elif instance_id.startswith("mrt_h"):
        category = "hard"
    else:
        return None

    modify_type = detect_modify_type(instance_dir=instance_dir, batch_dir=batch_dir, instance_id=instance_id)

    assign = generate_assign_choices(category, modify_type)
    text_input = QUESTION_TEMPLATE
    option_images = get_image_order(assign, instance_id)
    image_filenames = [f"{instance_id}_question.jpg"] + option_images

    img_dir = batch_dir / "images"
    video_dir = batch_dir / "video"
    flat = instance_dir is None
    if flat:
        visual_input = [{"type": "image", "path": f"{prefix}/images/{fn}"} for fn in image_filenames]
        guidance_filenames = get_guidance_order(assign, instance_id, category, modify_type)
        visual_output = []
        for guidance_filename in guidance_filenames:
            if guidance_filename == "<no_guidance>":
                continue
            video_path_obj = video_dir / guidance_filename
            video_duration = get_video_duration(video_path_obj) if video_path_obj.exists() else 2.0
            visual_output.append({
                "type": "video",
                "path": f"{prefix}/video/{guidance_filename}",
                "fps": DEFAULT_FPS,
                "video_start": DEFAULT_VIDEO_START,
                "video_end": video_duration,
            })
    else:
        guidance_dir = batch_dir / "video" / instance_id if (batch_dir / "video" / instance_id).is_dir() else (instance_dir / "guidance")
        nested = (batch_dir / "video" / instance_id).is_dir()
        visual_input = []
        for img_filename in image_filenames:
            path = f"{prefix}/images/{instance_id}/{img_filename}" if nested else f"{prefix}/{instance_id}/task/{img_filename}"
            visual_input.append({"type": "image", "path": path})
        guidance_filenames = get_guidance_order(assign, instance_id, category, modify_type)
        visual_output = []
        for guidance_filename in guidance_filenames:
            if guidance_filename == "<no_guidance>":
                continue
            video_path_obj = guidance_dir / guidance_filename
            video_duration = get_video_duration(video_path_obj) if video_path_obj.exists() else 2.0
            path = f"{prefix}/video/{instance_id}/{guidance_filename}" if nested else f"{prefix}/{instance_id}/guidance/{guidance_filename}"
            visual_output.append({
                "type": "video",
                "path": path,
                "fps": DEFAULT_FPS,
                "video_start": DEFAULT_VIDEO_START,
                "video_end": video_duration,
            })

    answer = determine_answer(assign)
    text_output = generate_reasoning(answer, category, assign, guidance_filenames)

    return TaskData(
        category=category,
        id=instance_id,
        text_input=text_input,
        assign=assign,
        visual_input=visual_input,
        visual_output=visual_output,
        answer=answer,
        text_output=text_output,
    )


def generate_all_task_data(batch_dir: Path, output_file: Path, limit_easy: int = None, limit_hard: int = None) -> None:
    """
    Generate task data for all instances in a batch. Visual paths use batch_dir as prefix.
    """
    instances = []
    easy_count = 0
    hard_count = 0

    shape_dir = batch_dir / "shape"
    if shape_dir.is_dir():
        import re
        configs = list(shape_dir.glob("mrt_*.json"))
        instance_ids = sorted(set(m.group(1) for p in configs for m in [re.match(r"^(mrt_[eh]\d{3})_", p.name)] if m))
        for inst_id in instance_ids:
            if inst_id.startswith("mrt_e"):
                if limit_easy is not None and easy_count >= limit_easy:
                    continue
                easy_count += 1
            else:
                if limit_hard is not None and hard_count >= limit_hard:
                    continue
                hard_count += 1
            task_data = generate_task_data(batch_dir=batch_dir, instance_id=inst_id)
            if task_data:
                instances.append(task_data)
    else:
        img_dir = batch_dir / "images"
        iter_dir = img_dir if img_dir.is_dir() else batch_dir
        for item in sorted(iter_dir.iterdir(), key=lambda x: x.name):
            if item.is_dir() and (item.name.startswith("mrt_e") or item.name.startswith("mrt_h")):
                if item.name.startswith("mrt_e"):
                    if limit_easy is not None and easy_count >= limit_easy:
                        continue
                    easy_count += 1
                else:
                    if limit_hard is not None and hard_count >= limit_hard:
                        continue
                    hard_count += 1
                task_data = generate_task_data(instance_dir=item)
                if task_data:
                    instances.append(task_data)
    
    # Sort instances by ID
    instances.sort(key=lambda x: x.id)
    
    # Save to JSONL file (one JSON object per line)
    with open(output_file, 'w', encoding='utf-8') as f:
        for task in instances:
            task_dict = {
                "category": task.category,
                "id": task.id,
                "text_input": task.text_input,
                "assign": task.assign,
                "visual_input": task.visual_input,
                "visual_output": task.visual_output,
                "answer": task.answer,
                "text_output": task.text_output
            }
            f.write(json.dumps(task_dict, ensure_ascii=False) + "\n")
    
    print(f"Generated task data for {len(instances)} instances")
    print(f"Saved to: {output_file}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Generate assign template data for MRT tasks')
    parser.add_argument('batch_dir', type=str, help='Path to batch directory')
    parser.add_argument('--output', '-o', type=str, help='Output JSONL file path (default: batch_dir/assign_data.jsonl)')
    parser.add_argument('--fps', type=int, default=30, help='Frame rate for videos (default: 30)')
    
    args = parser.parse_args()
    
    batch_dir = Path(args.batch_dir)
    if not batch_dir.exists():
        print(f"Error: Batch directory does not exist: {batch_dir}")
        return
    
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = batch_dir / 'assign_data.jsonl'
    
    global DEFAULT_FPS
    DEFAULT_FPS = args.fps
    generate_all_task_data(batch_dir, output_file)


if __name__ == '__main__':
    main()