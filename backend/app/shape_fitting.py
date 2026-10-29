from dataclasses import dataclass

import cv2
import numpy as np

from app.bezier_fit import Curve, fit_closed_curve, fit_cubic, unit

CORNER_REACH = 4
CORNER_ANGLE = np.radians(50)
CORNER_CONTRAST = 3.0
END_TRIM = 3
MIN_PRIMITIVE_POINTS = 24
PRIMITIVE_RMS = 0.3
PRIMITIVE_MAX = 0.9
MAX_ARC_RADIUS = 2000.0
MIN_ELLIPSE_POINTS = 12
CORNER_SNAP_DISTANCE = 8.0


@dataclass(frozen=True)
class Line:
    origin: np.ndarray
    direction: np.ndarray


@dataclass(frozen=True)
class Circle:
    center: np.ndarray
    radius: float


Primitive = Line | Circle | None


def fit_ring(points: np.ndarray, tolerance: float, snap_shapes: bool) -> list[Curve]:
    ellipse = snapped_ellipse(points) if snap_shapes else None
    if ellipse is not None:
        return fit_closed_curve(ellipse, tolerance)
    corners = find_corners(points)
    if len(corners) == 0:
        return fit_closed_curve(points, tolerance)
    segments = [points[np.arange(start, end + 1) % len(points)] for start, end in corner_spans(corners, len(points))]
    primitives = [segment_primitive(segment) if snap_shapes else None for segment in segments]
    segments = [regularized(segment, primitive) for segment, primitive in zip(segments, primitives)]
    sharpen_corners(segments, primitives)
    return [curve for segment in segments for curve in fit_open_curve(segment, tolerance)]


def corner_spans(corners: np.ndarray, count: int) -> list[tuple[int, int]]:
    ends = np.append(corners[1:], corners[0] + count)
    return list(zip(corners.tolist(), ends.tolist()))


def find_corners(points: np.ndarray) -> np.ndarray:
    count = len(points)
    if count < CORNER_REACH * 6:
        return np.array([], dtype=int)
    angle = turning_angle(points, CORNER_REACH)
    far = np.maximum(np.roll(angle, 2 * CORNER_REACH), np.roll(angle, -2 * CORNER_REACH))
    local_max = angle >= np.max([np.roll(angle, shift) for shift in range(-CORNER_REACH, CORNER_REACH + 1)], axis=0)
    corners = np.flatnonzero((angle > CORNER_ANGLE) & (angle > CORNER_CONTRAST * far) & local_max)
    return dedupe_corners(corners, count)


def turning_angle(points: np.ndarray, reach: int) -> np.ndarray:
    before = points - np.roll(points, reach, axis=0)
    after = np.roll(points, -reach, axis=0) - points
    norms = np.maximum(np.hypot(*before.T) * np.hypot(*after.T), 1e-9)
    return np.arccos(np.clip((before * after).sum(axis=1) / norms, -1, 1))


def dedupe_corners(corners: np.ndarray, count: int) -> np.ndarray:
    kept: list[int] = []
    for corner in corners.tolist():
        if not kept or corner - kept[-1] > CORNER_REACH:
            kept.append(corner)
    if len(kept) > 1 and kept[0] + count - kept[-1] <= CORNER_REACH:
        kept.pop()
    return np.array(kept, dtype=int)


def segment_primitive(segment: np.ndarray) -> Primitive:
    inner = segment[END_TRIM : len(segment) - END_TRIM]
    if len(inner) < MIN_PRIMITIVE_POINTS:
        return None
    line = fit_line(inner)
    if acceptable(line_deviation(inner, line)):
        return line
    circle = fit_circle(inner)
    if circle is not None and acceptable(circle_deviation(inner, circle)):
        return circle
    return None


def acceptable(deviation: np.ndarray) -> bool:
    return float(np.sqrt((deviation**2).mean())) < PRIMITIVE_RMS and float(deviation.max()) < PRIMITIVE_MAX


def fit_line(points: np.ndarray) -> Line:
    origin = points.mean(axis=0)
    _, _, axes = np.linalg.svd(points - origin, full_matrices=False)
    return Line(origin=origin, direction=axes[0])


def line_deviation(points: np.ndarray, line: Line) -> np.ndarray:
    offset = points - line.origin
    return np.abs(offset[:, 0] * line.direction[1] - offset[:, 1] * line.direction[0])


def fit_circle(points: np.ndarray) -> Circle | None:
    x, y = points[:, 0], points[:, 1]
    system = np.stack([x, y, np.ones_like(x)], axis=1)
    solution, *_ = np.linalg.lstsq(system, -(x * x + y * y), rcond=None)
    center = -solution[:2] / 2
    squared = float(center @ center - solution[2])
    if squared <= 0 or squared > MAX_ARC_RADIUS**2:
        return None
    return Circle(center=center, radius=float(np.sqrt(squared)))


