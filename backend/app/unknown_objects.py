import colorsys
from dataclasses import dataclass

import cv2
import numpy as np

COLOR_DISTANCE = 40
SURFACE_TONE_SHARE = 0.15
MIN_AREA_RATIO = 0.0015
ENCLOSURE_REACH = 5
ENCLOSURE_SHARE = 0.6
OPENING_RATIO = 1 / 300
GRAY_SATURATION = 0.18
WARM_HUES = ((0, 65), (335, 360))
HUE_NAMES = (
    (15, "red"),
    (40, "orange"),
    (65, "yellow"),
    (170, "green"),
    (200, "cyan"),
    (255, "blue"),
    (290, "purple"),
    (335, "pink"),
    (360, "red"),
)


@dataclass(frozen=True)
class UnknownObject:
    paths: np.ndarray
    color: np.ndarray


def find_unknown_objects(
    path_owner: np.ndarray, unowned: np.ndarray, colors: np.ndarray, ids: np.ndarray, surfaces: list[int]
) -> list[UnknownObject]:
    areas = np.bincount(ids.ravel(), minlength=len(path_owner))
    foreign = foreign_paths(path_owner, unowned, colors, surface_tone_map(path_owner, colors, areas, surfaces))
    labels, label_count = object_blobs(foreign[ids])
    path_blob = majority_blob(ids, labels, label_count, len(path_owner))
    blobs = [np.flatnonzero(foreign & (path_blob == label)) for label in range(1, label_count)]
    return [UnknownObject(blob, colors[blob[areas[blob].argmax()]]) for blob in blobs if len(blob)]


def is_enclosed(paths: np.ndarray, path_owner: np.ndarray, ids: np.ndarray) -> bool:
    blob = np.isin(ids, paths)
    reach = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ENCLOSURE_REACH + 1, 2 * ENCLOSURE_REACH + 1))
    ring = (cv2.dilate(blob.astype(np.uint8), reach) > 0) & ~blob
    surface = np.bincount(path_owner[paths]).argmax()
    return bool(ring.any()) and float((path_owner[ids[ring]] == surface).mean()) >= ENCLOSURE_SHARE


def surface_tone_map(
    path_owner: np.ndarray, colors: np.ndarray, areas: np.ndarray, surfaces: list[int]
) -> dict[int, np.ndarray]:
    tones: dict[int, np.ndarray] = {}
    for surface in surfaces:
        owned = np.flatnonzero(path_owner == surface)
        if len(owned):
            tones[surface] = surface_tones(colors[owned], areas[owned])
    return tones


def foreign_paths(
    path_owner: np.ndarray, unowned: np.ndarray, colors: np.ndarray, tones: dict[int, np.ndarray]
) -> np.ndarray:
    foreign = np.zeros(len(path_owner), dtype=bool)
    for surface, surface_colors in tones.items():
        candidates = np.flatnonzero(unowned & (path_owner == surface))
        foreign[candidates[tone_distances(colors[candidates], surface_colors) > COLOR_DISTANCE]] = True
    foreign[0] = False
    return foreign


def tone_distances(colors: np.ndarray, tones: np.ndarray) -> np.ndarray:
    return np.linalg.norm(colors[..., None, :].astype(float) - tones, axis=-1).min(axis=-1)


def surface_tones(colors: np.ndarray, areas: np.ndarray) -> np.ndarray:
    shares = areas / max(int(areas.sum()), 1)
    return colors[(shares >= SURFACE_TONE_SHARE) | (shares == shares.max())]


def object_blobs(mask: np.ndarray) -> tuple[np.ndarray, int]:
    size = max(3, round(max(mask.shape) * OPENING_RATIO))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    opened = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    kept = stats[:, cv2.CC_STAT_AREA] >= MIN_AREA_RATIO * mask.size
    kept[0] = False
    relabel = np.zeros(count, dtype=np.int64)
    relabel[kept] = np.arange(1, kept.sum() + 1)
    return relabel[labels], int(kept.sum()) + 1


def majority_blob(ids: np.ndarray, labels: np.ndarray, label_count: int, path_count: int) -> np.ndarray:
    pairs = ids * label_count + labels
    counts = np.bincount(pairs.ravel(), minlength=path_count * label_count).reshape(path_count, label_count)
    counts[:, 0] = 0
    return np.where(counts.max(axis=1) > 0, counts.argmax(axis=1), 0)


def color_name(color: np.ndarray) -> str:
    hue, lightness, saturation = colorsys.rgb_to_hls(*(color / 255))
    degrees = hue * 360
    if saturation < GRAY_SATURATION:
        return "black" if lightness < 0.2 else "white" if lightness > 0.85 else "gray"
    if any(low <= degrees < high for low, high in WARM_HUES):
        if lightness < 0.45:
            return "brown"
        if lightness > 0.75:
            return "beige"
        if saturation < 0.45:
            return "tan"
    base = next(name for limit, name in HUE_NAMES if degrees < limit)
    return f"dark-{base}" if lightness < 0.3 else f"light-{base}" if lightness > 0.75 else base
