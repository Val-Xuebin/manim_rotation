# 2D Rotation Test (2DR) — Synthesis & Methods

## Project layout

```
2dr/
├── README.md          # This file (task, pipeline, methods)
├── synth.md           # Pointer to README
├── generate.py        # CLI: meta | render | assign
├── src/
│   ├── meta_shape.py  # Meta: grid + variants JSON; rotation-group checks
│   ├── render.py      # Render: Manim scene, batch img/video
│   └── assign_json.py # Assign: shape + media → MCQ JSONL
└── utils/
    └── image_compose.py  # Optional: compose task preview images
```

Batch output: `medias/batch_<timestamp>/` with `shape/`, `img/`, `video/`, `assign_data.jsonl`, optionally `composed_img/`.

---

## Task Definition

2D Rotation Test: given a connected 2D grid and four other grids with different patterns (colors/textures), identify the one that is equivalent to the original under a given rotation (e.g. rotate original counter-clockwise 90°).

Without guidance, the task relies on **intuitive visual manipulation**: mentally rotating one grid to match another and deciding if they are rotation-equivalent.

### Difficulty

- **Easy**: Rotation direction is given in the prompt (e.g. “clockwise 90 degrees”). The model only needs to apply that rotation in imagination and pick the matching option.
- **Hard**: No rotation direction; the model must infer the correct transformation.

---

## Pipeline Overview

1. **Meta** — Generate shape JSONs (grid + variants s0–s4) → `batch/shape/*.json`
2. **Render** — Manim renders first/last frames and video per variant → `batch/img/`, `batch/video/`
3. **Assign** — Build MCQ JSONL (question, options A–D, answer) → `batch/assign_data.jsonl`

---

## 1. Meta (Metadata Generation)

**Role**: Produce one JSON per instance with original pattern (s0) and four variants (s1–s4), plus rotation and visual settings.

**Modes**: `color` (cell colors) or `texture` (lines/polygons). Grid size from config (e.g. 2×2, 3×3).

**Steps**:

1. **Grid style**: size, cell_size, show_grid; optional pattern (0/1 matrix) for non-full grids.
2. **Pattern**: Random connected pattern; color mode uses asymmetric patterns when possible.
3. **Variants**:
   - s0: original
   - s1: vertical mirror (row flip)
   - s2: horizontal mirror (column flip)
   - s3: swap positions of two cells
   - s4: modify one cell (color change, or line/polygon change in texture mode)
4. **Rotation**: angle (e.g. 90°), clockwise/counter-clockwise, duration.
5. **Visual**: fill_opacity, stroke_width, stroke_color, texture_opacity, etc.

**Uniqueness (rotation group)**:

- After building s0–s4, we apply the same rotation R to each and compare canonical representations.
- **Check 1**: R(s0), R(s1), …, R(s4) must be pairwise distinct so no two options show the same image.
- **Check 2**: No rotation of the original (R, R², R³) may equal any mirror (H, V, or diagonal). So the prototype is “chiral” with respect to rotation vs mirrors.
- If either check fails, config is regenerated (with retry limit).

**Output**: `shape/2dr_0001.json`, … with `variants`, `rotation`, `visual`, `video`.

---

## 2. Render (Manim)

**Role**: Turn each variant into images and (for s0) a rotation video.

**Modes**: `first` / `last` (single frame), `video` (animation), `task` (s0: first + last + video; s1–s4: last only).

**Flow**: Load JSON → build grid VGroup from variant `cells` (or legacy pattern/cell_colors) → apply rotation → write frames/video.

**Output** (per batch):

- `img/{id}_0_first.jpg`, `img/{id}_0_last.jpg`, `img/{id}_{0..4}_last.jpg`
- `video/{id}_0.mp4`

---

## 3. Assign (Task JSONL)

**Role**: Map rendered assets to MCQ rows (question image + 4 option images + answer).

**Flow**:

- Read `shape/*.json` and ensure all required images/video exist.
- For each instance: pick s0 + 3 from s1–s4, shuffle to A–D; question = original first frame, options = chosen variants’ last frames; answer = the key that maps to `original`.
- Build `text_input`, `visual_input`, `visual_output`, `assign`, `answer`, `text_output` (reasoning template). Easy uses a template with `{clockwise}` in the question; hard omits rotation direction.

**Output**: `assign_data.jsonl` — one JSON object per line (category, id, text_input, assign, visual_input, visual_output, answer, text_output).

---

## Variant Collision and Group-Theory Fix

If for some grid we have e.g. R(horizontal_mirror) = original, then the “original” thumbnail and one option (e.g. B) would show the same figure → duplicate option and ambiguous answer. To avoid this:

- We compare **canonical** forms of rotated variants (position + color/texture/line_direction/polygon_shape, sorted by (r,c)).
- We enforce: (1) all five rotated variants have distinct canonical forms; (2) no rotation of the original equals any mirror (H, V, or diagonal). So the 2D prototype cannot be turned into a mirror variant by rotation alone, and the four displayed options (after rotation) stay distinct.

See `src/meta_shape.py`: `_cells_canonical`, `_rotate_cells_90_cw` / `_rotate_cells_90_ccw`, `_mirror_cells_diag_*`, and the validation block in `generate_json_config`.

---

## Usage (concise)

```text
# Full pipeline (default 5 samples)
python generate.py
python generate.py --samples 10 --output-dir medias

# Single steps
python generate.py meta [--samples N] [--output-dir DIR] [--grid-size A,B] [--mode mixed|color|texture]
python generate.py render <batch_dir> [--mode task] [--range N] [--duration D]
python generate.py assign <batch_dir> [--data-path P] [-o out.jsonl] [--assign-category easy|hard|mixed]
```

Compose preview images (optional):

```text
python utils/image_compose.py <batch_dir> [--show-text-output]
```
