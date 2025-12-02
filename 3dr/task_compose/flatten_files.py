#!/usr/bin/env python3
"""
平铺脚本：将batch目录下所有instance的task和guidance文件提取到平铺目录

用法:
    python flatten_files.py <batch_path> [--output <new_path>]
"""

import argparse
import shutil
from pathlib import Path
from typing import Optional
import re


def flatten_batch_files(
    batch_path: Path,
    output_path: Optional[Path] = None,
    types: list = None
) -> None:
    """
    将batch目录下所有instance的指定类型文件平铺到目标目录
    
    Args:
        batch_path: 原始batch目录路径
        output_path: 输出目录路径，如果为None则使用batch_path
        types: 要平铺的类型列表，可选值：'task', 'guidance', 'meta'
    """
    if types is None:
        types = ['task']
    
    # 验证类型
    valid_types = {'task', 'guidance', 'meta'}
    invalid_types = set(types) - valid_types
    if invalid_types:
        raise ValueError(f"无效的类型: {invalid_types}。有效类型: {valid_types}")
    
    batch_path = Path(batch_path)
    if not batch_path.exists():
        raise FileNotFoundError(f"Batch目录不存在: {batch_path}")
    
    # 确定输出路径
    if output_path is None:
        output_path = batch_path
    else:
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"源目录: {batch_path}")
    print(f"目标目录: {output_path}")
    print(f"平铺类型: {', '.join(types)}")
    print("=" * 70)
    
    # 查找所有instance目录（mrt_e* 或 mrt_h*）
    instance_pattern = re.compile(r'^mrt_[eh]\d{3}$')
    instance_dirs = [d for d in batch_path.iterdir() 
                     if d.is_dir() and instance_pattern.match(d.name)]
    
    print(f"找到 {len(instance_dirs)} 个instance目录")
    
    # 统计信息
    copied_task = 0
    copied_guidance = 0
    copied_meta = 0
    skipped_task = 0
    skipped_guidance = 0
    skipped_meta = 0
    
    # 处理每个instance
    for instance_dir in sorted(instance_dirs):
        instance_id = instance_dir.name
        print(f"\n处理 {instance_id}...")
        
        # 处理task目录
        if 'task' in types:
            task_dir = instance_dir / 'task'
            if task_dir.exists() and task_dir.is_dir():
                task_files = list(task_dir.glob('*'))
                for task_file in task_files:
                    if task_file.is_file():
                        target_file = output_path / task_file.name
                        
                        if target_file.exists():
                            print(f"  跳过（已存在）: {task_file.name}")
                            skipped_task += 1
                        else:
                            try:
                                shutil.copy2(task_file, target_file)
                                print(f"  ✓ 复制task: {task_file.name}")
                                copied_task += 1
                            except Exception as e:
                                print(f"  ✗ 复制失败: {task_file.name} - {e}")
            else:
                print(f"  (task目录不存在)")
        
        # 处理guidance目录
        if 'guidance' in types:
            guidance_dir = instance_dir / 'guidance'
            if guidance_dir.exists() and guidance_dir.is_dir():
                guidance_files = list(guidance_dir.glob('*'))
                for guidance_file in guidance_files:
                    if guidance_file.is_file():
                        target_file = output_path / guidance_file.name
                        
                        if target_file.exists():
                            print(f"  跳过（已存在）: {guidance_file.name}")
                            skipped_guidance += 1
                        else:
                            try:
                                shutil.copy2(guidance_file, target_file)
                                print(f"  ✓ 复制guidance: {guidance_file.name}")
                                copied_guidance += 1
                            except Exception as e:
                                print(f"  ✗ 复制失败: {guidance_file.name} - {e}")
            else:
                print(f"  (guidance目录不存在)")
        
        # 处理meta目录（仅.json文件）
        if 'meta' in types:
            meta_dir = instance_dir / 'meta'
            if meta_dir.exists() and meta_dir.is_dir():
                meta_files = list(meta_dir.glob('*.json'))
                for meta_file in meta_files:
                    if meta_file.is_file():
                        target_file = output_path / meta_file.name
                        
                        if target_file.exists():
                            print(f"  跳过（已存在）: {meta_file.name}")
                            skipped_meta += 1
                        else:
                            try:
                                shutil.copy2(meta_file, target_file)
                                print(f"  ✓ 复制meta: {meta_file.name}")
                                copied_meta += 1
                            except Exception as e:
                                print(f"  ✗ 复制失败: {meta_file.name} - {e}")
            else:
                print(f"  (meta目录不存在)")
    
    # 输出统计
    print("\n" + "=" * 70)
    print("平铺完成！")
    if 'task' in types:
        print(f"  复制task文件: {copied_task} 个")
        print(f"  跳过task文件: {skipped_task} 个（已存在）")
    if 'guidance' in types:
        print(f"  复制guidance文件: {copied_guidance} 个")
        print(f"  跳过guidance文件: {skipped_guidance} 个（已存在）")
    if 'meta' in types:
        print(f"  复制meta文件: {copied_meta} 个")
        print(f"  跳过meta文件: {skipped_meta} 个（已存在）")
    print(f"\n所有文件已平铺到: {output_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='将batch目录下所有instance的指定类型文件平铺到目标目录'
    )
    parser.add_argument(
        'batch_path',
        type=str,
        help='Batch目录路径'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='输出目录路径（默认：使用batch_path）'
    )
    parser.add_argument(
        '--type', '-t',
        type=str,
        choices=['task', 'guidance', 'meta'],
        nargs='+',
        default=None,
        help='平铺类型（可空格分隔多选）：task（默认）、guidance、meta'
    )
    
    args = parser.parse_args()
    
    batch_path = Path(args.batch_path)
    output_path = Path(args.output) if args.output else None
    
    # 处理类型参数，默认为 ['task']
    types = args.type if args.type else ['task']
    # 去重并保持顺序
    types = list(dict.fromkeys(types))
    
    flatten_batch_files(batch_path, output_path, types)


if __name__ == '__main__':
    main()

