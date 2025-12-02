#!/usr/bin/env python3
"""
Assign Task Generator for 2DR Tasks
Generates text data for MCQ tasks based on rendered images.
"""

import json
import random
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import shutil

# Text templates for 2DR tasks
EASY_QUESTION_TEMPLATE = """Given the original 2D grid pattern <viusal>, which one of patterns shown in the following option can be obtained by rotating the original pattern {clockwise} for 90 degree?\nA. <visual> B. <visual> C. <visual> D. <viusal>. Answer with one letter: A, B, C or D."""
HARD_QUESTION_TEMPLATE = """Given the original 2D grid pattern <viusal>, which pattern shown in the following images can be obtained by rotating the original pattern?\nA. <visual> B. <visual> C. <visual> D. <viusal>. Answer with one letter: A, B, C or D."""

# Reasoning templates
EASY_REASONING_TEMPLATE = '''<think>I will mentally rotate the original grid {clockwise} for 90 degree to see which option matches its orientation. <visual>
After visually imagine the pattern {clockwise} for 90 degree, option {answer} matches the rotated image in my imagination.
</think><answer>{answer}</answer>'''
HARD_REASONING_TEMPLATE = '''<think>Based on the initial observation, I will try to mentally rotate the original grid to align its orientation with the rest of the patterns and determine their equivalence.<visual>
After visually imagine the pattern {clockwise} for 90 degree, option {answer} matches the rotated image in my imagination.
</think><answer>{answer}</answer>'''

# '''
# answer: OptionA/B/C/D the corresponding opiton of answer
# clockwise: if clockwise -> clockwise; false -> counter-clockwise
# '''

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
    """
    Generate ABCD assignment: s0 + 3 unique random from s1-s4.
    
    Logic:
    - s0 (0_last.jpg) is ALWAYS included as one option
    - Randomly sample 3 unique variants from s1-s4
    - Shuffle to randomize positions
    
    Args:
        s0_description: Description of s0 ('original')
        s1_to_s4_descriptions: List of descriptions for s1-s4
    
    Returns:
        Dictionary mapping A,B,C,D to variant descriptions (s0 + 3 from s1-s4)
    """
    # Get unique available descriptions from s1-s4
    available = [d for d in s1_to_s4_descriptions if d is not None]
    available = list(set(available))  # Remove duplicates
    
    # Sample 3 unique from s1-s4
    if len(available) >= 3:
        # Enough options: random sample 3
        selected = random.sample(available, 3)
    elif len(available) >= 1:
        # Not enough unique options: use all + fill with duplicates
        selected = available.copy()
        while len(selected) < 3:
            selected.append(random.choice(available))
    else:
        # No s1-s4 options (shouldn't happen in practice)
        selected = [s0_description] * 3
    
    # Always include s0
    selected.append(s0_description)
    
    # Shuffle to randomize positions
    random.shuffle(selected)
    
    return {
        'A': selected[0],
        'B': selected[1],
        'C': selected[2],
        'D': selected[3]
    }


def get_image_order(assign: Dict[str, str], instance_id: str, available_variants: Dict[str, str]) -> List[str]:
    """
    Get ordered list of image filenames based on assignment.
    Always starts with s0_first.jpg, then follows A,B,C,D order using s0_last and s1-s4 last images.
    
    Args:
        assign: ABCD assignment dictionary mapping to variant descriptions
        instance_id: Instance ID like '2dr_0001'
        available_variants: Dictionary mapping variant indices to variant descriptions
    
    Returns:
        List of image filenames: [s0_first, then A, B, C, D using last images]
    """
    # Create reverse mapping: description -> variant index
    description_to_idx = {}
    for idx, description in available_variants.items():
        if description and description not in description_to_idx:
            description_to_idx[description] = idx
    
    # Start with s0 first image (not the renamed question.jpg)
    image_list = [f'{instance_id}_0_first.jpg']
    
    # Then add A, B, C, D images using last images
    for key in ['A', 'B', 'C', 'D']:
        description = assign[key]
        # Find variant index for this description
        variant_idx = description_to_idx.get(description, '0')
        image_list.append(f'{instance_id}_{variant_idx}_last.jpg')
    
    return image_list


