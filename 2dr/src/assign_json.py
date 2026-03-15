#!/usr/bin/env python3
# Assign: build MCQ JSONL from shape JSONs + rendered img/video. See README.md.

import json
import random
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Text templates (easy = rotation direction in prompt; hard = no direction)
EASY_QUESTION_TEMPLATE = """Given the original 2D grid pattern <visual>, which one of patterns shown in the following option can be obtained by rotating the original pattern {clockwise} for 90 degree?\nA. <visual> B. <visual> C. <visual> D. <visual>. Answer with one letter: A, B, C or D."""
HARD_QUESTION_TEMPLATE = """Given the original 2D grid pattern <visual>, which pattern shown in the following images can be obtained by rotating the original pattern?\nA. <visual> B. <visual> C. <visual> D. <visual>. Answer with one letter: A, B, C or D."""

# Reasoning templates
EASY_REASONING_TEMPLATE = '''<think>I will mentally rotate the original grid {clockwise} for 90 degree to see which option matches its orientation. <visual>
After visually imagine the pattern {clockwise} for 90 degree, option {answer} matches the rotated image in my imagination.
</think><answer>{answer}</answer>'''
HARD_REASONING_TEMPLATE = '''<think>Based on the initial observation, I will try to mentally rotate the original grid to align its orientation with the rest of the patterns and determine their equivalence.<visual>
After visually imagine the pattern {clockwise} for 90 degree, option {answer} matches the rotated image in my imagination.
</think><answer>{answer}</answer>'''

@dataclass
class TaskData:
    """Task data structure"""
    category: str  # 'easy' or 'hard'
    id: str  # instance ID like '2dr_0001'
    question: str
    assign: Dict[str, str]  # {'A': 'answer', 'B': 'mirror1', ...}
    images: List[str]  # List of image filenames
    guidance: List[str]  # List of video filenames
    answer: str
    reasoning: str
    video_length: float  # Video duration in seconds


def generate_assign_choices(s0_description: str, s1_to_s4_descriptions: List[str]) -> Dict[str, str]:
    """A–D: s0 plus 3 distinct from s1–s4, shuffled."""
    available = [d for d in s1_to_s4_descriptions if d is not None]
    available = list(set(available))
    if len(available) >= 3:
        selected = random.sample(available, 3)
    elif len(available) >= 1:
        selected = available.copy()
        while len(selected) < 3:
            selected.append(random.choice(available))
    else:
        selected = [s0_description] * 3
    selected.append(s0_description)
    random.shuffle(selected)
    return {'A': selected[0], 'B': selected[1], 'C': selected[2], 'D': selected[3]}


def get_image_order(assign: Dict[str, str], instance_id: str, available_variants: Dict[str, str]) -> List[str]:
    description_to_idx = {}
    for idx, description in available_variants.items():
        if description and description not in description_to_idx:
            description_to_idx[description] = idx
    image_list = [f'{instance_id}_0_first.jpg']
    for key in ['A', 'B', 'C', 'D']:
        variant_idx = description_to_idx.get(assign[key], '0')
        image_list.append(f'{instance_id}_{variant_idx}_last.jpg')
    return image_list


def determine_answer(assign: Dict[str, str]) -> str:
    for key, value in assign.items():
        if value == 'original':
            return f'{key}.'
    return 'A.'


def prepare_task_images(batch_dir: Path, instance_id: str, data: Dict) -> Optional[Dict[str, str]]:
    img_dir = batch_dir / 'img'
    video_dir = batch_dir / 'video'
    if not (img_dir / f'{instance_id}_0_first.jpg').exists() or not (img_dir / f'{instance_id}_0_last.jpg').exists():
        return None
    available_variants = {}
    for i in range(5):
        variant_key = f's{i}'
        if variant_key in data.get('variants', {}):
            description = data['variants'][variant_key].get('description')
            if description:
                available_variants[str(i)] = description
    if not (video_dir / f'{instance_id}_0.mp4').exists():
        return None
    for i in range(1, 5):
        if not (img_dir / f'{instance_id}_{i}_last.jpg').exists():
            return None
    return available_variants


