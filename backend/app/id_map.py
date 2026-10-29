import io
import re

import cv2
import numpy as np
import resvg_py
from PIL import Image

from app.nearest_fill import fill_from_nearest
from app.tracing import svg_document

FILL_PATTERN = re.compile(r'fill="#[0-9A-Fa-f]{6}"')


def render_id_map(paths: list[str], size: tuple[int, int]) -> np.ndarray:
    id_paths = [FILL_PATTERN.sub(f'fill="#{index + 1:06X}"', path) for index, path in enumerate(paths)]
    png = resvg_py.svg_to_bytes(
        svg_string=svg_document(size, "".join(id_paths)), background="#000000", shape_rendering="crisp_edges"
    )
    pixels = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.int64)
    return (pixels[..., 0] << 16) | (pixels[..., 1] << 8) | pixels[..., 2]


def covering_id_map(paths: list[str], size: tuple[int, int]) -> np.ndarray:
    ids = render_id_map(paths, size)
    return fill_from_nearest(ids[..., None], ids > 0)[..., 0]


def path_fill_colors(paths: list[str]) -> np.ndarray:
    colors = np.zeros((len(paths) + 1, 3))
    for index, path in enumerate(paths):
        match = FILL_PATTERN.search(path)
        if match:
            hex_color = match.group(0)[7:13]
            colors[index + 1] = [int(hex_color[offset : offset + 2], 16) for offset in (0, 2, 4)]
    return colors


def path_centroids(ids: np.ndarray, path_count: int) -> np.ndarray:
    rows, columns = np.indices(ids.shape)
    flat_ids = ids.ravel()
    areas = np.bincount(flat_ids, minlength=path_count + 1).astype(float)
    sum_x = np.bincount(flat_ids, weights=columns.ravel(), minlength=path_count + 1)
    sum_y = np.bincount(flat_ids, weights=rows.ravel(), minlength=path_count + 1)
    safe_areas = np.maximum(areas, 1.0)
    return np.stack([sum_x / safe_areas, sum_y / safe_areas], axis=1)


def recolor_from_pixels(paths: list[str], ids: np.ndarray, pixels: np.ndarray) -> list[str]:
    count = len(paths) + 1
    flat_ids = ids.ravel()
    areas = np.bincount(flat_ids, minlength=count)
    channels = [np.bincount(flat_ids, weights=pixels[..., channel].ravel(), minlength=count) for channel in range(3)]
    means = np.stack(channels, axis=1) / np.maximum(areas, 1)[:, None]
    return [
        FILL_PATTERN.sub(hex_fill(means[index + 1]), path, count=1) if areas[index + 1] else path
        for index, path in enumerate(paths)
    ]


def hex_fill(color: np.ndarray) -> str:
    red, green, blue = np.clip(color.round(), 0, 255).astype(int)
    return f'fill="#{red:02X}{green:02X}{blue:02X}"'


def label_boxes(ids: np.ndarray, count: int) -> dict[int, tuple[int, int, int, int]]:
    flat = ids.ravel()
    order = np.argsort(flat, kind="stable")
    starts = np.searchsorted(flat[order], np.arange(count + 1))
    ends = np.searchsorted(flat[order], np.arange(count + 1), side="right")
    width = ids.shape[1]
    boxes = {}
    for label in range(1, count + 1):
        members = order[starts[label] : ends[label]]
        if len(members):
            rows, columns = members // width, members % width
            boxes[label] = (int(rows.min()), int(rows.max()) + 1, int(columns.min()), int(columns.max()) + 1)
    return boxes


def split_regions_at_ink(paths: list[str], ids: np.ndarray, ink: np.ndarray) -> tuple[list[str], np.ndarray]:
    split = ids.copy()
    split_paths = list(paths)
    for label, (top, bottom, left, right) in label_boxes(ids, len(paths)).items():
        region = (ids[top:bottom, left:right] == label) & ~ink[top:bottom, left:right]
        count, parts = cv2.connectedComponents(region.astype(np.uint8), connectivity=4)
        for part in range(2, count):
            split_paths.append(paths[label - 1])
            split[top:bottom, left:right][parts == part] = len(split_paths)
    return split_paths, fill_from_nearest(split[..., None], ~ink)[..., 0]
