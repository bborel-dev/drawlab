import cv2
import numpy as np
from PIL import Image

from app.nearest_fill import fill_from_nearest
from app.tracing import trace_paths
from app.unknown_objects import COLOR_DISTANCE, tone_distances

UNDERPAINT_OVERLAP = 3


def underpaint_regions(pixel_owner: np.ndarray, surfaces: list[int]) -> dict[int, np.ndarray]:
    ordered = sorted(surfaces)
    regions = {surface: np.zeros(pixel_owner.shape, dtype=bool) for surface in ordered}
    for depth in range(1, len(ordered) + 1):
        behind = ordered[:depth]
        covered = pixel_owner == ordered[depth] if depth < len(ordered) else ~np.isin(pixel_owner, ordered)
        is_behind = np.isin(pixel_owner, behind)
        if not covered.any() or not is_behind.any():
            continue
        nearest_behind = fill_from_nearest(pixel_owner[..., None], is_behind)[..., 0]
        for surface in behind:
            regions[surface] |= covered & (nearest_behind == surface)
    return regions


def trace_underpaint(
    rendered: np.ndarray, pixel_owner: np.ndarray, surface: int, region: np.ndarray, tones: np.ndarray | None
) -> str | None:
    visible = pixel_owner == surface
    if not region.any() or not visible.any():
        return None
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * UNDERPAINT_OVERLAP + 1, 2 * UNDERPAINT_OVERLAP + 1))
    grown = cv2.dilate(region.astype(np.uint8), kernel).astype(bool) & (region | visible)
    left, top, right, bottom = Image.fromarray(grown.astype(np.uint8) * 255).getbbox()
    pixels = rendered[top:bottom, left:right]
    source = color_source(visible[top:bottom, left:right], pixels, tones, kernel)
    if not source.any():
        return None
    colors = fill_from_nearest(pixels, source)
    alpha = grown[top:bottom, left:right]
    cut = np.where(alpha[..., None], np.dstack([colors, alpha.astype(np.uint8) * 255]), 0).astype(np.uint8)
    paths = trace_paths(Image.fromarray(cut, "RGBA"))
    return f'<g transform="translate({left},{top})">{"".join(paths)}</g>' if paths else None


def color_source(visible: np.ndarray, pixels: np.ndarray, tones: np.ndarray | None, kernel: np.ndarray) -> np.ndarray:
    interior = cv2.erode(visible.astype(np.uint8), kernel).astype(bool)
    on_tone = interior & (tone_distances(pixels, tones) <= COLOR_DISTANCE) if tones is not None else interior
    for candidate in (on_tone, interior, visible):
        if candidate.any():
            return candidate
    return visible
