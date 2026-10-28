import cv2
import numpy as np
from PIL import Image

from app.id_map import render_id_map
from app.nearest_fill import fill_from_nearest

BACKGROUND_KERNEL_RATIO = 0.009
CORE_KERNEL_RATIO = 0.004
MIN_KERNEL = 5
INK_MAX_LUMA = 110
INK_MIN_CONTRAST = 20
INK_RELATIVE_CONTRAST = 0.4
INK_CORE_SHARE = 0.5
DARKNESS_WEIGHT_POWER = 4
ERASE_MARGIN = 5
INK_OVERLAP = 9
INK_SUPPORT = 0.18
WIDE_INK_MAX_LUMA = 60
WIDE_INK_MIN_AREA_RATIO = 0.002
WIDE_INK_MIN_ELONGATION = 30
STROKE_REACH_FACTOR = 2.5
MAX_DIRECT_KERNEL = 31
LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114])
UNOWNED = -1


def kernel(width: int, ratio: float) -> np.ndarray:
    return ellipse(max(MIN_KERNEL, round(width * ratio)))


def ellipse(size: int) -> np.ndarray:
    odd = size | 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (odd, odd))


def ink_reach(image: Image.Image) -> int:
    base = max(MIN_KERNEL, round(image.width * BACKGROUND_KERNEL_RATIO)) | 1
    stroke = widest_ink_stroke(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY))
    return max(base, round(stroke * STROKE_REACH_FACTOR) | 1)


def widest_ink_stroke(luma: np.ndarray) -> float:
    dark = (luma < WIDE_INK_MAX_LUMA).astype(np.uint8)
    distance = cv2.distanceTransform(dark, cv2.DIST_L2, 5)
    ridge = (distance >= 1) & (distance >= cv2.dilate(distance, np.ones((3, 3), np.uint8)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    largest = 0
    stroke = 0.0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < WIDE_INK_MIN_AREA_RATIO * luma.size or area <= largest:
            continue
        half_widths = distance[ridge & (labels == label)]
        width = 2 * float(np.median(half_widths)) if len(half_widths) else 0.0
        if width > 0 and area / width**2 >= WIDE_INK_MIN_ELONGATION:
            largest, stroke = area, width
    return stroke


def find_ink(image: Image.Image, reach: int) -> np.ndarray:
    luma = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    background = closed_background(luma, reach)
    contrast = background.astype(np.int16) - luma
    candidate = (
        (luma < INK_MAX_LUMA) & (contrast > INK_MIN_CONTRAST) & (contrast > background * INK_RELATIVE_CONTRAST)
    )
    core_contrast = np.where(candidate, contrast, 0).astype(np.uint8)
    peak = cv2.dilate(core_contrast, kernel(image.width, CORE_KERNEL_RATIO))
    return candidate & (contrast >= peak * INK_CORE_SHARE)


def erase_ink(image: Image.Image, ink: np.ndarray) -> Image.Image:
    margin = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ERASE_MARGIN, ERASE_MARGIN))
    erase_mask = cv2.dilate(ink.astype(np.uint8), margin)
    return Image.fromarray(fill_from_nearest(np.asarray(image), erase_mask == 0))


def closed_background(luma: np.ndarray, reach: int) -> np.ndarray:
    if reach <= MAX_DIRECT_KERNEL:
        return cv2.morphologyEx(luma, cv2.MORPH_CLOSE, ellipse(reach))
    scale = MAX_DIRECT_KERNEL / reach
    small = cv2.resize(luma, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    closed = cv2.morphologyEx(small, cv2.MORPH_CLOSE, ellipse(MAX_DIRECT_KERNEL))
    return cv2.resize(closed, (luma.shape[1], luma.shape[0]), interpolation=cv2.INTER_LINEAR)


def front_ink_owners(ink: np.ndarray, pixel_owner: np.ndarray, reach: int) -> np.ndarray:
    box = (reach, reach)
    paint = ~ink
    neighbors = np.maximum(neighbor_counts(paint, box), 1)
    owners = np.full(ink.shape, UNOWNED, dtype=np.int64)
    for index in np.unique(pixel_owner):
        support = neighbor_counts(paint & (pixel_owner == index), box) / neighbors
        owners[ink & (support >= INK_SUPPORT)] = index
    return nearest_owner_for_unsupported(ink, owners)


def neighbor_counts(mask: np.ndarray, reach: tuple[int, int]) -> np.ndarray:
    return cv2.boxFilter(mask.astype(np.float32), -1, reach, normalize=False)


def nearest_owner_for_unsupported(ink: np.ndarray, owners: np.ndarray) -> np.ndarray:
    supported = owners != UNOWNED
    if not (ink & ~supported).any() or not supported.any():
        return owners
    nearest = fill_from_nearest(owners[..., None], supported)[..., 0]
    return np.where(ink, nearest, UNOWNED)


def overlapping_ink_region(ink: np.ndarray, ink_owner: np.ndarray, index: int) -> np.ndarray:
    overlap = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (INK_OVERLAP, INK_OVERLAP))
    own = cv2.dilate((ink_owner == index).astype(np.uint8), overlap)
    return ink & (own > 0) & (ink_owner >= index)


def ink_path_colors(paths: list[str], pixels: np.ndarray, region: np.ndarray) -> list[str]:
    ids = render_id_map(paths, (region.shape[1], region.shape[0]))
    inside = region & (ids > 0)
    rgb = pixels[inside].astype(float)
    weights = (255 - rgb @ LUMA_WEIGHTS) ** DARKNESS_WEIGHT_POWER
    path_ids = ids[inside]
    count = len(paths) + 1
    total = np.maximum(np.bincount(path_ids, weights, minlength=count), 1e-9)
    channels = [np.bincount(path_ids, weights * rgb[:, channel], minlength=count) / total for channel in range(3)]
    colors = np.stack(channels, axis=1).round().astype(int)[1:]
    return [f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in colors]
