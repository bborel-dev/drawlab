import io

import numpy as np
import resvg_py
from PIL import Image

from app.id_map import FILL_PATTERN
from app.nearest_fill import fill_from_nearest
from app.tracing import svg_document, trace_paths

SEAM_STROKE_WIDTH = 1
GAP_MAX_ALPHA = 128
GAP_CONTEXT_MARGIN = 4


def seal_seams(path: str) -> str:
    match = FILL_PATTERN.search(path)
    if match is None:
        return path
    color = match.group(0)[6:13]
    return path.replace("/>", f' stroke="{color}" stroke-width="{SEAM_STROKE_WIDTH}" stroke-linejoin="round"/>', 1)


def find_gaps(paths: list[str], size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    png = resvg_py.svg_to_bytes(svg_string=svg_document(size, "".join(paths)))
    rgba = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))
    return rgba[..., 3] < GAP_MAX_ALPHA, rgba[..., :3]


def trace_gap_patch(rendered: np.ndarray, gaps: np.ndarray) -> str | None:
    box = Image.fromarray(gaps.astype(np.uint8) * 255).getbbox()
    if box is None:
        return None
    height, width = gaps.shape
    left, top = max(box[0] - GAP_CONTEXT_MARGIN, 0), max(box[1] - GAP_CONTEXT_MARGIN, 0)
    right, bottom = min(box[2] + GAP_CONTEXT_MARGIN, width), min(box[3] + GAP_CONTEXT_MARGIN, height)
    gaps_crop = gaps[top:bottom, left:right]
    covered = ~gaps_crop
    if not covered.any():
        return None
    colors = fill_from_nearest(rendered[top:bottom, left:right], covered)
    cut = np.where(gaps_crop[..., None], np.dstack([colors, gaps_crop.astype(np.uint8) * 255]), 0).astype(np.uint8)
    paths = trace_paths(Image.fromarray(cut, "RGBA"))
    return f'<g transform="translate({left},{top})">{"".join(paths)}</g>' if paths else None