def generate_task_data(batch_dir: Path, instance_id: str, category_override: Optional[str] = None) -> Optional[TaskData]:
    """Build one task row. category_override: 'easy'|'hard'|'mixed'|None (default easy)."""
    json_file = batch_dir / 'shape' / f'{instance_id}.json'
    if not json_file.exists():
        return None
    with open(json_file, 'r') as f:
        data = json.load(f)
    available_variants = prepare_task_images(batch_dir, instance_id, data)
    if available_variants is None:
        return None
    s0_description = available_variants.get("0", "original")
    s1_to_s4_descriptions = [available_variants.get(str(i), None) for i in range(1, 5)]
    assign = generate_assign_choices(s0_description, s1_to_s4_descriptions)
    rotation_info = data.get('rotation', {})
    direction_info = rotation_info.get('direction', {})
    clockwise_bool = direction_info.get('clockwise', True)
    clockwise_text = "clockwise" if clockwise_bool else "counter-clockwise"
    images = get_image_order(assign, instance_id, available_variants)
    if category_override in ("easy", "hard"):
        category = category_override
    elif category_override == "mixed":
        category = random.choice(["easy", "hard"])
    else:
        category = "easy"
    question = (EASY_QUESTION_TEMPLATE if category == 'easy' else HARD_QUESTION_TEMPLATE).format(clockwise=clockwise_text)
    for i, img in enumerate(images, 1):
        question = question.replace(f'<image{i}>', img)
    guidance = [f'{instance_id}_0.mp4']
    video_length = float(rotation_info.get("duration", 3.0))
    answer = determine_answer(assign)
    answer_letter = answer.replace('.', '')
    reasoning = (EASY_REASONING_TEMPLATE if category == 'easy' else HARD_REASONING_TEMPLATE).format(
        answer=answer_letter, clockwise=clockwise_text
    )
    return TaskData(
        category=category, id=instance_id, question=question, assign=assign,
        images=images, guidance=guidance, answer=answer, reasoning=reasoning, video_length=video_length,
    )


def generate_all_task_data(batch_dir: Path, output_file: Path, category_mix: Optional[str] = None) -> None:
    """Write assign_data.jsonl. Visual paths use batch_dir as prefix. category_mix: None|'easy'|'hard'|'mixed'."""
    instances = []
    shape_dir = batch_dir / 'shape'
    if not shape_dir.is_dir():
        print(f"Error: shape directory not found: {shape_dir}")
        return
    category_mix = category_mix or "easy"
    prefix = str(batch_dir.resolve())
    for json_file in sorted(shape_dir.glob('2dr_*.json')):
        instance_id = json_file.stem
        task_data = generate_task_data(batch_dir, instance_id, category_override=category_mix)
        if task_data:
            instances.append(task_data)
    instances.sort(key=lambda x: x.id)
    with open(output_file, 'w', encoding='utf-8') as f:
        for task in instances:
            visual_input = [{"type": "image", "path": f"{prefix}/img/{img_path}"} for img_path in task.images]
            visual_output = [{
                "type": "video", "path": f"{prefix}/video/{video_path}",
                "fps": 30, "video_start": 0.0, "video_end": task.video_length
            } for video_path in task.guidance]
            task_dict = {
                "category": task.category, "id": task.id, "text_input": task.question,
                "assign": task.assign, "visual_input": visual_input, "visual_output": visual_output,
                "answer": task.answer, "text_output": task.reasoning
            }
            f.write(json.dumps(task_dict, ensure_ascii=False) + '\n')
    print(f"Generated task data for {len(instances)} instances")
    print(f"Saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Generate 2DR task JSONL (assign_json). Visual paths use batch_dir as prefix.')
    parser.add_argument('batch_dir', type=str, help='Path to batch directory')
    parser.add_argument('--output', '-o', type=str, help='Output JSONL path (default: batch_dir/assign_data.jsonl)')
    parser.add_argument('--category', type=str, default='easy', choices=['easy', 'hard', 'mixed'], help='Task category')
    args = parser.parse_args()
    batch_dir = Path(args.batch_dir)
    if not batch_dir.exists():
        print(f"Error: Batch directory does not exist: {batch_dir}")
        return
    output_file = Path(args.output) if args.output else batch_dir / 'assign_data.jsonl'
    generate_all_task_data(batch_dir, output_file, category_mix=getattr(args, 'category', 'easy'))


if __name__ == '__main__':
    main()
