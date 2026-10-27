import re

import numpy as np
import vtracer
from PIL import Image

from app.images import to_png_bytes

MAX_TRACE_SIDE = 3072
PATH_PRECISION = 2
COLOR_PRECISION = 7
COLOR_LENGTH_THRESHOLD = 8
COLOR_LAYER_DIFFERENCE = 12
PATH_PATTERN = re.compile(r"<path [^>]*/>")
BINARY_FILL = 'fill="#000000"'
BINARY_FILTER_SPECKLE = 8
BINARY_CORNER_THRESHOLD = 90
BINARY_LENGTH_THRESHOLD = 6


def downscale_for_tracing(image: Image.Image) -> Image.Image:
    trace_image = image.copy()
    trace_image.thumbnail((MAX_TRACE_SIDE, MAX_TRACE_SIDE))
    return trace_image


def trace_paths(image: Image.Image, hierarchical: str = "stacked") -> list[str]:
    svg = vtracer.convert_raw_image_to_svg(
        to_png_bytes(image),
        img_format="png",
        hierarchical=hierarchical,
        color_precision=COLOR_PRECISION,
        layer_difference=COLOR_LAYER_DIFFERENCE,
        length_threshold=COLOR_LENGTH_THRESHOLD,
        path_precision=PATH_PRECISION,
    )
    return PATH_PATTERN.findall(svg)


def trace_binary_paths(mask: np.ndarray) -> list[str]:
    image = Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).convert("RGB")
    svg = vtracer.convert_raw_image_to_svg(
        to_png_bytes(image),
        img_format="png",
        colormode="binary",
        filter_speckle=BINARY_FILTER_SPECKLE,
        corner_threshold=BINARY_CORNER_THRESHOLD,
        length_threshold=BINARY_LENGTH_THRESHOLD,
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