def determine_answer(assign: Dict[str, str]) -> str:
    """
    Determine the correct answer based on assignment.
    The answer is always the option that maps to 'original'.
    
    Args:
        assign: ABCD assignment dictionary mapping to descriptions
    
    Returns:
        Answer string like 'A.'
    """
    for key, value in assign.items():
        if value == 'original':
            return f'{key}.'
    return 'A.'  # fallback




def prepare_task_images(instance_dir: Path, instance_id: str, data: Dict) -> Optional[Dict[str, str]]:
    """
    Prepare task images by copying s0-s4 variants to task folder.
    
    Args:
        instance_dir: Path to instance directory
        instance_id: Instance ID like '2dr_0001'
        data: JSON data containing variants
    
    Returns:
        Dictionary mapping variant indices to descriptions or None if required files missing
    """
    # Check if required files exist (s0 first and last)
    s0_first = instance_dir / f'{instance_id}_0_first.jpg'
    s0_last = instance_dir / f'{instance_id}_0_last.jpg'
    if not s0_first.exists() or not s0_last.exists():
        return None
    
    # Create task directory
    task_dir = instance_dir / 'task'
    task_dir.mkdir(exist_ok=True)
    
    # Collect descriptions from JSON data (regardless of mode)
    available_variants = {}
    for i in range(5):  # s0 to s4
        variant_key = f's{i}'
        if variant_key in data.get('variants', {}):
            description = data['variants'][variant_key].get('description')
            if description:
                available_variants[str(i)] = description
    
    # Copy s0-s4 last images if they exist
    for i in range(5):  # s0 to s4
        src_file = instance_dir / f'{instance_id}_{i}_last.jpg'
        if src_file.exists():
            dst_file = task_dir / f'{instance_id}_{i}_last.jpg'
            shutil.copy2(src_file, dst_file)
    
    # Copy s0 first image (keep original name, not rename to question.jpg)
    src_first = instance_dir / f'{instance_id}_0_first.jpg'
    if src_first.exists():
        dst_first = task_dir / f'{instance_id}_0_first.jpg'
        shutil.copy2(src_first, dst_first)
        # Also copy as question.jpg for compatibility
        dst_question = task_dir / f'{instance_id}_question.jpg'
        shutil.copy2(src_first, dst_question)
    
    # Copy s0 video
    src_video = instance_dir / f'{instance_id}_0.mp4'
    if src_video.exists():
        dst_video = task_dir / f'{instance_id}_0.mp4'
        shutil.copy2(src_video, dst_video)
    
    return available_variants


def generate_task_data(instance_dir: Path) -> Optional[TaskData]:
    """
    Generate task data for a single instance.
    
    Args:
        instance_dir: Path to instance directory
    
    Returns:
        TaskData object or None if instance is invalid
    """
    instance_id = instance_dir.name
    
    # Read JSON file
    json_file = instance_dir / f'{instance_id}.json'
    if not json_file.exists():
        return None
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Prepare task images
    available_variants = prepare_task_images(instance_dir, instance_id, data)
    if available_variants is None:
        return None
    
    # Separate s0 and s1-s4 descriptions
    s0_description = available_variants.get("0", "original")
    s1_to_s4_descriptions = [
        available_variants.get(str(i), None) 
        for i in range(1, 5)
    ]
    
    # Generate assignment (s0 + 3 random from s1-s4)
    assign = generate_assign_choices(s0_description, s1_to_s4_descriptions)
    
    # Get rotation direction info from JSON
    rotation_info = data.get('rotation', {})
    direction_info = rotation_info.get('direction', {})
    clockwise_bool = direction_info.get('clockwise', True)
    
    # Format clockwise text
    clockwise_text = "clockwise" if clockwise_bool else "counter-clockwise"
    
    # Get image order (s0_first + A,B,C,D last images)
    images = get_image_order(assign, instance_id, available_variants)
    
    # Randomly assign easy or hard category (50:50 distribution)
    category = random.choice(['easy']) # 'easy', 'hard'
    
    # Generate question based on category
    if category == 'easy':
        question = EASY_QUESTION_TEMPLATE.format(clockwise=clockwise_text)
    else:
        question = HARD_QUESTION_TEMPLATE
    
    # Replace <image1>...<image5> with actual filenames
    for i, img in enumerate(images, 1):
        question = question.replace(f'<image{i}>', img)
    
    # Video output is s0 video
    guidance = [f'{instance_id}_0.mp4']
    
    # Get video duration from JSON
    video_length = float(rotation_info.get("duration", 3.0))
    
    # Determine answer and reasoning
    answer = determine_answer(assign)
    answer_letter = answer.replace('.', '')  # Remove dot for template
    
    # Generate reasoning based on category
    if category == 'easy':
        reasoning = EASY_REASONING_TEMPLATE.format(
            answer=answer_letter,
            clockwise=clockwise_text
        )
    else:
        reasoning = HARD_REASONING_TEMPLATE.format(
            answer=answer_letter,
            clockwise=clockwise_text
        )
    
    return TaskData(
        category=category,  # Randomly assigned: 'easy' or 'hard'
        id=instance_id,
        question=question,
        assign=assign,
        images=images,
        guidance=guidance,
        answer=answer,
        reasoning=reasoning,
        video_length=video_length
    )


