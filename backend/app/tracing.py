import io
import re

import vtracer
from PIL import Image

MAX_TRACE_SIDE = 3072
PATH_PRECISION = 2
SVG_SIZE_PATTERN = re.compile(r'<svg([^>]*?) width="(\d+)" height="(\d+)"')


def prepare_image(data: bytes) -> bytes:
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((MAX_TRACE_SIDE, MAX_TRACE_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def add_view_box(svg: str) -> str:
    return SVG_SIZE_PATTERN.sub(r'<svg\1 width="\2" height="\3" viewBox="0 0 \2 \3"', svg, count=1)


def trace_to_svg(data: bytes) -> str:
    svg = vtracer.convert_raw_image_to_svg(prepare_image(data), img_format="png", path_precision=PATH_PRECISION)
    return add_view_box(svg)
