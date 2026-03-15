# 3DR — 3D Rotation MRT Data Pipeline

Pipeline for generating **MRT (Mental Rotation Task)** data: 3D voxel stacks, rotation videos, task images, and MCQ assignment JSONL. Output layout matches the 2dr-style batch structure (`shape/`, `images/`, `video/`).

## Requirements

- Python 3.8+
- [Manim](https://www.manim.community/) (e.g. `conda activate manim`)
- Pillow (for image composition)
- ffmpeg (for frame extraction)

## Project layout

```
3dr/
├── generate.py           # Entry: full pipeline or single steps
├── chiral_voxels_variants.json   # Chiral voxel shapes (required for meta)
├── src/
│   ├── MRT_generator.py  # Meta: load chiral data, generate instances & configs
│   ├── cube_stack_animation.py  # Manim scene & video rendering
│   ├── renderer.py       # render_video, extract_frame helpers
│   └── voxel_space.py    # Voxel data structures
├── task_compose/
│   ├── mcq_task_compose.py   # Compose configs; task+guidance rendering
│   ├── assign_template.py   # Assign A/B/C/D; generate assign_data.jsonl
│   └── image_compose.py      # Compose task images + prompt → composed_img/
└── medias/
    └── batch_YYYYMMDD_HHMMSS/
        ├── shape/        # Config JSONs + meta_mrt_*.json (+ tex/)
        ├── images/       # Task images (flat: mrt_e001_question.jpg, ...)
        ├── video/        # Guidance videos (flat: mrt_e001_guidance_easy.mp4, ...)
        ├── assign_data.jsonl
        └── composed_img/ # Optional: one composed image per instance
```

## Usage

**Full pipeline (default = same as `all`):**

```bash
conda activate manim
cd 3dr
python generate.py --limit-easy 1 --limit-hard 1
```

**Single steps:**

```bash
python generate.py meta
python generate.py compose medias/batch_YYYYMMDD_HHMMSS
python generate.py task   medias/batch_YYYYMMDD_HHMMSS [--worker N]
python generate.py assign medias/batch_YYYYMMDD_HHMMSS [-o out.jsonl]
```

**Compose task images (after assign):**

```bash
python task_compose/image_compose.py medias/batch_YYYYMMDD_HHMMSS [--show-text-output]
```

## Options

| Option | Description |
|--------|-------------|
| `--limit-easy N` | Process only first N easy instances (task/assign). |
| `--limit-hard N` | Process only first N hard instances (task/assign). |
| `--worker N` | Number of workers for task+guidance (default 1). |
| `-o path` | Assign output JSONL path (default: batch_dir/assign_data.jsonl). |

## Batch output

- **shape/** — One JSON per config (`mrt_e001_...json`), one `meta_mrt_<timestamp>.json`. Optional `shape/tex/` for LaTeX cache.
- **images/** — Task images: `mrt_<id>_question.jpg`, `_answer.jpg`, `_mirror1.jpg`, `_mirror2.jpg`, `_move.jpg` or `_remove.jpg` (instance id in filename; flat layout).
- **video/** — Guidance videos: `mrt_<id>_guidance_*.mp4` (flat layout).
- **assign_data.jsonl** — One JSON object per line: `id`, `category`, `text_input`, `assign`, `visual_input`, `visual_output`, `answer`, `text_output`.

## Design notes

- **Easy**: one rotation per instance; question/answer + mirror1/mirror2 + one of move/remove; one guidance video.
- **Hard**: four rotations (r0–r3) per instance; separate guidance per option; task images from s0_r0 (question/answer) and s1_r1, s2_r2, s3_r3 (mirror1, mirror2, move/remove).
- Instance list is taken from `shape/` config filenames when present; otherwise from `images/` subdirs (legacy).
