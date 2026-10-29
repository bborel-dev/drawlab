import logging
from dataclasses import dataclass, replace
from typing import Any, Literal

import numpy as np
from meta_sam_parser import FramePrompt, PromptBox, PromptObject, build_object_prompt
from PIL import Image, ImageDraw, ImageFont

from app.agents.art_director import ArtDirection, Element
from app.agents.cutter import Cut
from app.budget import BudgetExceededError
from app.images import downscale_for_models, to_data_url
from app.masks import parse_mask_records, render_mask
from app.model_client import ModelClient

Verdict = Literal["ok", "wrong", "missing"]

logger = logging.getLogger("drawlab.mask_reviewer")

GRID = 1000
MAX_BOXES_PER_CALL = 16
MIN_BOX_SIDE = 2
MAX_BOX_SHARE = 0.4
OVERLAY_OPACITY = 0.55
LABEL_SIZE_RATIO = 0.035
OVERLAY_COLORS = [
    (59, 130, 246),
    (236, 72, 153),
    (168, 85, 247),
    (6, 182, 212),
    (251, 146, 60),
    (34, 197, 94),
    (234, 179, 8),
    (239, 68, 68),
]

REVIEWER_PROMPT = """You check the work of a segmentation model for a vector drawing studio.
The first image is the original. The second image shows every mask the model found, filled with a color
and marked with the element number. Elements:
{elements}
For every element, give a verdict:
- "ok" when its colored mask covers that element and little else,
- "wrong" when its mask covers something else, or misses a large part of the element,
- "missing" when it has no mask.
For "wrong" and "missing" elements, give a tight box around the real element in the first image,
as x_min, y_min, x_max, y_max on a 0 to 1000 grid. For "ok" elements, give the box of their mask."""

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reviews"],
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["number", "verdict", "x_min", "y_min", "x_max", "y_max"],
                "properties": {
                    "number": {"type": "integer"},
                    "verdict": {"type": "string", "enum": ["ok", "wrong", "missing"]},
                    "x_min": {"type": "number"},
                    "y_min": {"type": "number"},
                    "x_max": {"type": "number"},
                    "y_max": {"type": "number"},
                },
            },
        }
    },
}


@dataclass(frozen=True)
class MaskFix:
    element_name: str
    verdict: Verdict
    box: PromptBox


@dataclass(frozen=True)
class MaskCheck:
    cuts: list[Cut]
    fixes: list[MaskFix]


def check_masks(client: ModelClient, image: Image.Image, direction: ArtDirection, cuts: list[Cut]) -> MaskCheck:
    try:
        fixes = review_cuts(client, image, direction, cuts)
        return MaskCheck(repair_cuts(client, image, cuts, fixes), fixes)
    except BudgetExceededError:
        logger.warning("budget exhausted, keeping the masks as cut")
        return MaskCheck(cuts, [])


def review_cuts(client: ModelClient, image: Image.Image, direction: ArtDirection, cuts: list[Cut]) -> list[MaskFix]:
    model_image = downscale_for_models(image)
    elements = [element for element in direction.elements if element.kind == "object"]
    prompt = REVIEWER_PROMPT.format(elements=element_list(elements, cuts))
    overlay = draw_overlay(model_image, elements, cuts)
    raw = client.ask_for_json(prompt, [to_data_url(model_image), to_data_url(overlay)], "MaskReview", REVIEW_SCHEMA)
    return parse_fixes(raw, elements, model_image.size)


def repair_cuts(client: ModelClient, image: Image.Image, cuts: list[Cut], fixes: list[MaskFix]) -> list[Cut]:
    model_image = downscale_for_models(image)
    repaired = {cut.element_name: cut for cut in cuts}
    batch = fixes[:MAX_BOXES_PER_CALL]
    if not batch:
        return cuts
    objects = [PromptObject(id=index + 1, prompts=[FramePrompt(frame=0, box=fix.box)]) for index, fix in enumerate(batch)]
    prompt = build_object_prompt(size=model_image.size, objects=objects)
    records = parse_mask_records(client.segment(to_data_url(model_image), prompt))
    for record in records:
        fix = batch[int(record.object_id) - 1] if record.object_id.isdigit() else None
        if fix and fix.element_name in repaired:
            repaired[fix.element_name] = replace(
                repaired[fix.element_name], prompt="box", mask=render_mask(record, model_image.size)
            )
    return [repaired[cut.element_name] for cut in cuts]


def element_list(elements: list[Element], cuts: list[Cut]) -> str:
    found = {cut.element_name for cut in cuts if cut.mask}
    lines = [
        f"{number}. {element.name}: {element.description} ({'has a mask' if element.name in found else 'no mask'})"
        for number, element in enumerate(elements, start=1)
    ]
    return "\n".join(lines)


def draw_overlay(image: Image.Image, elements: list[Element], cuts: list[Cut]) -> Image.Image:
    masks = {cut.element_name: cut.mask for cut in cuts if cut.mask}
    overlay = np.asarray(image.convert("RGB")).astype(np.float32) * 0.6
    labels: list[tuple[int, tuple[int, int], tuple[int, int, int]]] = []
    for number, element in enumerate(elements, start=1):
        mask = masks.get(element.name)
        if mask is None:
            continue
        color = OVERLAY_COLORS[(number - 1) % len(OVERLAY_COLORS)]
        inside = np.asarray(mask.resize(image.size)) > 127
        overlay[inside] = overlay[inside] * (1 - OVERLAY_OPACITY) + np.array(color) * OVERLAY_OPACITY
        rows, columns = np.nonzero(inside)
        labels.append((number, (int(columns.mean()), int(rows.mean())), color))
    result = Image.fromarray(overlay.clip(0, 255).astype(np.uint8))
    draw_labels(result, labels)
    return result


def draw_labels(image: Image.Image, labels: list[tuple[int, tuple[int, int], tuple[int, int, int]]]) -> None:
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(12, round(max(image.size) * LABEL_SIZE_RATIO)))
    for number, (x, y), color in labels:
        left, top, right, bottom = draw.textbbox((x, y), str(number), font=font, anchor="mm")
        draw.rectangle((left - 4, top - 3, right + 4, bottom + 3), fill=(255, 255, 255), outline=color, width=2)
        draw.text((x, y), str(number), fill=(0, 0, 0), font=font, anchor="mm")


def parse_fixes(raw: dict[str, Any], elements: list[Element], size: tuple[int, int]) -> list[MaskFix]:
    fixes: list[MaskFix] = []
    for review in raw["reviews"]:
        number = int(review["number"])
        if not 1 <= number <= len(elements) or not needs_fix(elements[number - 1], review["verdict"]):
            continue
        box = grid_box(review, size)
        if box:
            fixes.append(MaskFix(elements[number - 1].name, review["verdict"], box))
    return fixes


def needs_fix(element: Element, verdict: str) -> bool:
    return verdict == "missing" or (verdict == "wrong" and not element.group)


def grid_box(review: dict[str, Any], size: tuple[int, int]) -> PromptBox | None:
    width, height = size
    left = clamp(review["x_min"] / GRID * width, width)
    right = clamp(review["x_max"] / GRID * width, width)
    top = clamp(review["y_min"] / GRID * height, height)
    bottom = clamp(review["y_max"] / GRID * height, height)
    too_small = right - left < MIN_BOX_SIDE or bottom - top < MIN_BOX_SIDE
    too_vague = (right - left) * (bottom - top) > MAX_BOX_SHARE * width * height
    if too_small or too_vague:
        return None
    return PromptBox(left, top, right, bottom)


def clamp(value: float, limit: int) -> int:
    return int(min(max(round(value), 0), limit))
