import re
from dataclasses import dataclass, replace
from typing import Any, Literal

from PIL import Image

from app.images import downscale_for_models, to_data_url
from app.model_client import ModelClient

MAX_ELEMENTS = 25

ElementKind = Literal["object", "surface"]

ART_DIRECTOR_PROMPT = """You are the art director of a vector drawing studio.
Break this image into the visual elements an illustrator would draw as separate layers.
For each element give:
- name: a short, unique, kebab-case layer name, such as "man-figure" or "left-potted-plant".
- description: one sentence about its shape and color.
- sam_prompt: a generic noun phrase of one to three words naming what the element is, such as "potted plant" or "wooden chair".
  A segmentation model reads it and ignores positions, so never use words like left, right, front, back, top or bottom.
- kind: "object" for things with a clear outline (people, furniture, plants, cups, lamps),
  "surface" for backgrounds and large areas (sky, wall, ground, floor, pavement).
- center_x and center_y: the approximate center of the element as fractions of the image width and height,
  from 0 (left or top) to 1 (right or bottom).
List the elements in drawing order: surfaces first, then large objects, then small details.
Use between 5 and 25 elements and prefer whole objects over tiny parts.
Also give the overall style and the main palette as hex colors."""

ART_DIRECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["style", "palette", "elements"],
    "properties": {
        "style": {"type": "string"},
        "palette": {"type": "array", "items": {"type": "string"}},
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "description", "sam_prompt", "kind", "center_x", "center_y"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "sam_prompt": {"type": "string"},
                    "kind": {"type": "string", "enum": ["object", "surface"]},
                    "center_x": {"type": "number"},
                    "center_y": {"type": "number"},
                },
            },
        },
    },
}


@dataclass(frozen=True)
class Element:
    name: str
    description: str
    sam_prompt: str
    kind: ElementKind
    center: tuple[float, float]


@dataclass(frozen=True)
class ArtDirection:
    style: str
    palette: list[str]
    elements: list[Element]


def ask_art_director(client: ModelClient, image: Image.Image) -> ArtDirection:
    image_url = to_data_url(downscale_for_models(image))
    raw = client.ask_for_json(ART_DIRECTOR_PROMPT, image_url, "ArtDirection", ART_DIRECTION_SCHEMA)
    return parse_art_direction(raw)


def parse_art_direction(raw: dict[str, Any]) -> ArtDirection:
    elements = [parse_element(item) for item in raw["elements"][:MAX_ELEMENTS]]
    return ArtDirection(style=raw["style"], palette=list(raw["palette"]), elements=with_unique_names(elements))


def parse_element(item: dict[str, Any]) -> Element:
    return Element(
        name=to_layer_name(item["name"]),
        description=item["description"],
        sam_prompt=item["sam_prompt"].strip(),
        kind="surface" if item["kind"] == "surface" else "object",
        center=(clamp_fraction(item["center_x"]), clamp_fraction(item["center_y"])),
    )


def to_layer_name(raw_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", raw_name.lower()).strip("-") or "element"


def clamp_fraction(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def with_unique_names(elements: list[Element]) -> list[Element]:
    seen: dict[str, int] = {}
    unique: list[Element] = []
    for element in elements:
        seen[element.name] = seen.get(element.name, 0) + 1
        count = seen[element.name]
        unique.append(element if count == 1 else replace(element, name=f"{element.name}-{count}"))
    return unique
