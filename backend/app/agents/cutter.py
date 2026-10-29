import logging
from dataclasses import dataclass
from typing import Iterator

import numpy as np
from meta_sam_parser import SegmentationMaskRecord
from PIL import Image

from app.agents.art_director import ArtDirection, Element
from app.budget import BudgetExceededError
from app.fixtures import load_mask
from app.images import downscale_for_models, to_data_url
from app.masks import bounds_center, distance_to_bounds, parse_mask_records, render_mask
from app.model_client import ModelClient

logger = logging.getLogger("drawlab.cutter")

SAME_INSTANCE_IOU = 0.5


@dataclass(frozen=True)
class Cut:
    element_name: str
    prompt: str
    mask: Image.Image | None


@dataclass(frozen=True)
class Instance:
    record: SegmentationMaskRecord
    mask: np.ndarray
    prompts: set[str]


Segmented = dict[str, tuple[list[SegmentationMaskRecord], str]]


def cut_elements(client: ModelClient, image: Image.Image, direction: ArtDirection) -> Iterator[Cut]:
    model_image = downscale_for_models(image)
    elements = object_elements(direction)
    segmented = segment_prompts(client, to_data_url(model_image), elements)
    yield from assign_cuts(elements, segmented, model_image.size)


def mock_cut_elements(direction: ArtDirection) -> Iterator[Cut]:
    for element in object_elements(direction):
        yield Cut(element.name, element.sam_prompt, load_mask(element.name))


def object_elements(direction: ArtDirection) -> list[Element]:
    return [element for element in direction.elements if element.kind == "object"]


def segment_prompts(client: ModelClient, image_url: str, elements: list[Element]) -> Segmented:
    segmented: Segmented = {}
    try:
        for prompt in group_by_prompt(elements):
            segmented[prompt] = segment_with_fallback(client, image_url, prompt)
    except BudgetExceededError:
        logger.warning("budget exhausted, keeping the masks cut so far")
    return segmented


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


def assign_cuts(elements: list[Element], segmented: Segmented, size: tuple[int, int]) -> Iterator[Cut]:
    instances = merge_instances(segmented, size)
    singles = match_singles([element for element in elements if not element.group], instances, size)
    group_elements = [element for element in elements if element.group]
    groups = split_among_groups(group_elements, instances, set(singles.values()), size)
    for element in elements:
        owned = owned_instances(element, singles, groups)
        used_prompt = segmented.get(prompt_key(element), ([], element.sam_prompt))[1]
        yield Cut(element.name, used_prompt, union_mask([instances[index].mask for index in owned]))


def owned_instances(element: Element, singles: dict[str, int], groups: dict[str, list[int]]) -> list[int]:
    if element.group:
        return groups.get(element.name, [])
    return [singles[element.name]] if element.name in singles else []


def prompt_key(element: Element) -> str:
    return element.sam_prompt.lower()


def merge_instances(segmented: Segmented, size: tuple[int, int]) -> list[Instance]:
    instances: list[Instance] = []
    for prompt, (records, _) in segmented.items():
        for record in records:
            mask = np.asarray(render_mask(record, size)) > 0
            same = next((instance for instance in instances if iou(instance.mask, mask) > SAME_INSTANCE_IOU), None)
            if same:
                same.prompts.add(prompt)
            else:
                instances.append(Instance(record, mask, {prompt}))
    return instances


def iou(first: np.ndarray, second: np.ndarray) -> float:
    union = np.count_nonzero(first | second)
    return np.count_nonzero(first & second) / union if union else 0.0


def match_singles(elements: list[Element], instances: list[Instance], size: tuple[int, int]) -> dict[str, int]:
    candidates = sorted(
        (match_cost(instance.record, element, size), element_index, instance_index)
        for element_index, element in enumerate(elements)
        for instance_index, instance in enumerate(instances)
        if prompt_key(element) in instance.prompts
    )
    assignment: dict[str, int] = {}
    for _, element_index, instance_index in candidates:
        name = elements[element_index].name
        if name not in assignment and instance_index not in assignment.values():
            assignment[name] = instance_index
    return assignment


def split_among_groups(
    groups: list[Element], instances: list[Instance], claimed: set[int], size: tuple[int, int]
) -> dict[str, list[int]]:
    split: dict[str, list[int]] = {group.name: [] for group in groups}
    for index, instance in enumerate(instances):
        candidates = [group for group in groups if prompt_key(group) in instance.prompts]
        if index in claimed or not candidates:
            continue
        center = bounds_center(instance.record)
        nearest = min(candidates, key=lambda group: point_distance(center, element_center(group, size)))
        split[nearest.name].append(index)
    return split


def union_mask(masks: list[np.ndarray]) -> Image.Image | None:
    if not masks:
        return None
    return Image.fromarray(np.logical_or.reduce(masks).astype(np.uint8) * 255)


def match_cost(record: SegmentationMaskRecord, element: Element, size: tuple[int, int]) -> tuple[float, float]:
    center = element_center(element, size)
    return (distance_to_bounds(record, center), point_distance(bounds_center(record), center))


def element_center(element: Element, size: tuple[int, int]) -> tuple[float, float]:
    return (element.center[0] * size[0], element.center[1] * size[1])


def point_distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5
