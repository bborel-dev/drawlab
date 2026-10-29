from typing import Iterator

import numpy as np
from PIL import Image

FLAT_RANGE = 14
WINDOW_RADIUS = 4
MAX_BLEND_RESIDUAL = 28.0
MIN_SIDE_CONTRAST = 40.0
MIN_EDGE_SHARPNESS = 0.3


def snap_edge_blends(image: Image.Image) -> Image.Image:
    pixels = np.asarray(image).astype(np.float32)
    local_range = neighborhood_range(pixels)
    flat = local_range <= FLAT_RANGE
    blended = ~flat
    blended[:WINDOW_RADIUS, :] = blended[-WINDOW_RADIUS:, :] = False
    blended[:, :WINDOW_RADIUS] = blended[:, -WINDOW_RADIUS:] = False
    rows, columns = np.nonzero(blended)
    snapped = snap_colors(pixels, flat, local_range[rows, columns], rows, columns)
    result = pixels.copy()
    result[rows, columns] = snapped
    return Image.fromarray(result.round().astype(np.uint8))


def neighborhood_range(pixels: np.ndarray) -> np.ndarray:
    padded = np.pad(pixels, ((1, 1), (1, 1), (0, 0)), mode="edge")
    height, width = pixels.shape[:2]
    shifts = [padded[1 + dy : 1 + dy + height, 1 + dx : 1 + dx + width] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
    stack = np.stack(shifts)
    return (stack.max(axis=0) - stack.min(axis=0)).max(axis=2)


def window_offsets() -> list[tuple[int, int]]:
    span = range(-WINDOW_RADIUS, WINDOW_RADIUS + 1)
    return [(dy, dx) for dy in span for dx in span if (dy, dx) != (0, 0)]


def snap_colors(
    pixels: np.ndarray, flat: np.ndarray, local_range: np.ndarray, rows: np.ndarray, columns: np.ndarray
) -> np.ndarray:
    colors = pixels[rows, columns]
    nearest = nearest_flat_neighbor(pixels, flat, rows, columns)
    best_residual = np.full(len(colors), np.inf, dtype=np.float32)
    best_choice = colors.copy()
    for other, other_flat in neighbors(pixels, flat, rows, columns):
        residual, toward_other = blend_fit(colors, nearest, other)
        contrast = np.linalg.norm(other - nearest, axis=1)
        sharp = local_range >= contrast * MIN_EDGE_SHARPNESS
        valid = other_flat & sharp & (contrast >= MIN_SIDE_CONTRAST) & (residual < best_residual)
        best_residual = np.where(valid, residual, best_residual)
        best_choice = np.where((valid & toward_other)[:, None], other, np.where(valid[:, None], nearest, best_choice))
    return np.where((best_residual <= MAX_BLEND_RESIDUAL)[:, None], best_choice, colors)


def neighbors(
    pixels: np.ndarray, flat: np.ndarray, rows: np.ndarray, columns: np.ndarray
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    for dy, dx in window_offsets():
        yield pixels[rows + dy, columns + dx], flat[rows + dy, columns + dx]


def nearest_flat_neighbor(pixels: np.ndarray, flat: np.ndarray, rows: np.ndarray, columns: np.ndarray) -> np.ndarray:
    colors = pixels[rows, columns]
    best_distance = np.full(len(colors), np.inf, dtype=np.float32)
    nearest = colors.copy()
    for neighbor, neighbor_flat in neighbors(pixels, flat, rows, columns):
        distance = np.where(neighbor_flat, np.linalg.norm(neighbor - colors, axis=1), np.inf)
        closer = distance < best_distance
        best_distance = np.where(closer, distance, best_distance)
        nearest = np.where(closer[:, None], neighbor, nearest)
    return nearest


def blend_fit(colors: np.ndarray, start: np.ndarray, end: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    direction = end - start
    length_squared = np.maximum((direction**2).sum(axis=1), 1e-6)
    t = np.clip(((colors - start) * direction).sum(axis=1) / length_squared, 0, 1)
    residual = np.linalg.norm(colors - (start + t[:, None] * direction), axis=1)
    return residual, t > 0.5
