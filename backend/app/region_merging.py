import heapq

import cv2
import numpy as np

MERGE_DELTA_E = 3.0
SMALL_MERGE_DELTA_E = 12.0
SMALL_REGION_SHARE = 0.0003
SNAP_BLUR_SIGMA = 1.0
SNAP_ITERATIONS = 3
STRONG_SNAP_BLUR_SIGMA = 0.6
STRONG_SNAP_ITERATIONS = 25
STRONG_EDGE_DELTA_E = 20.0


class RegionGraph:
    def __init__(self, ids: np.ndarray, pixels: np.ndarray, owners: np.ndarray) -> None:
        count = int(ids.max()) + 1
        flat = ids.ravel()
        lab = cv2.cvtColor(pixels.astype(np.float32) / 255, cv2.COLOR_RGB2LAB).reshape(-1, 3)
        self.area = np.bincount(flat, minlength=count).astype(np.float64)
        self.color_sum = np.stack([np.bincount(flat, lab[:, channel], minlength=count) for channel in range(3)], axis=1)
        self.owner = majority_owner(flat, owners.ravel(), count)
        self.neighbors = adjacency(ids, count)
        self.parent = np.arange(count)
        self.version = np.zeros(count, dtype=np.int64)
        self.pixel_count = ids.size

    def color(self, region: int) -> np.ndarray:
        return self.color_sum[region] / max(self.area[region], 1.0)

    def distance(self, first: int, second: int) -> float:
        return float(np.linalg.norm(self.color(first) - self.color(second)))

    def may_merge(self, first: int, second: int, distance: float) -> bool:
        if self.owner[first] != self.owner[second]:
            return False
        small = min(self.area[first], self.area[second]) < SMALL_REGION_SHARE * self.pixel_count
        return distance < (SMALL_MERGE_DELTA_E if small else MERGE_DELTA_E)

    def merge(self, first: int, second: int) -> int:
        keep, gone = (first, second) if self.area[first] >= self.area[second] else (second, first)
        self.parent[gone] = keep
        self.area[keep] += self.area[gone]
        self.color_sum[keep] += self.color_sum[gone]
        self.neighbors[keep] |= self.neighbors.pop(gone)
        self.neighbors[keep] -= {keep, gone}
        for neighbor in self.neighbors[keep]:
            self.neighbors[neighbor].discard(gone)
            self.neighbors[neighbor].add(keep)
        self.version[keep] += 1
        self.version[gone] += 1
        return keep

    def roots(self) -> np.ndarray:
        roots = self.parent.copy()
        while True:
            next_roots = roots[roots]
            if np.array_equal(next_roots, roots):
                return roots
            roots = next_roots


def merge_similar_regions(ids: np.ndarray, pixels: np.ndarray, owners: np.ndarray) -> np.ndarray:
    graph = RegionGraph(ids, pixels, owners)
    queue: list[tuple[float, int, int, int, int]] = []
    for region, neighbors in graph.neighbors.items():
        for neighbor in neighbors:
            if region < neighbor:
                push_pair(queue, graph, region, neighbor)
    while queue:
        distance, first, second, first_version, second_version = heapq.heappop(queue)
        if distance >= SMALL_MERGE_DELTA_E:
            break
        if graph.version[first] != first_version or graph.version[second] != second_version:
            continue
        if not graph.may_merge(first, second, distance):
            continue
        kept = graph.merge(first, second)
        for neighbor in graph.neighbors[kept]:
            push_pair(queue, graph, kept, neighbor)
    return graph.roots()[ids]


def push_pair(queue: list[tuple[float, int, int, int, int]], graph: RegionGraph, first: int, second: int) -> None:
    heapq.heappush(
        queue, (graph.distance(first, second), first, second, int(graph.version[first]), int(graph.version[second]))
    )


def majority_owner(flat_ids: np.ndarray, flat_owners: np.ndarray, count: int) -> np.ndarray:
    owner_count = int(flat_owners.max()) + 2
    pairs = flat_ids.astype(np.int64) * owner_count + (flat_owners + 1)
    counts = np.bincount(pairs, minlength=count * owner_count).reshape(count, owner_count)
    return counts.argmax(axis=1) - 1


