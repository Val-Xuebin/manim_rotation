#!/usr/bin/env python3
"""
Compose 3dr task: one image per task (question + answer + row Original|A|B|C|D).
Optional text_output below. Reads assign_data.jsonl, resolves paths to batch_dir/images/.
Out: composed_img/{id}_composed.jpg
"""
import argparse
import json
import re
from pathlib import Path
from typing import List, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("Requires Pillow: pip install Pillow")


def _resolve_img_path(batch_dir: Path, path_str: str) -> Path:
    """Resolve JSONL path to batch_dir/images/ (flat: .../images/file.jpg -> batch_dir/images/file.jpg)."""
    if "/images/" in path_str:
        suffix = path_str.split("/images/")[-1].strip()
        return batch_dir / "images" / suffix
    name = path_str.split("/")[-1].strip()
    tid = path_str.split("/")[-2].strip() if "/" in path_str else ""
    if tid and tid.startswith("mrt_"):
        return batch_dir / "images" / tid / name
    return batch_dir / "images" / name


def _text_width(draw, s: str, font) -> int:
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), s, font=font)
        return bbox[2] - bbox[0]
    if hasattr(draw, "textsize"):
        w, _ = draw.textsize(s, font=font)
        return w
    return len(s) * 8


def _wrap_text(draw, text: str, font, max_width: int) -> List[str]:
    lines = []
    for para in text.replace("\r", "").split("\n"):
        if not para.strip():
            lines.append("")
            continue
        words = re.split(r"(\s+)", para)
        line = ""
        for w in words:
            candidate = line + w
            if _text_width(draw, candidate, font) <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line.strip())
                line = w
        if line:
            lines.append(line.strip())
    return lines


def _draw_text_block(
    draw, xy: Tuple[int, int], text: str, font, max_width: int,
    line_height: int, fill=(0, 0, 0),
) -> int:
    """Draw wrapped text; return height used."""
    lines = _wrap_text(draw, text, font, max_width)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y - xy[1]


def _load_fonts(font_size: int):
    small = max(12, font_size - 2)
    for path in [
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Times.ttc",
        "C:/Windows/Fonts/times.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, font_size), ImageFont.truetype(path, small)
            except Exception:
                pass
    f = ImageFont.load_default()
    return f, f


def compose_one(
    batch_dir: Path,
    task: dict,
    out_path: Path,
    row_height: int = 160,
    max_text_width: int = 900,
    padding: int = 16,
    gap: int = 12,
    font_size: int = 18,
    show_text_output: bool = False,
) -> bool:
    """One canvas: text block + row of 5 images (Original, A, B, C, D). Optionally text_output below."""
    batch_dir = Path(batch_dir)
    visual_input = task.get("visual_input") or []
    if len(visual_input) < 5:
        return False

    paths = []
    for item in visual_input:
        path_str = item.get("path", "") if isinstance(item, dict) else str(item)
        p = _resolve_img_path(batch_dir, path_str)
        if not p.exists():
            return False
        paths.append(p)

    imgs: List[Tuple[Image.Image, int, int]] = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        w, h = im.size
        scale = row_height / h if h else 1
        new_w = max(1, int(w * scale))
        new_h = row_height
        im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        imgs.append((im, new_w, new_h))

    row_width = sum(w for _, w, _ in imgs) + gap * 4
    canvas_w = max(max_text_width, row_width) + 2 * padding
    text_block_w = canvas_w - 2 * padding

    font, font_small = _load_fonts(font_size)
    temp_im = Image.new("RGB", (canvas_w, 100))
    temp_draw = ImageDraw.Draw(temp_im)
    line_height = int(font_size * 1.35)

    text_input = task.get("text_input", "")
    answer = task.get("answer", "")
    line1 = f"Question: {text_input}"
    line2 = f"Answer: {answer}"
    h1 = _draw_text_block(temp_draw, (0, 0), line1, font_small, text_block_w, line_height)
    h2 = _draw_text_block(temp_draw, (0, 0), line2, font_small, text_block_w, line_height)
    text_block_h = padding + h1 + 4 + h2 + padding

    label_h = font_size + 8
    canvas_h = text_block_h + padding + row_height + label_h + padding

    text_output = (task.get("text_output") or "").strip() if show_text_output else ""
    if text_output:
        h_output = _draw_text_block(temp_draw, (0, 0), text_output, font_small, text_block_w, line_height)
        canvas_h += padding + h_output

    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    y = padding
    _draw_text_block(draw, (padding, y), line1, font_small, text_block_w, line_height)
    y += h1 + 4
    _draw_text_block(draw, (padding, y), line2, font_small, text_block_w, line_height)
    y += h2 + padding

    row_y = y
    x = padding + (canvas_w - 2 * padding - row_width) // 2
    labels = ["Original", "A", "B", "C", "D"]

    for i, ((im, w, h), label) in enumerate(zip(imgs, labels)):
        if i > 0:
            x += gap
        canvas.paste(im, (x, row_y))
        lw = _text_width(draw, label, font_small)
        lx = x + (w - lw) // 2
        ly = row_y + h + 4
        draw.text((lx, ly), label, font=font_small, fill=(0, 0, 0))
        x += w

    if text_output:
        y = row_y + row_height + label_h + padding
        _draw_text_block(draw, (padding, y), text_output, font_small, text_block_w, line_height)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Compose 3dr task images from assign_data.jsonl -> batch/composed_img/"
    )
    parser.add_argument("batch_dir", type=str, help="Batch dir, e.g. medias/batch_xxx")
    parser.add_argument("--jsonl", type=str, default=None, help="JSONL path (default: batch_dir/assign_data.jsonl)")
    parser.add_argument("--row-height", type=int, default=160, help="Image row height")
    parser.add_argument("--max-text-width", type=int, default=900, help="Max width for question/answer text")
    parser.add_argument("--padding", type=int, default=16, help="Canvas padding")
    parser.add_argument("--gap", type=int, default=12, help="Gap between images")
    parser.add_argument("--font-size", type=int, default=22, help="Font size")
    parser.add_argument("--show-text-output", action="store_true", help="Draw text_output below image row")
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir)
    if not batch_dir.is_dir():
        print("Directory not found:", batch_dir)
        return
    jsonl_path = Path(args.jsonl) if args.jsonl else batch_dir / "assign_data.jsonl"
    if not jsonl_path.exists():
        print("JSONL not found:", jsonl_path)
        return

    out_dir = batch_dir / "composed_img"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            task = json.loads(line)
            tid = task.get("id", "")
            if not tid:
                continue
            out_path = out_dir / f"{tid}_composed.jpg"
            if compose_one(
                batch_dir,
                task,
                out_path,
                row_height=args.row_height,
                max_text_width=args.max_text_width,
                padding=args.padding,
                gap=args.gap,
                font_size=args.font_size,
                show_text_output=getattr(args, "show_text_output", False),
            ):
                count += 1
                print(" ", out_path.name)
    print("Composed", count, "images ->", out_dir)


if __name__ == "__main__":
    main()