def circle_deviation(points: np.ndarray, circle: Circle) -> np.ndarray:
    return np.abs(np.hypot(*(points - circle.center).T) - circle.radius)


def project(points: np.ndarray, primitive: Primitive) -> np.ndarray:
    if isinstance(primitive, Line):
        along = (points - primitive.origin) @ primitive.direction
        return primitive.origin + along[:, None] * primitive.direction
    if isinstance(primitive, Circle):
        offset = points - primitive.center
        lengths = np.maximum(np.hypot(*offset.T), 1e-9)[:, None]
        return primitive.center + offset / lengths * primitive.radius
    return points


def regularized(segment: np.ndarray, primitive: Primitive) -> np.ndarray:
    if primitive is None:
        return segment
    inner = project(segment[END_TRIM : len(segment) - END_TRIM], primitive)
    return np.vstack([segment[:1], inner, segment[-1:]])


def sharpen_corners(segments: list[np.ndarray], primitives: list[Primitive]) -> None:
    for index in range(len(segments)):
        following = (index + 1) % len(segments)
        corner = segments[index][-1]
        sharp = intersection(primitives[index], primitives[following], corner)
        if sharp is not None and float(np.hypot(*(sharp - corner))) < CORNER_SNAP_DISTANCE:
            segments[index][-1] = sharp
            segments[following][0] = sharp


def intersection(first: Primitive, second: Primitive, near: np.ndarray) -> np.ndarray | None:
    if isinstance(first, Line) and isinstance(second, Line):
        return line_intersection(first, second)
    if isinstance(first, Line) and isinstance(second, Circle):
        return closest(line_circle_intersections(first, second), near)
    if isinstance(first, Circle) and isinstance(second, Line):
        return closest(line_circle_intersections(second, first), near)
    if isinstance(first, Circle) and isinstance(second, Circle):
        return closest(circle_intersections(first, second), near)
    return None


def line_intersection(first: Line, second: Line) -> np.ndarray | None:
    matrix = np.stack([first.direction, -second.direction], axis=1)
    if abs(float(np.linalg.det(matrix))) < 1e-6:
        return None
    steps = np.linalg.solve(matrix, second.origin - first.origin)
    return first.origin + steps[0] * first.direction


def line_circle_intersections(line: Line, circle: Circle) -> list[np.ndarray]:
    offset = line.origin - circle.center
    along = float(offset @ line.direction)
    discriminant = along * along - float(offset @ offset) + circle.radius**2
    if discriminant < 0:
        return []
    root = float(np.sqrt(discriminant))
    return [line.origin + (-along + sign * root) * line.direction for sign in (-1, 1)]


def circle_intersections(first: Circle, second: Circle) -> list[np.ndarray]:
    offset = second.center - first.center
    distance = float(np.hypot(*offset))
    if distance < 1e-9 or distance > first.radius + second.radius or distance < abs(first.radius - second.radius):
        return []
    along = (first.radius**2 - second.radius**2 + distance**2) / (2 * distance)
    height = float(np.sqrt(max(first.radius**2 - along**2, 0.0)))
    base = first.center + offset * along / distance
    normal = np.array([-offset[1], offset[0]]) / distance
    return [base + normal * height, base - normal * height]


def closest(candidates: list[np.ndarray], near: np.ndarray) -> np.ndarray | None:
    if not candidates:
        return None
    return min(candidates, key=lambda point: float(np.hypot(*(point - near))))


def fit_open_curve(segment: np.ndarray, tolerance: float) -> list[Curve]:
    if len(segment) < 2:
        return []
    reach = max(1, min(CORNER_REACH, len(segment) - 1))
    left = unit(segment[reach] - segment[0])
    right = unit(segment[-1 - reach] - segment[-1])
    return fit_cubic(segment, left, right, tolerance)


def snapped_ellipse(points: np.ndarray) -> np.ndarray | None:
    if len(points) < MIN_ELLIPSE_POINTS:
        return None
    (center_x, center_y), (width, height), angle = cv2.fitEllipse(points.astype(np.float32))
    if width <= 0 or height <= 0:
        return None
    rotation = np.radians(angle)
    axes = np.array([[np.cos(rotation), np.sin(rotation)], [-np.sin(rotation), np.cos(rotation)]])
    local = (points - [center_x, center_y]) @ axes.T
    scale = np.hypot(local[:, 0] / (width / 2), local[:, 1] / (height / 2))
    on_ellipse = local / np.maximum(scale, 1e-9)[:, None]
    deviation = np.hypot(*(local - on_ellipse).T)
    if not acceptable(deviation):
        return None
    return on_ellipse @ axes + [center_x, center_y]
