import cv2
import numpy as np
from PIL import Image

from app.nearest_fill import fill_from_nearest
from app.tracing import trace_paths
from app.unknown_objects import COLOR_DISTANCE, tone_distances

UNDERPAINT_OVERLAP = 3
LARGE_SOURCE_SHARE = 0.005
HIDDEN_RING = 2
HIDDEN_ENCLOSURE = 0.35
MIN_HIDDEN_SHARE = 0.0005


NO_SOURCE = -1


def source_paths(
    path_owner: np.ndarray, colors: np.ndarray, areas: np.ndarray, tones: dict[int, np.ndarray]
) -> np.ndarray:
    preferred = areas >= LARGE_SOURCE_SHARE * areas.sum()
    for layer, layer_tones in tones.items():
        owned = np.flatnonzero(path_owner == layer)
        preferred[owned[tone_distances(colors[owned], layer_tones) <= COLOR_DISTANCE]] = True
    return preferred


def layer_sources(pixel_owner: np.ndarray, preferred: np.ndarray, layer_count: int) -> np.ndarray:
    kernel = overlap_kernel()
    sources = np.full(pixel_owner.shape, NO_SOURCE, dtype=np.int64)
    for layer in range(layer_count):
        sources[color_source(pixel_owner == layer, preferred, kernel)] = layer
    return sources


def underpaint_regions(
    pixel_owner: np.ndarray, sources: np.ndarray, surfaces: list[int], layer_count: int
) -> dict[int, np.ndarray]:
    regions = surface_underpaint_regions(pixel_owner, sources, surfaces)
    for layer in range(layer_count):
        if layer not in regions:
            regions[layer] = hidden_object_region(pixel_owner, layer)
    return regions


def surface_underpaint_regions(pixel_owner: np.ndarray, sources: np.ndarray, surfaces: list[int]) -> dict[int, np.ndarray]:
    ordered = sorted(surfaces)
    regions = {surface: np.zeros(pixel_owner.shape, dtype=bool) for surface in ordered}
    for depth in range(1, len(ordered) + 1):
        behind = ordered[:depth]
        covered = pixel_owner == ordered[depth] if depth < len(ordered) else ~np.isin(pixel_owner, ordered)
        is_behind = np.isin(sources, behind)
        if not covered.any() or not is_behind.any():
            continue
        nearest_behind = fill_from_nearest(sources[..., None], is_behind)[..., 0]
        for surface in behind:
            regions[surface] |= covered & (nearest_behind == surface)
    return regions


def hidden_object_region(pixel_owner: np.ndarray, layer: int) -> np.ndarray:
    visible = pixel_owner == layer
    hidden = convex_hull_mask(visible) & (pixel_owner > layer)
    if not hidden.any():
        return hidden
    count, parts = cv2.connectedComponents(hidden.astype(np.uint8))
    ring = ring_labels(parts, hidden)
    touching = np.bincount(ring[ring > 0], minlength=count)
    enclosing = np.bincount(ring[(ring > 0) & visible], minlength=count)
    areas = np.bincount(parts.ravel(), minlength=count)
    kept = (enclosing >= HIDDEN_ENCLOSURE * np.maximum(touching, 1)) & (areas >= MIN_HIDDEN_SHARE * hidden.size)
    kept[0] = False
    return kept[parts]


def convex_hull_mask(visible: np.ndarray) -> np.ndarray:
    mask = np.zeros(visible.shape, dtype=np.uint8)
    points = cv2.findNonZero(visible.astype(np.uint8))
    if points is not None:
        cv2.fillConvexPoly(mask, cv2.convexHull(points), 1)
    return mask.astype(bool)


def ring_labels(parts: np.ndarray, hidden: np.ndarray) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * HIDDEN_RING + 1, 2 * HIDDEN_RING + 1))
    grown = cv2.dilate(parts.astype(np.float32), kernel).astype(np.int64)
    return np.where(hidden, 0, grown)


def trace_underpaint(
    rendered: np.ndarray, pixel_owner: np.ndarray, sources: np.ndarray, layer: int, region: np.ndarray
) -> str | None:
    source = sources == layer
    if not region.any() or not source.any():
        return None
    grown = cv2.dilate(region.astype(np.uint8), overlap_kernel()).astype(bool) & (region | (pixel_owner == layer))
    left, top, right, bottom = Image.fromarray(grown.astype(np.uint8) * 255).getbbox()
    window = (slice(top, bottom), slice(left, right))
    colors = fill_from_nearest(rendered, source)[window]
    alpha = grown[window]
    cut = np.where(alpha[..., None], np.dstack([colors, alpha.astype(np.uint8) * 255]), 0).astype(np.uint8)
    paths = trace_paths(Image.fromarray(cut, "RGBA"))
    return f'<g transform="translate({left},{top})">{"".join(paths)}</g>' if paths else None


def overlap_kernel() -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * UNDERPAINT_OVERLAP + 1, 2 * UNDERPAINT_OVERLAP + 1))


def color_source(visible: np.ndarray, preferred: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    interior = cv2.erode(visible.astype(np.uint8), kernel).astype(bool)
    for candidate in (interior & preferred, interior):
        if candidate.any():
            return candidate
    return visible
