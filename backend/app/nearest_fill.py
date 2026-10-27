import cv2
import numpy as np


def fill_from_nearest(pixels: np.ndarray, keep: np.ndarray) -> np.ndarray:
    fill_mask = (~keep).astype(np.uint8) * 255
    _, labels = cv2.distanceTransformWithLabels(fill_mask, cv2.DIST_L2, cv2.DIST_MASK_5, labelType=cv2.DIST_LABEL_PIXEL)
    nearest_color = np.zeros((labels.max() + 1, pixels.shape[2]), dtype=pixels.dtype)
    nearest_color[labels[keep]] = pixels[keep]
    return nearest_color[labels]
