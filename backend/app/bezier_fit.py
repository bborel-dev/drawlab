import numpy as np

MAX_REPARAMETERIZE = 4
REPARAMETERIZE_FACTOR = 4.0
TANGENT_REACH = 4

Curve = np.ndarray


def fit_closed_curve(points: np.ndarray, tolerance: float) -> list[Curve]:
    closed = np.vstack([points, points[:1]])
    reach = min(TANGENT_REACH, (len(points) - 1) // 2)
    tangent = unit(points[reach] - points[-reach]) if reach else unit(points[1] - points[0])
    return fit_cubic(closed, tangent, -tangent, tolerance)


def fit_cubic(points: np.ndarray, left_tangent: np.ndarray, right_tangent: np.ndarray, tolerance: float) -> list[Curve]:
    if len(points) == 2:
        return [straight_curve(points[0], points[1], left_tangent, right_tangent)]
    parameters = chord_length_parameters(points)
    curve = generate_curve(points, parameters, left_tangent, right_tangent)
    error, split = max_error(points, curve, parameters)
    if error < tolerance:
        return [curve]
    if error < tolerance * REPARAMETERIZE_FACTOR:
        for _ in range(MAX_REPARAMETERIZE):
            parameters = reparameterize(points, parameters, curve)
            curve = generate_curve(points, parameters, left_tangent, right_tangent)
            error, split = max_error(points, curve, parameters)
            if error < tolerance:
                return [curve]
    split = min(max(split, 1), len(points) - 2)
    reach = min(TANGENT_REACH, split, len(points) - 1 - split)
    center = unit(points[split - reach] - points[split + reach])
    return fit_cubic(points[: split + 1], left_tangent, center, tolerance) + fit_cubic(
        points[split:], -center, right_tangent, tolerance
    )


def unit(vector: np.ndarray) -> np.ndarray:
    length = float(np.hypot(vector[0], vector[1]))
    return vector / length if length > 1e-9 else np.zeros(2)


def straight_curve(start: np.ndarray, end: np.ndarray, left: np.ndarray, right: np.ndarray) -> Curve:
    reach = float(np.hypot(*(end - start))) / 3
    return np.array([start, start + left * reach, end + right * reach, end])


def chord_length_parameters(points: np.ndarray) -> np.ndarray:
    lengths = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(points, axis=0).T))])
    return lengths / lengths[-1] if lengths[-1] > 0 else np.linspace(0, 1, len(points))


def bernstein(parameters: np.ndarray) -> np.ndarray:
    inverse = 1 - parameters
    return np.stack([inverse**3, 3 * parameters * inverse**2, 3 * parameters**2 * inverse, parameters**3], axis=1)


def generate_curve(points: np.ndarray, parameters: np.ndarray, left: np.ndarray, right: np.ndarray) -> Curve:
    start, end = points[0], points[-1]
    basis = bernstein(parameters)
    a_left = basis[:, 1:2] * left
    a_right = basis[:, 2:3] * right
    c00 = float((a_left * a_left).sum())
    c01 = float((a_left * a_right).sum())
    c11 = float((a_right * a_right).sum())
    baseline = (basis[:, 0:1] + basis[:, 1:2]) * start + (basis[:, 2:3] + basis[:, 3:4]) * end
    residual = points - baseline
    x0 = float((a_left * residual).sum())
    x1 = float((a_right * residual).sum())
    determinant = c00 * c11 - c01 * c01
    chord = float(np.hypot(*(end - start)))
    alpha_left = alpha_right = 0.0
    if abs(determinant) > 1e-12:
        alpha_left = (x0 * c11 - x1 * c01) / determinant
        alpha_right = (c00 * x1 - c01 * x0) / determinant
    arc = float(np.hypot(*np.diff(points, axis=0).T).sum())
    if min(alpha_left, alpha_right) < chord * 1e-6 or max(alpha_left, alpha_right) > arc:
        alpha_left = alpha_right = chord / 3
    return np.array([start, start + left * alpha_left, end + right * alpha_right, end])


def evaluate(curve: Curve, parameters: np.ndarray) -> np.ndarray:
    return bernstein(parameters) @ curve


def max_error(points: np.ndarray, curve: Curve, parameters: np.ndarray) -> tuple[float, int]:
    distances = np.hypot(*(evaluate(curve, parameters) - points).T)
    split = int(distances[1:-1].argmax()) + 1
    return float(distances[split]), split


def reparameterize(points: np.ndarray, parameters: np.ndarray, curve: Curve) -> np.ndarray:
    first = 3 * np.diff(curve, axis=0)
    second = 2 * np.diff(first, axis=0)
    inverse = 1 - parameters
    value = evaluate(curve, parameters)
    derivative = (
        (inverse**2)[:, None] * first[0] + (2 * parameters * inverse)[:, None] * first[1] + (parameters**2)[:, None] * first[2]
    )
    second_derivative = inverse[:, None] * second[0] + parameters[:, None] * second[1]
    difference = value - points
    numerator = (difference * derivative).sum(axis=1)
    denominator = (derivative * derivative).sum(axis=1) + (difference * second_derivative).sum(axis=1)
    step = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=np.abs(denominator) > 1e-12)
    return np.clip(parameters - step, 0, 1)