def adjacency(ids: np.ndarray, count: int) -> dict[int, set[int]]:
    first = np.concatenate([ids[:, 1:].ravel(), ids[1:, :].ravel()])
    second = np.concatenate([ids[:, :-1].ravel(), ids[:-1, :].ravel()])
    differs = first != second
    pairs = np.unique(np.stack([first[differs], second[differs]], axis=1), axis=0)
    neighbors: dict[int, set[int]] = {int(region): set() for region in np.flatnonzero(np.bincount(ids.ravel(), minlength=count))}
    for a, b in pairs.tolist():
        neighbors[a].add(b)
        neighbors[b].add(a)
    return neighbors


def snap_region_boundaries(ids: np.ndarray, pixels: np.ndarray) -> np.ndarray:
    snapped = snap_boundaries(ids, blurred_lab(pixels, SNAP_BLUR_SIGMA), SNAP_ITERATIONS, 0.0)
    strong_lab = blurred_lab(pixels, STRONG_SNAP_BLUR_SIGMA)
    return snap_boundaries(snapped, strong_lab, STRONG_SNAP_ITERATIONS, STRONG_EDGE_DELTA_E)


def blurred_lab(pixels: np.ndarray, sigma: float) -> np.ndarray:
    return cv2.cvtColor(cv2.GaussianBlur(pixels.astype(np.float32) / 255, (0, 0), sigma), cv2.COLOR_RGB2LAB)


def snap_boundaries(ids: np.ndarray, lab: np.ndarray, iterations: int, min_contrast: float) -> np.ndarray:
    snapped = ids.copy()
    for _ in range(iterations):
        means = region_means(snapped, lab)
        rows, columns = np.nonzero(boundary_pixels(snapped))
        candidates = neighbor_labels(snapped, rows, columns)
        distances = np.linalg.norm(means[candidates] - lab[rows, columns][None], axis=2)
        contrast = np.linalg.norm(means[candidates] - means[candidates[0]][None], axis=2)
        distances[1:][contrast[1:] < min_contrast] = np.inf
        best = candidates[distances.argmin(axis=0), np.arange(len(rows))]
        if np.array_equal(best, candidates[0]):
            break
        snapped[rows, columns] = best
    return snapped


def region_means(ids: np.ndarray, lab: np.ndarray) -> np.ndarray:
    flat = ids.ravel()
    count = int(ids.max()) + 1
    area = np.maximum(np.bincount(flat, minlength=count), 1)
    sums = [np.bincount(flat, lab[..., channel].ravel(), minlength=count) for channel in range(3)]
    return np.stack(sums, axis=1) / area[:, None]


def boundary_pixels(ids: np.ndarray) -> np.ndarray:
    boundary = np.zeros(ids.shape, dtype=bool)
    horizontal = ids[:, 1:] != ids[:, :-1]
    vertical = ids[1:, :] != ids[:-1, :]
    boundary[:, 1:] |= horizontal
    boundary[:, :-1] |= horizontal
    boundary[1:, :] |= vertical
    boundary[:-1, :] |= vertical
    return boundary


def neighbor_labels(ids: np.ndarray, rows: np.ndarray, columns: np.ndarray) -> np.ndarray:
    height, width = ids.shape
    shifts = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
    return np.stack(
        [ids[np.clip(rows + dy, 0, height - 1), np.clip(columns + dx, 0, width - 1)] for dy, dx in shifts]
    )


def region_widths(ids: np.ndarray) -> np.ndarray:
    count = int(ids.max()) + 1
    area = np.bincount(ids.ravel(), minlength=count).astype(np.float64)
    horizontal = ids[:, 1:] != ids[:, :-1]
    vertical = ids[1:, :] != ids[:-1, :]
    sides = [ids[:, 1:][horizontal], ids[:, :-1][horizontal], ids[1:, :][vertical], ids[:-1, :][vertical]]
    perimeter = sum(np.bincount(side, minlength=count) for side in sides).astype(np.float64)
    return np.where(perimeter > 0, 2 * area / np.maximum(perimeter, 1), np.inf)
