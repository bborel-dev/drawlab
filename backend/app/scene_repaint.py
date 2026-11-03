import io
import re
from dataclasses import dataclass

import resvg_py
from PIL import Image

from app.images import fit_within, from_data_url
from app.model_client import ModelClient

MAX_IMAGE_EDIT_SIDE = 1536
EMBEDDED_IMAGE = re.compile(r"<image\b[^>]*(?:/>|>.*?</image>)", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class ProposalRequest:
    image_prompt: str
    svg: str = ""
    image: str = ""


@dataclass(frozen=True)
class RedrawRequest:
    image: str
    width: int
    height: int
    layer_names: list[str]


def render_drawing(svg: str) -> Image.Image:
    png = resvg_py.svg_to_bytes(svg_string=EMBEDDED_IMAGE.sub("", svg), background="#ffffff")
    return Image.open(io.BytesIO(png)).convert("RGB")


def proposed_scene(client: ModelClient, request: ProposalRequest) -> Image.Image:
    source = from_data_url(request.image) if request.image else render_drawing(request.svg)
    return client.edit_image(model_sized(source), request.image_prompt)


def accepted_scene(request: RedrawRequest) -> Image.Image:
    return from_data_url(request.image).resize((request.width, request.height), Image.Resampling.LANCZOS)


def edited_image(client: ModelClient, image: Image.Image, prompt: str) -> Image.Image:
    return client.edit_image(model_sized(image), prompt).resize(image.size, Image.Resampling.LANCZOS)


def model_sized(image: Image.Image) -> Image.Image:
    return fit_within(image, MAX_IMAGE_EDIT_SIDE)
