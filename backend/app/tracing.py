import re

import numpy as np
import vtracer
from PIL import Image

from app.images import to_png_bytes

MAX_TRACE_SIDE = 3072
PATH_PRECISION = 2
UPSCALE_FACTORS = (8, 6, 5, 4, 3, 2)
UPSCALE_SAMPLE_STEP = 7
UPSCALE_COLOR_STEP = 2
UPSCALE_MIN_CHANGES = 1000
UPSCALE_ALIGNED_SHARE = 0.95
COLOR_PRECISION = 7
COLOR_LENGTH_THRESHOLD = 8
COLOR_LAYER_DIFFERENCE = 12
TRACE_MODE = "polygon"
PATH_PATTERN = re.compile(r"<path [^>]*/>")
BINARY_FILL = 'fill="#000000"'


def downscale_for_tracing(image: Image.Image) -> Image.Image:
    factor = nearest_upscale_factor(np.asarray(image))
    native = image.resize((image.width // factor, image.height // factor), Image.Resampling.NEAREST)
    trace_image = native if factor > 1 else image.copy()
    trace_image.thumbnail((MAX_TRACE_SIDE, MAX_TRACE_SIDE))
    return trace_image


def nearest_upscale_factor(pixels: np.ndarray) -> int:
    rows = pixels[::UPSCALE_SAMPLE_STEP].astype(np.int16)
    columns = np.nonzero(np.abs(np.diff(rows, axis=1)).max(axis=2) > UPSCALE_COLOR_STEP)[1] + 1
    if len(columns) < UPSCALE_MIN_CHANGES:
        return 1
    for factor in UPSCALE_FACTORS:
        if np.bincount(columns % factor, minlength=factor).max() >= UPSCALE_ALIGNED_SHARE * len(columns):
            return factor
    return 1


def trace_paths(image: Image.Image, hierarchical: str = "stacked") -> list[str]:
    svg = vtracer.convert_raw_image_to_svg(
        to_png_bytes(image),
        img_format="png",
        hierarchical=hierarchical,
        mode=TRACE_MODE,
        color_precision=COLOR_PRECISION,
        layer_difference=COLOR_LAYER_DIFFERENCE,
        length_threshold=COLOR_LENGTH_THRESHOLD,
        path_precision=PATH_PRECISION,
    )
    return PATH_PATTERN.findall(svg)


def recolor_binary_path(path: str, color: str) -> str:
    return path.replace(BINARY_FILL, f'fill="{color}"')


def svg_document(size: tuple[int, int], body: str) -> str:
    width, height = size
    return (
        f'<svg version="1.1" xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">{body}</svg>'
    )


def trace_to_svg(image: Image.Image) -> str:
    trace_image = downscale_for_tracing(image)
    return svg_document(trace_image.size, "".join(trace_paths(trace_image)))
