import heapq
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Iterator

import cv2
import numpy as np
from meta_sam_parser import SegmentationMaskRecord
from PIL import Image

from app.agents.art_director import ArtDirection, Element, free_name
from app.budget import BudgetExceededError
from app.fixtures import load_mask
from app.images import downscale_for_models, to_data_url
from app.masks import bounds_center, distance_to_bounds, parse_mask_records, render_mask
from app.model_client import ModelClient

logger = logging.getLogger("drawlab.cutter")

PARALLEL_SEGMENTS = 6
SAME_INSTANCE_IOU = 0.5
MAX_SPLIT_COPIES = 12
NESTED_SHARE = 0.8


@dataclass(frozen=True)
class Cut:
    element_name: str
    prompt: str
    mask: Image.Image | None
    copies: tuple[Image.Image, ...] = ()


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
    with ThreadPoolExecutor(max_workers=PARALLEL_SEGMENTS) as pool:
        futures = {
            prompt: pool.submit(segment_with_fallback, client, image_url, prompt)
            for prompt in group_by_prompt(elements)
        }
    segmented: Segmented = {}
    for prompt, future in futures.items():
        try:
            segmented[prompt] = future.result()
        except BudgetExceededError:
            logger.warning("budget exhausted, skipping the prompt %s", prompt)
    return segmented


def group_by_prompt(elements: list[Element]) -> dict[str, list[Element]]:
    groups: dict[str, list[Element]] = {}
    for element in elements:
        groups.setdefault(prompt_key(element), []).append(element)
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
        masks = [instances[index].mask for index in owned_instances(element, singles, groups)]
        used_prompt = segmented.get(prompt_key(element), ([], element.sam_prompt))[1]
        copies = tuple(to_mask_image(mask) for mask in masks) if element.group else ()
        yield Cut(element.name, used_prompt, union_mask(masks), copies)


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
            if not mask.any():
                continue
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
    return to_mask_image(np.logical_or.reduce(masks)) if masks else None


def to_mask_image(mask: np.ndarray) -> Image.Image:
    return Image.fromarray(mask.astype(np.uint8) * 255)


def arrange_cuts(direction: ArtDirection, cuts: list[Cut]) -> tuple[ArtDirection, list[Cut]]:
    split_direction, split_cuts = split_groups(direction, cuts)
    return nest_parts(split_direction, split_cuts), split_cuts


def nest_parts(direction: ArtDirection, cuts: list[Cut]) -> ArtDirection:
    masks = {cut.element_name: np.asarray(cut.mask) > 127 for cut in cuts if cut.mask}
    elements = direction.elements
    behind: list[set[int]] = [set() for _ in elements]
    for part_index, part in enumerate(elements):
        for whole_index, whole in enumerate(elements):
            if part.name in masks and whole.name in masks and contains(masks[whole.name], masks[part.name]):
                behind[part_index].add(whole_index)
    return replace(direction, elements=[elements[index] for index in front_to_back_order(behind)])


def contains(whole: np.ndarray, part: np.ndarray) -> bool:
    part_area = np.count_nonzero(part)
    if not part_area or np.count_nonzero(whole) <= part_area:
        return False
    return np.count_nonzero(whole & part) >= NESTED_SHARE * part_area


def front_to_back_order(behind: list[set[int]]) -> list[int]:
    waiting = [len(wholes) for wholes in behind]
    ready = [index for index, count in enumerate(waiting) if count == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        index = heapq.heappop(ready)
        order.append(index)
        for part_index, wholes in enumerate(behind):
            if index in wholes:
                waiting[part_index] -= 1
                if waiting[part_index] == 0:
                    heapq.heappush(ready, part_index)
    return order


def split_groups(direction: ArtDirection, cuts: list[Cut]) -> tuple[ArtDirection, list[Cut]]:
    cut_by_name = {cut.element_name: cut for cut in cuts}
    taken = {element.name for element in direction.elements}
    elements: list[Element] = []
    split_cuts: list[Cut] = []
    for element in direction.elements:
        cut = cut_by_name.get(element.name)
        pairs = split_copies(element, cut, taken) if cut else [(element, None)]
        elements.extend(copy_element for copy_element, _ in pairs)
        split_cuts.extend(copy_cut for _, copy_cut in pairs if copy_cut)
    return replace(direction, elements=elements), split_cuts


def split_copies(element: Element, cut: Cut, taken: set[str]) -> list[tuple[Element, Cut | None]]:
    if not 2 <= len(cut.copies) <= MAX_SPLIT_COPIES:
        return [(element, cut)]
    pairs: list[tuple[Element, Cut | None]] = []
    for number, mask in enumerate(sorted(cut.copies, key=front_order), start=1):
        name = free_name(f"{element.name}-{number}", taken)
        taken.add(name)
        pairs.append((copy_element(element, name, mask), Cut(name, cut.prompt, mask)))
    return pairs


def front_order(mask: Image.Image) -> tuple[int, int]:
    left, _, _, bottom = mask.getbbox() or (0, 0, 0, 0)
    return bottom, left


def copy_element(element: Element, name: str, mask: Image.Image) -> Element:
    width, height = mask.size
    left, top, right, bottom = mask.getbbox() or (0, 0, width, height)
    x, y = inner_point(mask)
    center = ((left + right) / 2 / width, (top + bottom) / 2 / height)
    return replace(element, name=name, group=False, center=center, anchors=((x / width, y / height),))


def inner_point(mask: Image.Image) -> tuple[float, float]:
    distances = cv2.distanceTransform((np.asarray(mask) > 127).astype(np.uint8), cv2.DIST_L2, 3)
    row, column = np.unravel_index(int(distances.argmax()), distances.shape)
    return float(column) + 0.5, float(row) + 0.5


def match_cost(record: SegmentationMaskRecord, element: Element, size: tuple[int, int]) -> tuple[float, float]:
    center = element_center(element, size)
    return (distance_to_bounds(record, center), point_distance(bounds_center(record), center))


def element_center(element: Element, size: tuple[int, int]) -> tuple[float, float]:
    return (element.center[0] * size[0], element.center[1] * size[1])


def point_distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5
