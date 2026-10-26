from meta_sam_parser import (
    CompletedOutcome,
    SegmentationMaskRecord,
    decode_mask_to_raster,
    image_segmentation_format,
)
from PIL import Image


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
