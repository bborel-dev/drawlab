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
LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114])
UNOWNED = -1


def kernel(width: int, ratio: float) -> np.ndarray:
    size = max(MIN_KERNEL, round(width * ratio)) | 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def find_ink(image: Image.Image) -> np.ndarray:
    luma = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    background = cv2.morphologyEx(luma, cv2.MORPH_CLOSE, kernel(image.width, BACKGROUND_KERNEL_RATIO))
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


def front_ink_owners(ink: np.ndarray, pixel_owner: np.ndarray, width: int) -> np.ndarray:
    shifted = (pixel_owner + 1).astype(np.uint16)
    front = cv2.dilate(shifted, kernel(width, BACKGROUND_KERNEL_RATIO)).astype(np.int64) - 1
    return np.where(ink, front, UNOWNED)


def overlapping_ink_region(ink: np.ndarray, ink_owner: np.ndarray, index: int) -> np.ndarray:
    overlap = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (INK_OVERLAP, INK_OVERLAP))
    own = cv2.dilate((ink_owner == index).astype(np.uint8), overlap)
    return ink & (own > 0)


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
