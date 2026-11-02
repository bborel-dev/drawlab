import re
from dataclasses import dataclass, replace
from typing import Any, Literal

from PIL import Image

from app.images import downscale_for_models, to_data_url
from app.model_client import ModelClient, ReasoningEffort

MAX_ELEMENTS = 30
MAX_ANCHORS = 4
RESERVED_NAMES = ("background-color",)

ElementKind = Literal["object", "surface"]
OutlineKind = Literal["smooth", "detailed"]

ART_DIRECTOR_PROMPT = """You are the art director of a vector drawing studio.
Break this image into the visual elements an illustrator would draw as separate layers.
A designer will then move each main object on its own, so every distinct object is its own element,
never merged with its neighbors: each person, animal, piece of furniture, potted plant, cup, lamp, building,
cloud, tree or vehicle. Keep each object whole: a person with their clothes and hair, a potted plant with its pot,
a house with its roof, door and windows.
For each element give:
- name: a short, unique, kebab-case layer name, such as "man-figure" or "left-potted-plant".
- description: one sentence about its shape and color.
- sam_prompt: a generic noun phrase of one to three words naming what the element is, such as "potted plant" or "wooden chair".
  A segmentation model reads it and ignores positions, so never use words like left, right, front, back, top or bottom.
- kind: "object" for things with a clear outline (people, furniture, plants, cups, lamps),
  "surface" for backgrounds and large areas (sky, wall, ground, floor, pavement).
- outline: how faithfully the illustrator must follow its silhouette.
  "smooth" for clean shapes the drawing should simplify into flowing curves, perfect circles and straight lines,
  ignoring jitter and compression noise (logos, buildings, furniture, people, clothes, hills, flat-design shapes).
  "detailed" for intricate silhouettes whose every spike, notch and tip matters
  (tree foliage, pine needles, grass, fur, hair strands, flames, splashes, lace, lettering).
- group: true only when the element is many small copies of the same thing that the segmentation model must find
  together, such as a flock of birds, scattered stars or a row of distant trees; each copy still becomes its own layer.
  False when it is one single thing.
- center_x and center_y: the approximate center of the element as fractions of the image width and height,
  from 0 (left or top) to 1 (right or bottom).
- anchors: one to four points, in the same fractions, that land on clearly visible parts of the element,
  away from its edges and never on another element in front of it.
  When an element shows in several separate parts, such as a wall on both sides of a window, put one point in each part.
List the elements from back to front, in the order a painter would paint them: surfaces first, then objects,
each object after every element it covers. A person sitting on a chair comes after the chair,
and a cup on a table comes after the table.
Name each object after the thing itself, such as "man-figure" with the sam_prompt "man",
never after a material or a color such as "skin".
Use between 5 and 30 elements.
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
                "required": [
                    "name",
                    "description",
                    "sam_prompt",
                    "kind",
                    "outline",
                    "group",
                    "center_x",
                    "center_y",
                    "anchors",
                ],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "sam_prompt": {"type": "string"},
                    "kind": {"type": "string", "enum": ["object", "surface"]},
                    "outline": {"type": "string", "enum": ["smooth", "detailed"]},
                    "group": {"type": "boolean"},
                    "center_x": {"type": "number"},
                    "center_y": {"type": "number"},
                    "anchors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["x", "y"],
                            "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                        },
                    },
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
    group: bool = False
    outline: OutlineKind = "smooth"
    anchors: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class ArtDirection:
    style: str
    palette: list[str]
    elements: list[Element]


def ask_art_director(
    client: ModelClient,
    image: Image.Image,
    previous_names: list[str] | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> ArtDirection:
    image_url = to_data_url(downscale_for_models(image))
    prompt = ART_DIRECTOR_PROMPT + previous_names_hint(previous_names or [])
    raw = client.ask_for_json(prompt, [image_url], "ArtDirection", ART_DIRECTION_SCHEMA, reasoning_effort)
    return parse_art_direction(raw)


def previous_names_hint(previous_names: list[str]) -> str:
    if not previous_names:
        return ""
    return (
        "\nThis image is an edited version of a drawing whose layers were named: "
        + ", ".join(previous_names)
        + ". Give the same name to every element that is still there."
    )


def parse_art_direction(raw: dict[str, Any]) -> ArtDirection:
    parsed = [parse_element(item) for item in raw["elements"][:MAX_ELEMENTS]]
    elements = sorted(parsed, key=lambda element: element.kind != "surface")
    return ArtDirection(style=raw["style"], palette=list(raw["palette"]), elements=with_unique_names(elements))


def parse_element(item: dict[str, Any]) -> Element:
    return Element(
        name=to_layer_name(item["name"]),
        description=item["description"],
        sam_prompt=item["sam_prompt"].strip(),
        kind="surface" if item["kind"] == "surface" else "object",
        center=(clamp_fraction(item["center_x"]), clamp_fraction(item["center_y"])),
        group=bool(item.get("group", False)),
        outline="detailed" if item.get("outline") == "detailed" else "smooth",
        anchors=tuple(
            (clamp_fraction(anchor["x"]), clamp_fraction(anchor["y"])) for anchor in item.get("anchors", [])[:MAX_ANCHORS]
        ),
    )


def to_layer_name(raw_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", raw_name.lower()).strip("-") or "element"


def clamp_fraction(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def with_unique_names(elements: list[Element]) -> list[Element]:
    planned = {element.name for element in elements}
    taken: set[str] = set(RESERVED_NAMES)
    unique: list[Element] = []
    for element in elements:
        name = element.name
        count = 1
        while name in taken or (count > 1 and name in planned):
            count += 1
            name = f"{element.name}-{count}"
        taken.add(name)
        unique.append(element if name == element.name else replace(element, name=name))
    return unique
