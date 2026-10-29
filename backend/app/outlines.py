from dataclasses import dataclass

import cv2
import numpy as np

from app.shape_fitting import fit_ring
from app.id_map import FILL_PATTERN, label_boxes
from app.nearest_fill import fill_from_nearest
from app.region_merging import region_widths
from app.strokes import split_thin_strokes, stroke_rings
from app.tracing import BINARY_FILL

SMOOTHING_SIGMA = 1.5
DETAIL_SIGMA = 0.6
THIN_SIGMA = 0.6
THIN_HALF_WIDTH = 0.5
THICK_HALF_WIDTH = 2.5
THICKNESS_REACH = 11
PROJECTION_STEPS = 3
MAX_PROJECTION_STEP = 1.0
MIN_CONTOUR_POINTS = 4
MIN_CONTOUR_AREA = 4.0
MIN_REGION_WIDTH = 1.2
TOLERANCE_PER_WIDTH = 0.3
MIN_TOLERANCE = 0.15
CONTEXT_MARGIN = int(np.ceil(SMOOTHING_SIGMA * 3)) + 2
MAX_MARGIN = 8.0

Edges = tuple[bool, bool, bool, bool]


@dataclass(frozen=True)
class Smoothing:
    sigma: float
    tolerance: float
    ink_tolerance: float
    snap_shapes: bool


SMOOTH = Smoothing(sigma=SMOOTHING_SIGMA, tolerance=0.4, ink_tolerance=0.6, snap_shapes=True)
DETAILED = Smoothing(sigma=DETAIL_SIGMA, tolerance=0.25, ink_tolerance=0.3, snap_shapes=False)


def ink_mask_outlines(mask: np.ndarray, image_edges: Edges, clip: np.ndarray, smoothing: Smoothing) -> list[str]:
    field = smoothed_signed_distance(padded(mask, image_edges), smoothing.sigma)
    field = np.minimum(field, signed_distance(padded(clip, image_edges)))
    return field_outlines(
        field > 0, field, image_edges, (0, 0), mask.shape, smoothing.ink_tolerance, smoothing.snap_shapes
    )


