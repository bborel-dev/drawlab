import re

import vtracer
from PIL import Image

from app.images import to_png_bytes

MAX_TRACE_SIDE = 3072
PATH_PRECISION = 2
SVG_SIZE_PATTERN = re.compile(r'<svg([^>]*?) width="(\d+)" height="(\d+)"')


def downscale_for_tracing(image: Image.Image) -> Image.Image:
    trace_image = image.copy()
    trace_image.thumbnail((MAX_TRACE_SIDE, MAX_TRACE_SIDE))
    return trace_image


def add_view_box(svg: str) -> str:
    return SVG_SIZE_PATTERN.sub(r'<svg\1 width="\2" height="\3" viewBox="0 0 \2 \3"', svg, count=1)


def trace_to_svg(image: Image.Image) -> str:
    png = to_png_bytes(downscale_for_tracing(image))
    svg = vtracer.convert_raw_image_to_svg(png, img_format="png", path_precision=PATH_PRECISION)
    return add_view_box(svg)
