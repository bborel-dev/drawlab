import re

import vtracer
from PIL import Image

from app.images import to_png_bytes

MAX_TRACE_SIDE = 3072
PATH_PRECISION = 2
PATH_PATTERN = re.compile(r"<path [^>]*/>")


def downscale_for_tracing(image: Image.Image) -> Image.Image:
    trace_image = image.copy()
    trace_image.thumbnail((MAX_TRACE_SIDE, MAX_TRACE_SIDE))
    return trace_image


def trace_paths(image: Image.Image) -> list[str]:
    svg = vtracer.convert_raw_image_to_svg(to_png_bytes(image), img_format="png", path_precision=PATH_PRECISION)
    return PATH_PATTERN.findall(svg)


def svg_document(size: tuple[int, int], body: str) -> str:
    width, height = size
    return (
        f'<svg version="1.1" xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">{body}</svg>'
    )


def trace_to_svg(image: Image.Image) -> str:
    trace_image = downscale_for_tracing(image)
    return svg_document(trace_image.size, "".join(trace_paths(trace_image)))
