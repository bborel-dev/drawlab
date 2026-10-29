import cv2
import numpy as np

from app.region_merging import region_widths

THIN_STROKE_WIDTH = 3.0
CENTERLINE_SIGMA = 2.0
WIDTH_SIGMA = 3.0
WIDTH_WINDOW = 7
MIN_WIDTH = 0.8
CAP_POINTS = 7
MIN_SPUR_POINTS = 3

Pixel = tuple[int, int]
NEIGHBOR_OFFSETS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def split_thin_strokes(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    count, labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    if count < 2:
        return mask, np.zeros_like(mask)
    thin = mask & (region_widths(labels)[labels] < THIN_STROKE_WIDTH)
    return mask & ~thin, thin


def stroke_rings(mask: np.ndarray) -> list[tuple[list[np.ndarray], float]]:
    if not mask.any():
        return []
    skeleton = skeletonize(mask)
    widths = local_widths(mask, skeleton)
    shapes = []
    for line, closed in trace_centerlines(skeleton):
        points = np.array([(column + 0.5, row + 0.5) for row, column in line], dtype=np.float64)
        half_widths = np.array([widths[row, column] for row, column in line]) / 2
        shapes.append((stroke_outline(points, half_widths, closed), float(half_widths.mean() * 2)))
    return shapes


def skeletonize(mask: np.ndarray) -> np.ndarray:
    image = mask.astype(np.uint8)
    while True:
        changed = False
        for step in (0, 1):
            removable = thinning_candidates(image, step)
            if removable.any():
                image[removable] = 0
                changed = True
        if not changed:
            return image.astype(bool)


def thinning_candidates(image: np.ndarray, step: int) -> np.ndarray:
    padded = np.pad(image, 1)
    north, north_east, east = padded[:-2, 1:-1], padded[:-2, 2:], padded[1:-1, 2:]
    south_east, south, south_west = padded[2:, 2:], padded[2:, 1:-1], padded[2:, :-2]
    west, north_west = padded[1:-1, :-2], padded[:-2, :-2]
    ring = [north, north_east, east, south_east, south, south_west, west, north_west, north]
    count = sum(ring[:8])
    transitions = sum((ring[index] == 0) & (ring[index + 1] == 1) for index in range(8))
    if step == 0:
        first, second = north * east * south, east * south * west
    else:
        first, second = north * east * west, north * south * west
    return (image == 1) & (count >= 2) & (count <= 6) & (transitions == 1) & (first == 0) & (second == 0)


def local_widths(mask: np.ndarray, skeleton: np.ndarray) -> np.ndarray:
    window = (WIDTH_WINDOW, WIDTH_WINDOW)
    area = cv2.boxFilter(mask.astype(np.float32), -1, window, normalize=False)
    length = cv2.boxFilter(skeleton.astype(np.float32), -1, window, normalize=False)
    inside = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    widest = 2 * cv2.dilate(inside, np.ones((3, 3), np.uint8))
    return np.clip(area / np.maximum(length, 1), MIN_WIDTH, np.maximum(widest, MIN_WIDTH))


def trace_centerlines(skeleton: np.ndarray) -> list[tuple[list[Pixel], bool]]:
    rows, columns = np.nonzero(skeleton)
    pixels = set(zip(rows.tolist(), columns.tolist()))
    links = {pixel: linked_neighbors(pixel, pixels) for pixel in pixels}
    nodes = {pixel for pixel, neighbors in links.items() if len(neighbors) != 2}
    walked: set[frozenset[Pixel]] = set()
    lines: list[tuple[list[Pixel], bool]] = []
    for node in nodes:
        if not links[node]:
            lines.append(([node], False))
        for neighbor in links[node]:
            if frozenset((node, neighbor)) not in walked:
                lines.append((walk(node, neighbor, links, nodes, walked), False))
    for pixel in pixels:
        if pixel not in nodes and any(frozenset((pixel, other)) not in walked for other in links[pixel]):
            loop = walk(pixel, links[pixel][0], links, nodes, walked)
            lines.append((loop[:-1] if loop[-1] == pixel else loop, True))
    return [(line, closed) for line, closed in lines if not is_spur(line, links)]


def linked_neighbors(pixel: Pixel, pixels: set[Pixel]) -> list[Pixel]:
    row, column = pixel
    straight = [(row + dy, column + dx) for dy, dx in NEIGHBOR_OFFSETS[:4] if (row + dy, column + dx) in pixels]
    diagonal = [
        (row + dy, column + dx)
        for dy, dx in NEIGHBOR_OFFSETS[4:]
        if (row + dy, column + dx) in pixels and (row + dy, column) not in pixels and (row, column + dx) not in pixels
    ]
    return straight + diagonal


def walk(
    start: Pixel, first: Pixel, links: dict[Pixel, list[Pixel]], nodes: set[Pixel], walked: set[frozenset[Pixel]]
) -> list[Pixel]:
    line = [start]
    previous, current = start, first
    walked.add(frozenset((start, first)))
    while True:
        line.append(current)
        if current in nodes or current == start:
            return line
        following = [pixel for pixel in links[current] if pixel != previous and frozenset((current, pixel)) not in walked]
        if not following:
            return line
        walked.add(frozenset((current, following[0])))
        previous, current = current, following[0]


def is_spur(line: list[Pixel], links: dict[Pixel, list[Pixel]]) -> bool:
    if len(line) >= MIN_SPUR_POINTS:
        return False
    return len(line) > 1 and len(links[line[0]]) > 2 or len(links[line[-1]]) > 2


def stroke_outline(points: np.ndarray, half_widths: np.ndarray, closed: bool) -> list[np.ndarray]:
    if len(points) == 1:
        return [dot_ring(points[0], max(half_widths[0], MIN_WIDTH / 2))]
    center = smooth_along(points, CENTERLINE_SIGMA, closed)
    half = smooth_along(half_widths[:, None], WIDTH_SIGMA, closed)[:, 0]
    normals = line_normals(center, closed)
    left, right = center + normals * half[:, None], center - normals * half[:, None]
    if closed:
        return [left, right[::-1]]
    end_cap = cap(center[-1], normals[-1], half[-1])
    start_cap = cap(center[0], -normals[0], half[0])
    return [np.vstack([left, end_cap, right[::-1], start_cap])]


def smooth_along(values: np.ndarray, sigma: float, closed: bool) -> np.ndarray:
    count = len(values)
    reach = min(int(3 * sigma), count - 1)
    if reach < 1:
        return values.astype(np.float64)
    offsets = np.arange(-reach, reach + 1)
    weights = np.exp(-(offsets**2) / (2 * sigma**2))
    weights /= weights.sum()
    if closed:
        extended = np.vstack([values[-reach:], values, values[:reach]])
    else:
        before = 2 * values[0] - values[reach:0:-1]
        after = 2 * values[-1] - values[-2 : -reach - 2 : -1]
        extended = np.vstack([before, values, after])
    return np.stack(
        [np.convolve(extended[:, axis], weights, mode="valid") for axis in range(values.shape[1])], axis=1
    )


def line_normals(center: np.ndarray, closed: bool) -> np.ndarray:
    if closed:
        tangents = np.roll(center, -1, axis=0) - np.roll(center, 1, axis=0)
    else:
        tangents = np.gradient(center, axis=0)
    lengths = np.maximum(np.hypot(*tangents.T), 1e-9)[:, None]
    tangents = tangents / lengths
    return np.stack([-tangents[:, 1], tangents[:, 0]], axis=1)


def cap(center: np.ndarray, normal: np.ndarray, half_width: float) -> np.ndarray:
    angles = np.linspace(0, np.pi, CAP_POINTS + 2)[1:-1]
    forward = np.array([normal[1], -normal[0]])
    return center + half_width * (np.cos(angles)[:, None] * normal + np.sin(angles)[:, None] * forward)


def dot_ring(center: np.ndarray, radius: float) -> np.ndarray:
    angles = np.linspace(0, 2 * np.pi, 2 * CAP_POINTS, endpoint=False)
    return center + radius * np.stack([np.cos(angles), np.sin(angles)], axis=1)