def field_outlines(
    inside: np.ndarray,
    field: np.ndarray,
    image_edges: Edges,
    offset: tuple[int, int],
    shape: tuple[int, ...],
    tolerance: float,
    snap_shapes: bool,
) -> list[str]:
    contours, hierarchy = cv2.findContours(inside.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hierarchy is None:
        return []
    shift = np.array([offset[0] - CONTEXT_MARGIN + 0.5, offset[1] - CONTEXT_MARGIN + 0.5])
    low, high = clamp_bounds(shape, image_edges, offset)
    rings = [ring_points(field, contour, shift, low, high) for contour in contours]
    outlines = []
    for index, links in enumerate(hierarchy[0]):
        if links[3] != -1 or rings[index] is None:
            continue
        holes = child_indexes(hierarchy[0], index)
        parts = [oriented(rings[index], outer=True)]
        parts += [oriented(rings[hole], outer=False) for hole in holes if rings[hole] is not None]
        part_tolerance = width_tolerance(rings[index], tolerance)
        outlines.append("".join(curve_data(part, part_tolerance, snap_shapes) for part in parts))
    return outlines


def padded(mask: np.ndarray, image_edges: Edges) -> np.ndarray:
    grown = np.pad(mask, CONTEXT_MARGIN, mode="edge")
    left, top, right, bottom = image_edges
    margin = CONTEXT_MARGIN
    if not left:
        grown[:, :margin] = False
    if not top:
        grown[:margin, :] = False
    if not right:
        grown[:, -margin:] = False
    if not bottom:
        grown[-margin:, :] = False
    return grown


def clamp_bounds(shape: tuple[int, ...], image_edges: Edges, offset: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    left, top, right, bottom = image_edges
    low = np.array([offset[0] if left else -np.inf, offset[1] if top else -np.inf])
    high = np.array([offset[0] + shape[1] if right else np.inf, offset[1] + shape[0] if bottom else np.inf])
    return low, high


def box_image_edges(box: tuple[int, int, int, int], shape: tuple[int, ...]) -> Edges:
    top, bottom, left, right = box
    return (left == 0, top == 0, right == shape[1], bottom == shape[0])


def smoothed_signed_distance(mask: np.ndarray, sigma: float) -> np.ndarray:
    signed = signed_distance(mask)
    wide = cv2.GaussianBlur(signed, (0, 0), sigma)
    thin = cv2.GaussianBlur(signed, (0, 0), THIN_SIGMA)
    reach = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (THICKNESS_REACH, THICKNESS_REACH))
    half_width = cv2.dilate(np.maximum(signed, 0), reach)
    weight = np.clip((half_width - THIN_HALF_WIDTH) / (THICK_HALF_WIDTH - THIN_HALF_WIDTH), 0, 1)
    return thin + weight * (wide - thin)


def signed_distance(mask: np.ndarray) -> np.ndarray:
    inside = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    outside = cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    return np.where(mask, inside - 0.5, 0.5 - outside).astype(np.float32)


def child_indexes(links: np.ndarray, parent: int) -> list[int]:
    children = []
    child = links[parent][2]
    while child != -1:
        children.append(int(child))
        child = links[child][0]
    return children


def ring_points(
    field: np.ndarray, contour: np.ndarray, shift: np.ndarray, low: np.ndarray, high: np.ndarray
) -> np.ndarray | None:
    if len(contour) < MIN_CONTOUR_POINTS:
        return None
    points = project_to_zero(field, contour[:, 0, :].astype(np.float64)) + shift
    points = np.clip(points, low, high)
    points = drop_repeated(points)
    if len(points) < MIN_CONTOUR_POINTS or abs(signed_area(points)) < MIN_CONTOUR_AREA:
        return None
    return points


def project_to_zero(field: np.ndarray, points: np.ndarray) -> np.ndarray:
    for _ in range(PROJECTION_STEPS):
        value = bilinear(field, points)
        gradient = np.stack(
            [
                bilinear(field, points + [0.5, 0]) - bilinear(field, points - [0.5, 0]),
                bilinear(field, points + [0, 0.5]) - bilinear(field, points - [0, 0.5]),
            ],
            axis=1,
        )
        norm = np.maximum((gradient**2).sum(axis=1), 1e-6)
        step = -(value / norm)[:, None] * gradient
        length = np.maximum(np.hypot(*step.T) / MAX_PROJECTION_STEP, 1)[:, None]
        points = points + step / length
    return points


def bilinear(field: np.ndarray, points: np.ndarray) -> np.ndarray:
    height, width = field.shape
    x = np.clip(points[:, 0], 0, width - 1.001)
    y = np.clip(points[:, 1], 0, height - 1.001)
    left, top = x.astype(int), y.astype(int)
    fx, fy = x - left, y - top
    upper = field[top, left] * (1 - fx) + field[top, left + 1] * fx
    lower = field[top + 1, left] * (1 - fx) + field[top + 1, left + 1] * fx
    return upper * (1 - fy) + lower * fy


def drop_repeated(points: np.ndarray) -> np.ndarray:
    steps = np.hypot(*(points - np.roll(points, 1, axis=0)).T)
    return points[steps > 1e-3]


def signed_area(points: np.ndarray) -> float:
    x, y = points[:, 0], points[:, 1]
    return float((x * np.roll(y, -1) - np.roll(x, -1) * y).sum() / 2)


def oriented(points: np.ndarray, outer: bool) -> np.ndarray:
    return points if (signed_area(points) > 0) == outer else points[::-1]


def width_tolerance(points: np.ndarray, tolerance: float) -> float:
    perimeter = float(np.hypot(*(points - np.roll(points, 1, axis=0)).T).sum())
    width = 2 * abs(signed_area(points)) / max(perimeter, 1e-9)
    return float(np.clip(width * TOLERANCE_PER_WIDTH, MIN_TOLERANCE, tolerance))


def curve_data(points: np.ndarray, tolerance: float, snap_shapes: bool) -> str:
    curves = fit_ring(points, tolerance, snap_shapes)
    start = curves[0][0]
    segments = "".join(f"C{coords(curve[1])} {coords(curve[2])} {coords(curve[3])}" for curve in curves)
    return f"M{coords(start)}{segments}Z"


def coords(point: np.ndarray) -> str:
    return f"{point[0]:.2f} {point[1]:.2f}"


def region_outline_data(
    owner: np.ndarray, margin: np.ndarray, label: int, box: tuple[int, int, int, int], smoothing: Smoothing
) -> str:
    top, bottom, left, right = context_box(box, owner.shape)
    inside = owner[top:bottom, left:right] == label
    field = np.where(inside, margin[top:bottom, left:right], -margin[top:bottom, left:right])
    edges = box_image_edges((top, bottom, left, right), owner.shape)
    padding = CONTEXT_MARGIN
    outlines = field_outlines(
        np.pad(inside, padding, mode="edge"),
        np.pad(field, padding, mode="edge"),
        edges,
        (left, top),
        inside.shape,
        smoothing.tolerance,
        smoothing.snap_shapes,
    )
    return "".join(outlines)


def context_box(box: tuple[int, int, int, int], shape: tuple[int, ...]) -> tuple[int, int, int, int]:
    top, bottom, left, right = box
    margin = CONTEXT_MARGIN
    return (max(top - margin, 0), min(bottom + margin, shape[0]), max(left - margin, 0), min(right + margin, shape[1]))


def smooth_region_paths(
    paths: list[str], ids: np.ndarray, detailed: np.ndarray
) -> tuple[list[str], np.ndarray]:
    styles = [DETAILED if detail else SMOOTH for detail in detailed]
    owner, margin = smoothed_partition(ids, len(paths), styles)
    boxes = label_boxes(owner, len(paths))
    smoothed = [
        smooth_region_path(path, owner, margin, label, boxes.get(label), styles[label])
        for label, path in enumerate(paths, start=1)
    ]
    return smoothed, owner


def smoothed_partition(ids: np.ndarray, count: int, styles: list[Smoothing]) -> tuple[np.ndarray, np.ndarray]:
    best = np.full(ids.shape, -np.inf, dtype=np.float32)
    second = best.copy()
    owner = ids.copy()
    padding = CONTEXT_MARGIN
    for label, box in label_boxes(ids, count).items():
        top, bottom, left, right = context_box(box, ids.shape)
        mask = ids[top:bottom, left:right] == label
        edges = box_image_edges((top, bottom, left, right), ids.shape)
        field = smoothed_signed_distance(padded(mask, edges), styles[label].sigma)[padding:-padding, padding:-padding]
        leading, runner_up = best[top:bottom, left:right], second[top:bottom, left:right]
        higher = field > leading
        runner_up[...] = np.where(higher, leading, np.maximum(runner_up, field))
        leading[...] = np.where(higher, field, leading)
        owner[top:bottom, left:right][higher] = label
    return owner, np.minimum(best - second, MAX_MARGIN)


def smooth_region_path(
    path: str,
    owner: np.ndarray,
    margin: np.ndarray,
    label: int,
    box: tuple[int, int, int, int] | None,
    smoothing: Smoothing,
) -> str:
    fill = FILL_PATTERN.search(path)
    if box is None or fill is None:
        return ""
    data = region_outline_data(owner, margin, label, box, smoothing)
    return f'<path d="{data}" {fill.group(0)}/>' if data else ""


def absorb_slivers(ids: np.ndarray) -> np.ndarray:
    keep = region_widths(ids)[ids] >= MIN_REGION_WIDTH
    return fill_from_nearest(ids[..., None], keep)[..., 0] if keep.any() else ids


def ink_outline_paths(mask: np.ndarray, image_edges: Edges, clip: np.ndarray, smoothing: Smoothing) -> list[str]:
    thick, thin = split_thin_strokes(mask)
    outlines = ink_mask_outlines(thick, image_edges, clip, smoothing)
    outlines += [stroke_data(rings, width, smoothing) for rings, width in stroke_rings(thin & clip)]
    return [f'<path d="{data}" {BINARY_FILL}/>' for data in outlines]


def stroke_data(rings: list[np.ndarray], width: float, smoothing: Smoothing) -> str:
    tolerance = float(np.clip(width * TOLERANCE_PER_WIDTH, MIN_TOLERANCE, smoothing.ink_tolerance))
    ordered = sorted(rings, key=lambda ring: -abs(signed_area(ring)))
    parts = [oriented(ordered[0], outer=True)] + [oriented(ring, outer=False) for ring in ordered[1:]]
    return "".join(curve_data(part, tolerance, smoothing.snap_shapes) for part in parts)
