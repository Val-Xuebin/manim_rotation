#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Union


def render_video(config_path: Path, config_data: dict = None, save_meta: bool = True) -> Path:
    """调用现有渲染入口渲染视频，返回视频绝对路径"""
    import sys, os
    # 将项目根目录加入路径：当前文件位于 MRT/renderer.py → 根目录是上一级的上一级
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)  # MRT-CubeStack
    sys.path.insert(0, project_root)
    from cube_stack_animation import create_video_from_config
    
    if config_data is not None:
        # 使用修改后的配置数据创建临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
            temp_config_path = f.name
        result_path = create_video_from_config(temp_config_path, save_meta=save_meta)
        os.unlink(temp_config_path)  # 删除临时文件
    else:
        result_path = create_video_from_config(str(config_path), save_meta=save_meta)
    return Path(result_path)


def find_actual_video_path(expected_path: Path, video_dir: str) -> Path:
    """
    查找实际视频文件路径
    因为 Manim 可能将视频保存到子目录中
    """
    if expected_path.exists():
        return expected_path
    
    # 尝试各种可能的路径
    possible_paths = [
        expected_path,
        Path(video_dir) / "videos" / "720p30" / expected_path.name,
        Path(video_dir) / "videos" / "1080p60" / expected_path.name,
        Path(video_dir) / "videos" / "480p15" / expected_path.name,
        Path(video_dir) / "videos" / "360p30" / expected_path.name,
        Path(video_dir) / expected_path.name,
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def extract_frame(video_path: Path, out_path: Path, select: str) -> bool:
    """
    使用 ffmpeg 抽取首/末帧。
    select: 'first' or 'last'
    """
    try:
        if select == "first":
            # 抽取第一帧
            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-frames:v", "1",
                str(out_path)
            ]
        else:
            # 抽取最后一帧（先获取总帧数，再定位），简化用 -sseof -1s 近似最后帧
            cmd = [
                "ffmpeg", "-y", "-sseof", "-0.04", "-i", str(video_path),
                "-frames:v", "1",
                str(out_path)
            ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def render_folder(
    folder: Path,
    modes: List[str],
    limit: int = None,
    *,
    image_output_dir: Optional[Union[str, Path]] = None,
    skip_default_images: bool = False,
) -> None:
    folder = Path(folder)
    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder}")

    # 仅渲染该目录下的 json
    json_files = sorted(folder.glob("*.json"))
    if limit is not None:
        json_files = json_files[:max(0, int(limit))]
    print(f"找到 {len(json_files)} 个配置")

    for idx, cfg in enumerate(json_files, 1):
        print(f"[{idx}/{len(json_files)}] {cfg.name}")
        
        # 读取配置
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            output_config = data.get("output", {})
            video_dir = output_config.get("video_dir", "videos")
            image_dir = output_config.get("image_dir", "images")
            filename = output_config.get("filename", "output")
        except Exception as e:
            print(f"  ✗ 配置读取失败: {e}")
            continue

        # 确保输出目录存在
        Path(video_dir).mkdir(parents=True, exist_ok=True)
        Path(image_dir).mkdir(parents=True, exist_ok=True)

        video_path = None
        if "video" in modes:
            try:
                video_path = render_video(cfg, data)
                print(f"  ✓ 视频: {video_path}")
            except Exception as e:
                print(f"  ✗ 渲染失败: {e}")

        # 若需要抽帧，但还没渲染视频，则尝试先渲染视频（只供抽帧）
        if ("first" in modes or "last" in modes) and video_path is None:
            # 抑制 Manim 渲染阶段在批次目录下生成 images/meta/videos：改写临时输出路径
            try:
                import tempfile
                import copy
                import shutil as _shutil
                temp_root = Path(tempfile.mkdtemp(prefix="render_tmp_"))
                temp_images = temp_root / "images"
                temp_meta = temp_root / "meta"
                temp_videos = temp_root / "videos"
                temp_images.mkdir(parents=True, exist_ok=True)
                temp_meta.mkdir(parents=True, exist_ok=True)
                temp_videos.mkdir(parents=True, exist_ok=True)

                data_for_video = copy.deepcopy(data)
                data_for_video.setdefault("output", {})
                # 覆盖所有输出目录，避免在批次目录下生成任何文件
                data_for_video["output"]["image_dir"] = str(temp_images)
                data_for_video["output"]["meta_dir"] = str(temp_meta)
                data_for_video["output"]["video_dir"] = str(temp_videos)

                video_path = render_video(cfg, data_for_video, save_meta=False)
                print(f"  ✓ 视频(供抽帧): {video_path}")
                # 渲染完成后清理临时目录（不影响已生成的视频文件）
                try:
                    _shutil.rmtree(temp_root, ignore_errors=True)
                except Exception:
                    pass
            except Exception as e:
                print(f"  ✗ 渲染失败(抽帧用): {e}")

        # 抽取首/末帧到指定的 image_dir
        if video_path and video_path.exists():
            base = video_path.stem  # 不含扩展名
            # 目标图片目录：允许覆盖；如覆盖且 skip_default_images=True，则仅保存到覆盖目录
            override_dir = Path(image_output_dir) if image_output_dir is not None else None
            target_dir_default = Path(image_dir)
            targets = []
            if "first" in modes:
                targets.append(("first", f"{base}_first.jpg"))
            if "last" in modes:
                targets.append(("last", f"{base}_last.jpg"))

            for select, fname in targets:
                wrote = False
                # 优先覆盖目录
                if override_dir is not None:
                    override_dir.mkdir(parents=True, exist_ok=True)
                    out_path = override_dir / fname
                    if extract_frame(video_path, out_path, select):
                        print(f"  ✓ {select}帧(override): {out_path}")
                        wrote = True
                    else:
                        print(f"  ✗ {select}帧抽取失败(override)")
                # 默认目录（如未要求跳过，或覆盖失败时兜底）
                if (not skip_default_images) and (not wrote or image_output_dir is None):
                    target_dir_default.mkdir(parents=True, exist_ok=True)
                    out_path_def = target_dir_default / fname
                    if extract_frame(video_path, out_path_def, select):
                        print(f"  ✓ {select}帧: {out_path_def}")
                    else:
                        print(f"  ✗ {select}帧抽取失败")
        else:
            # 如果返回的路径不存在，尝试查找实际视频文件
            if video_path:
                actual_video_path = find_actual_video_path(video_path, video_dir)
                if actual_video_path and actual_video_path.exists():
                    base = actual_video_path.stem  # 不含扩展名
                    if "first" in modes:
                        out_first = Path(image_dir) / f"{base}_first.jpg"
                        if extract_frame(actual_video_path, out_first, "first"):
                            print(f"  ✓ 首帧: {out_first}")
                        else:
                            print("  ✗ 首帧抽取失败")
                    if "last" in modes:
                        out_last = Path(image_dir) / f"{base}_last.jpg"
                        if extract_frame(actual_video_path, out_last, "last"):
                            print(f"  ✓ 末帧: {out_last}")
                        else:
                            print("  ✗ 末帧抽取失败")
                else:
                    print("  ✗ 无法找到实际视频文件")


def main():
    parser = argparse.ArgumentParser(description="渲染指定文件夹下的 MRT JSON 配置")
    parser.add_argument("folder", type=str, help="包含 JSON 的文件夹")
    parser.add_argument("--modes", nargs="+", default=["video"], choices=["video", "first", "last"],
                        help="选择生成的内容：video/first/last，可多选")
    parser.add_argument("--limit", type=int, default=None, help="只渲染前N个JSON")
    args = parser.parse_args()

    render_folder(Path(args.folder), args.modes, args.limit)


if __name__ == "__main__":
    main()

