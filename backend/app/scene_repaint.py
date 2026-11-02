import io
import re
from dataclasses import dataclass

import resvg_py
from PIL import Image

from app.model_client import ModelClient

MAX_IMAGE_EDIT_SIDE = 1536
EMBEDDED_IMAGE = re.compile(r"<image\b[^>]*(?:/>|>.*?</image>)", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class RepaintRequest:
    svg: str
    image_prompt: str
    layer_names: list[str]


def render_drawing(svg: str) -> Image.Image:
    png = resvg_py.svg_to_bytes(svg_string=EMBEDDED_IMAGE.sub("", svg), background="#ffffff")
    return Image.open(io.BytesIO(png)).convert("RGB")


def repainted_scene(client: ModelClient, request: RepaintRequest) -> Image.Image:
    drawing = render_drawing(request.svg)
    sent = drawing.copy()
    sent.thumbnail((MAX_IMAGE_EDIT_SIDE, MAX_IMAGE_EDIT_SIDE))
    return client.edit_image(sent, request.image_prompt).resize(drawing.size, Image.Resampling.LANCZOS)
