import heapq

import cv2
import numpy as np

from app.ink import UNOWNED
from app.nearest_fill import fill_from_nearest
from app.region_merging import adjacency

SurfaceCenter = tuple[int, tuple[float, float]]

FRAGMENT_DELTA_E = 15.0
FRAGMENT_BORDER_SHARE = 0.5


def grow_surfaces(path_owner: np.ndarray, ids: np.ndarray, colors: np.ndarray, surfaces: list[SurfaceCenter]) -> None:
    seeds = surface_seeds(path_owner, ids, surfaces)
    if not seeds:
        return
    lab = lab_colors(colors)
    neighbors = adjacency(ids, len(path_owner))
    queue = [(0.0, region, surface) for surface, region in seeds]
    heapq.heapify(queue)
    while queue:
        _, region, surface = heapq.heappop(queue)
        if path_owner[region] != UNOWNED:
            continue
        path_owner[region] = surface
        for neighbor in neighbors.get(region, ()):
            if path_owner[neighbor] == UNOWNED:
                edge = float(np.linalg.norm(lab[region] - lab[neighbor]))
                heapq.heappush(queue, (edge, neighbor, surface))


def lab_colors(colors: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(colors.reshape(-1, 1, 3).astype(np.float32) / 255, cv2.COLOR_RGB2LAB).reshape(-1, 3)


def attach_object_fragments(path_owner: np.ndarray, ids: np.ndarray, colors: np.ndarray) -> None:
    regions, neighbors, lengths = border_lengths(ids, len(path_owner))
    perimeter = np.bincount(regions, weights=lengths, minlength=len(path_owner))
    lab = lab_colors(colors)
    owner = path_owner.copy()
    candidate = (owner[regions] == UNOWNED) & (owner[neighbors] != UNOWNED)
    candidate &= np.linalg.norm(lab[regions] - lab[neighbors], axis=1) < FRAGMENT_DELTA_E
    shared: dict[tuple[int, int], float] = {}
    for region, neighbor, length in zip(regions[candidate], neighbors[candidate], lengths[candidate]):
        key = (int(region), int(owner[neighbor]))
        shared[key] = shared.get(key, 0.0) + float(length)
    for (region, layer), length in shared.items():
        if length >= FRAGMENT_BORDER_SHARE * perimeter[region]:
            path_owner[region] = layer


def border_lengths(ids: np.ndarray, count: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    first = np.concatenate([ids[:, 1:].ravel(), ids[1:, :].ravel()]).astype(np.int64)
    second = np.concatenate([ids[:, :-1].ravel(), ids[:-1, :].ravel()]).astype(np.int64)
    differs = first != second
    pairs = np.concatenate([first[differs] * count + second[differs], second[differs] * count + first[differs]])
    keys, lengths = np.unique(pairs, return_counts=True)
    return keys // count, keys % count, lengths


def surface_seeds(path_owner: np.ndarray, ids: np.ndarray, surfaces: list[SurfaceCenter]) -> list[tuple[int, int]]:
    free = path_owner[ids] == UNOWNED
    if not free.any():
        return []
    nearest = fill_from_nearest(ids[..., None], free)[..., 0]
    height, width = ids.shape
    seeds: dict[int, int] = {}
    for surface, (x, y) in surfaces:
        seeds.setdefault(int(nearest[min(int(y), height - 1), min(int(x), width - 1)]), surface)
    return [(surface, region) for region, surface in seeds.items()]


def split_contested_regions(
    paths: list[str], ids: np.ndarray, owners: np.ndarray, surfaces: list[SurfaceCenter]
) -> tuple[list[str], np.ndarray]:
    free = owners == UNOWNED
    if not free.any() or not surfaces:
        return paths, ids
    nearest_region = fill_from_nearest(ids[..., None], free)[..., 0]
    anchors = anchor_map(ids.shape, surfaces)
    claims: dict[int, set[int]] = {}
    for (row, column), surface in anchors.items():
        claims.setdefault(int(nearest_region[row, column]), set()).add(surface)
    contested = [region for region, claimants in claims.items() if len(claimants) > 1]
    if not contested:
        return paths, ids
    seeds = np.zeros(ids.shape, dtype=np.int64)
    for (row, column), surface in anchors.items():
        seeds[row, column] = surface + 1
    closest = fill_from_nearest(seeds[..., None], seeds > 0)[..., 0]
    split = ids.copy()
    split_paths = list(paths)
    for region in contested:
        inside = (ids == region) & free
        for surface in sorted(claims[region])[1:]:
            split_paths.append(paths[region - 1])
            split[inside & (closest == surface + 1)] = len(split_paths)
    return split_paths, split


def anchor_map(shape: tuple[int, ...], surfaces: list[SurfaceCenter]) -> dict[tuple[int, int], int]:
    height, width = shape[:2]
    return {(min(int(y), height - 1), min(int(x), width - 1)): surface for surface, (x, y) in surfaces}
