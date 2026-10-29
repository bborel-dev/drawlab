import cv2
import numpy as np
from meta_sam_parser import (
    CompletedOutcome,
    SegmentationMaskRecord,
    decode_mask_to_raster,
    image_segmentation_format,
)
from PIL import Image

OUTLINE_TOLERANCE = 1.5


def parse_mask_records(output_text: str) -> list[SegmentationMaskRecord]:
    parser = image_segmentation_format().create_parser()
    parser.push(output_text)
    result = parser.finish(CompletedOutcome()).result
    return [record for record in result.records if isinstance(record, SegmentationMaskRecord)]


def render_mask(record: SegmentationMaskRecord, size: tuple[int, int]) -> Image.Image:
    raster = decode_mask_to_raster(record.mask)
    mask = Image.frombytes("L", (record.mask.width, record.mask.height), raster).point(lambda value: 255 if value else 0)
    left, top = round(record.bounds.left), round(record.bounds.top)
    box_size = (max(1, round(record.bounds.right) - left), max(1, round(record.bounds.bottom) - top))
    canvas = Image.new("L", size, 0)
    canvas.paste(mask.resize(box_size, Image.Resampling.NEAREST), (left, top))
    return canvas


def bounds_center(record: SegmentationMaskRecord) -> tuple[float, float]:
    bounds = record.bounds
    return ((bounds.left + bounds.right) / 2, (bounds.top + bounds.bottom) / 2)


def distance_to_bounds(record: SegmentationMaskRecord, point: tuple[float, float]) -> float:
    bounds = record.bounds
    dx = max(bounds.left - point[0], 0.0, point[0] - bounds.right)
    dy = max(bounds.top - point[1], 0.0, point[1] - bounds.bottom)
    return (dx**2 + dy**2) ** 0.5


def mask_outline(mask: Image.Image) -> str:
    binary = (np.asarray(mask) > 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    simplified = (cv2.approxPolyDP(contour, OUTLINE_TOLERANCE, True) for contour in contours)
    return "".join(contour_path(contour) for contour in simplified if len(contour) >= 3)


def contour_path(contour: np.ndarray) -> str:
    points = [f"{x} {y}" for x, y in contour.reshape(-1, 2)]
    return "M" + "L".join(points) + "Z"
