import cv2
import numpy as np

from app.nearest_fill import fill_from_nearest

MAX_INK_TONES = 8
SAME_TONE_DELTA_E = 18.0
KMEANS_SAMPLE = 20000
KMEANS_ATTEMPTS = 3
TONE_OVERLAP = 3


def split_ink_by_tone(pixels: np.ndarray, ink: np.ndarray) -> list[np.ndarray]:
    core = ink_core(ink)
    lab = cv2.cvtColor(pixels.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
    tones = merged_tones(lab[core])
    if len(tones) < 2:
        return [ink]
    core_labels = nearest_tone(lab[core], tones)
    labels = np.zeros(ink.shape, dtype=np.int32)
    labels[core] = core_labels
    labels = fill_from_nearest(labels[..., None], core)[..., 0]
    order = np.argsort(-tones[:, 0])
    return [tone_mask(ink, labels, tone) for tone in order if (ink & (labels == tone)).any()]


def ink_core(ink: np.ndarray) -> np.ndarray:
    ink_bytes = ink.astype(np.uint8)
    eroded = cv2.erode(ink_bytes, np.ones((3, 3), np.uint8)) > 0
    near_core = cv2.dilate(eroded.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    return eroded | (ink & ~near_core)


def merged_tones(samples: np.ndarray) -> np.ndarray:
    if len(samples) < MAX_INK_TONES:
        return samples.mean(axis=0, keepdims=True) if len(samples) else np.zeros((0, 3), np.float32)
    rng = np.random.default_rng(0)
    fit = samples[rng.choice(len(samples), min(len(samples), KMEANS_SAMPLE), replace=False)]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, labels, centers = cv2.kmeans(fit, MAX_INK_TONES, None, criteria, KMEANS_ATTEMPTS, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=MAX_INK_TONES).astype(float)
    return merge_close_tones(centers, counts)


def merge_close_tones(centers: np.ndarray, counts: np.ndarray) -> np.ndarray:
    tones = [(center, count) for center, count in zip(centers, counts) if count > 0]
    while len(tones) > 1:
        pairs = [
            (float(np.linalg.norm(tones[a][0] - tones[b][0])), a, b)
            for a in range(len(tones))
            for b in range(a + 1, len(tones))
        ]
        distance, a, b = min(pairs)
        if distance > SAME_TONE_DELTA_E:
            break
        (center_a, count_a), (center_b, count_b) = tones[a], tones[b]
        merged = ((center_a * count_a + center_b * count_b) / (count_a + count_b), count_a + count_b)
        tones = [tone for index, tone in enumerate(tones) if index not in (a, b)] + [merged]
    return np.array([center for center, _ in tones], dtype=np.float32)


def nearest_tone(samples: np.ndarray, tones: np.ndarray) -> np.ndarray:
    distances = np.linalg.norm(samples[:, None, :] - tones[None, :, :], axis=2)
    return distances.argmin(axis=1).astype(np.int32)


def tone_mask(ink: np.ndarray, labels: np.ndarray, tone: int) -> np.ndarray:
    own = (ink & (labels == tone)).astype(np.uint8)
    overlap = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (TONE_OVERLAP, TONE_OVERLAP))
    return ink & (cv2.dilate(own, overlap) > 0)