def generate_all_task_data(batch_dir: Path, output_file: Path, data_path: str, limit: int = None) -> None:
    """
    Generate task data for all instances in a batch.
    
    Args:
        batch_dir: Path to batch directory
        output_file: Path to output JSONL file (one JSON object per line)
        data_path: Base data path for jsonl output paths
        limit: Limit number of instances to process
    """
    instances = []
    count = 0
    
    # Find all instance directories
    for item in sorted(batch_dir.iterdir()):
        if item.is_dir() and item.name.startswith('2dr_'):
            # Check limit
            if limit is not None and count >= limit:
                continue
            
            task_data = generate_task_data(item)
            if task_data:
                instances.append(task_data)
                count += 1
    
    # Sort instances by ID
    instances.sort(key=lambda x: x.id)
    
    # Save to JSONL file (one JSON object per line)
    with open(output_file, 'w', encoding='utf-8') as f:
        for task in instances:
            # Format visual_input as object array
            visual_input = []
            for img_path in task.images:
                visual_input.append({
                    "type": "image",
                    "path": f"{data_path}/{task.id}/{img_path}"
                })
            
            # Format visual_output as object array
            visual_output = []
            for video_path in task.guidance:
                visual_output.append({
                    "type": "video",
                    "path": f"{data_path}/{task.id}/{video_path}",
                    "fps": 30,
                    "video_start": 0.0,
                    "video_end": task.video_length
                })
            
            task_dict = {
                "category": task.category,
                "id": task.id,
                "text_input": task.question,
                "assign": task.assign,
                "visual_input": visual_input,
                "visual_output": visual_output,
                "answer": task.answer,
                "text_output": task.reasoning
            }
            
            # Write each task as a single line JSON
            f.write(json.dumps(task_dict, ensure_ascii=False) + '\n')
    
    print(f"Generated task data for {len(instances)} instances")
    print(f"Saved to: {output_file}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Generate assign task data for 2DR tasks')
    parser.add_argument('batch_dir', type=str, help='Path to batch directory')
    parser.add_argument('--data-path', '-d', type=str, default='/root/autodl-fs/data/2dr-training', help='Base data path for jsonl output paths (default: /root/autodl-fs/data/2dr-training)')
    parser.add_argument('--output', '-o', type=str, help='Output JSONL file path (default: batch_dir/assign_data.jsonl)')
    parser.add_argument('--limit', '-l', type=int, help='Limit number of instances to process')
    
    args = parser.parse_args()
    
    batch_dir = Path(args.batch_dir)
    if not batch_dir.exists():
        print(f"Error: Batch directory does not exist: {batch_dir}")
        return
    
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = batch_dir / 'assign_data.jsonl'
    
    # Normalize data_path (remove trailing slash if present)
    data_path = args.data_path.rstrip('/')
    
    generate_all_task_data(batch_dir, output_file, data_path, args.limit)


if __name__ == '__main__':
    main()

