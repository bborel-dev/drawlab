import logging
from dataclasses import dataclass
from typing import Iterator

from meta_sam_parser import SegmentationMaskRecord
from PIL import Image

from app.agents.art_director import ArtDirection, Element
from app.budget import BudgetExceededError
from app.fixtures import load_mask
from app.images import downscale_for_models, to_data_url
from app.masks import bounds_center, distance_to_bounds, parse_mask_records, render_mask
from app.model_client import ModelClient

logger = logging.getLogger("drawlab.cutter")


@dataclass(frozen=True)
class Cut:
    element_name: str
    prompt: str
    mask: Image.Image | None


def cut_elements(client: ModelClient, image: Image.Image, direction: ArtDirection) -> Iterator[Cut]:
    model_image = downscale_for_models(image)
    image_url = to_data_url(model_image)
    try:
        for prompt, elements in group_by_prompt(object_elements(direction)).items():
            records, used_prompt = segment_with_fallback(client, image_url, prompt)
            yield from assign_instances(elements, records, model_image.size, used_prompt)
    except BudgetExceededError:
        logger.warning("budget exhausted, keeping the masks cut so far")


def mock_cut_elements(direction: ArtDirection) -> Iterator[Cut]:
    for element in object_elements(direction):
        yield Cut(element.name, element.sam_prompt, load_mask(element.name))


def object_elements(direction: ArtDirection) -> list[Element]:
    return [element for element in direction.elements if element.kind == "object"]


def group_by_prompt(elements: list[Element]) -> dict[str, list[Element]]:
    groups: dict[str, list[Element]] = {}
    for element in elements:
        groups.setdefault(element.sam_prompt.lower(), []).append(element)
    return groups


def segment_with_fallback(
    client: ModelClient, image_url: str, prompt: str
) -> tuple[list[SegmentationMaskRecord], str]:
    records = parse_mask_records(client.segment(image_url, prompt))
    fallback = fallback_prompt(prompt)
    if records or fallback is None:
        return records, prompt
    return parse_mask_records(client.segment(image_url, fallback)), fallback


def fallback_prompt(prompt: str) -> str | None:
    words = prompt.split()
    return words[-1] if len(words) > 1 else None


def assign_instances(
    elements: list[Element], records: list[SegmentationMaskRecord], size: tuple[int, int], prompt: str
) -> Iterator[Cut]:
    assignment = match_records_to_elements(elements, records, size)
    for element in elements:
        record = assignment.get(element.name)
        yield Cut(element.name, prompt, render_mask(record, size) if record else None)


def match_records_to_elements(
    elements: list[Element], records: list[SegmentationMaskRecord], size: tuple[int, int]
) -> dict[str, SegmentationMaskRecord]:
    candidates = sorted(
        (match_cost(record, element, size), element_index, record_index)
        for element_index, element in enumerate(elements)
        for record_index, record in enumerate(records)
    )
    assignment: dict[str, SegmentationMaskRecord] = {}
    used_records: set[int] = set()
    for _, element_index, record_index in candidates:
        element = elements[element_index]
        if element.name in assignment or record_index in used_records:
            continue
        assignment[element.name] = records[record_index]
        used_records.add(record_index)
    return assignment


def match_cost(record: SegmentationMaskRecord, element: Element, size: tuple[int, int]) -> tuple[float, float]:
    center = (element.center[0] * size[0], element.center[1] * size[1])
    record_center = bounds_center(record)
    center_distance = ((record_center[0] - center[0]) ** 2 + (record_center[1] - center[1]) ** 2) ** 0.5
    return (distance_to_bounds(record, center), center_distance)
