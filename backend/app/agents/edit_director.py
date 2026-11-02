import logging
from dataclasses import dataclass
from typing import Any, Literal

from app.images import downscale_for_models, to_data_url
from app.model_client import ModelClient
from app.scene_repaint import render_drawing

logger = logging.getLogger("drawlab.edit_director")

EditOp = Literal["hide", "show", "move", "opacity", "forward", "backward", "front", "back"]

EDIT_OPS: tuple[EditOp, ...] = ("hide", "show", "move", "opacity", "forward", "backward", "front", "back")
MAX_OPERATIONS = 40
MAX_MOVE = 1.0

EDIT_PROMPT = """You are the art director of a vector drawing studio. A designer talks to a finished drawing.
The image shows the drawing as it looks now. Its layers, from back to front, with their main tones and their share:
{layers}
{selection}
The designer asks: "{request}"

There are two ways to answer.
1. image_prompt, for any request that changes how something looks: a color, a detail, an added, removed or replaced
   element, a defect to fix, a new mood or time of day. An image editing model will repaint this whole drawing
   from your instruction, then the studio redraws every layer as vectors.
   Write one precise English instruction: say exactly what changes and where, in terms of what is visible in the image.
   Ask to keep the exact same composition, framing, characters, poses, objects, flat illustration style,
   outlines, palette and lighting for everything else, and to keep the scene natural and coherent.
   Read the request in context: in French, "verres" can mean the lenses of glasses, not a drinking glass.
2. operations, only for requests that hide, show, move, fade or reorder existing layers without changing how they look:
   - hide, show: set layer.
   - move: set layer, dx and dy as fractions of the drawing width and height (positive moves right and down).
   - opacity: set layer and opacity, from 0 to 1.
   - forward, backward: move the layer one step toward the front or the back.
   - front, back: move the layer to the very front or the very back.
   Set every field an operation does not use to 0.
Use image_prompt or operations, not both. Leave image_prompt "" when you use operations.
When the request cannot be done, return an empty image_prompt and no operation, and say why.
reply: one short sentence, in the designer's language, saying what you are changing."""

EDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reply", "image_prompt", "operations"],
    "properties": {
        "reply": {"type": "string"},
        "image_prompt": {"type": "string"},
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["op", "layer", "dx", "dy", "opacity"],
                "properties": {
                    "op": {"type": "string", "enum": list(EDIT_OPS)},
                    "layer": {"type": "string"},
                    "dx": {"type": "number"},
                    "dy": {"type": "number"},
                    "opacity": {"type": "number"},
                },
            },
        },
    },
}


@dataclass(frozen=True)
class Tone:
    color: str
    share: float


@dataclass(frozen=True)
class LayerSummary:
    id: str
    visible: bool
    tones: list[Tone]


@dataclass(frozen=True)
class EditRequest:
    prompt: str
    svg: str
    layers: list[LayerSummary]
    selected: str | None


@dataclass(frozen=True)
class EditOperation:
    op: EditOp
    layer: str
    dx: float = 0.0
    dy: float = 0.0
    opacity: float = 1.0


@dataclass(frozen=True)
class EditPlan:
    reply: str
    image_prompt: str
    operations: list[EditOperation]


def plan_edits(client: ModelClient, request: EditRequest) -> EditPlan:
    image_url = to_data_url(downscale_for_models(render_drawing(request.svg)))
    raw = client.ask_for_json(edit_prompt(request), [image_url], "EditPlan", EDIT_SCHEMA)
    plan = parse_edit_plan(raw, request.layers)
    logger.info(
        "edit request=%r image_prompt=%r operations=%s",
        request.prompt,
        plan.image_prompt,
        [(operation.op, operation.layer) for operation in plan.operations],
    )
    return plan


def mock_plan_edits(request: EditRequest) -> EditPlan:
    target = next((layer for layer in request.layers if layer.id == request.selected), None)
    if target is None:
        return EditPlan("Mock mode: select a layer, then ask again.", "", [])
    return EditPlan(f"Mock mode: hid {target.id}.", "", [EditOperation("hide", target.id)])


def edit_prompt(request: EditRequest) -> str:
    selection = f"The selected layer is {request.selected}: \"it\" or \"this\" means that layer." if request.selected else ""
    return EDIT_PROMPT.format(
        layers="\n".join(layer_line(layer) for layer in request.layers),
        selection=selection,
        request=request.prompt.replace('"', "'"),
    )


def layer_line(layer: LayerSummary) -> str:
    tones = ", ".join(f"{tone.color} {tone.share:.0%}" for tone in layer.tones)
    hidden = " (hidden)" if not layer.visible else ""
    return f"- {layer.id}{hidden}: {tones}"


def parse_edit_plan(raw: dict[str, Any], layers: list[LayerSummary]) -> EditPlan:
    image_prompt = str(raw["image_prompt"]).strip()
    if image_prompt:
        return EditPlan(str(raw["reply"]), image_prompt, [])
    known = {layer.id for layer in layers}
    operations = [parse_operation(item, known) for item in raw["operations"][:MAX_OPERATIONS]]
    return EditPlan(str(raw["reply"]), "", [operation for operation in operations if operation])


def parse_operation(item: dict[str, Any], known: set[str]) -> EditOperation | None:
    op, layer = item["op"], str(item["layer"])
    if op not in EDIT_OPS or layer not in known:
        return None
    return EditOperation(
        op=op,
        layer=layer,
        dx=clamp(float(item["dx"]), -MAX_MOVE, MAX_MOVE),
        dy=clamp(float(item["dy"]), -MAX_MOVE, MAX_MOVE),
        opacity=clamp(float(item["opacity"]), 0.0, 1.0),
    )


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)
