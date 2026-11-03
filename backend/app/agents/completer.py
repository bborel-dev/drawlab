import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterator

import cv2
import numpy as np
from openai import APIError
from PIL import Image

from app.agents.art_director import ArtDirection, Element
from app.agents.cutter import Cut
from app.budget import BudgetExceededError
from app.images import downscale_for_models, to_data_url
from app.masks import convex_hull_mask, parse_mask_records, render_mask
from app.model_client import ModelClient
from app.scene_repaint import edited_image, model_sized

logger = logging.getLogger("drawlab.completer")

MAX_COMPLETIONS = 6
PARALLEL_COMPLETIONS = 4
MAX_LISTED_OCCLUDERS = 6
CONTACT_RING = 12
MIN_OCCLUDER_CONTACT = 0.03
MIN_HIDDEN_SHARE = 0.08
MIN_HIDDEN_AREA = 0.002
MIN_CONTACT_SHARE = 0.15
MIN_VISIBLE_COVERAGE = 0.7
MAX_SPILL = 0.15
MIN_ALIGNMENT = 0.7
MAX_SHIFT = 0.03
MAX_SCALE_CHANGE = 0.05
ALIGN_ITERATIONS = 100
ALIGN_EPSILON = 1e-5
ALIGN_BLUR = 5

REVEAL_PROMPT = (
    "Remove {occluders} from this illustration. Paint what they were hiding, so that {target} is complete "
    "and fully visible, drawn in exactly the same flat style, colors and outlines. Keep everything else exactly "
    "the same: same composition, framing, positions, sizes, style and colors."
)


@dataclass(frozen=True)
class Occlusion:
    name: str
    occluders: list[str]
    hidden: int


@dataclass(frozen=True)
class Completion:
    name: str
    image: Image.Image
    shape: np.ndarray


def find_occlusions(direction: ArtDirection, cuts: list[Cut]) -> list[Occlusion]:
    masks = visible_masks(cuts)
    order = [element.name for element in direction.elements if element.name in masks]
    found: list[Occlusion] = []
    for index, name in enumerate(order):
        occlusion = occlusion_of(name, masks[name], {front: masks[front] for front in order[index + 1 :]})
        if occlusion:
            found.append(occlusion)
    return sorted(found, key=lambda occlusion: occlusion.hidden, reverse=True)[:MAX_COMPLETIONS]


def visible_masks(cuts: list[Cut]) -> dict[str, np.ndarray]:
    return {cut.element_name: np.asarray(cut.mask) > 127 for cut in cuts if cut.mask}


def occlusion_of(name: str, visible: np.ndarray, fronts: dict[str, np.ndarray]) -> Occlusion | None:
    ring = cv2.dilate(visible.astype(np.uint8), ring_kernel()).astype(bool) & ~visible
    ring_area = max(int(ring.sum()), 1)
    contacts = {front: int((ring & mask).sum()) for front, mask in fronts.items()}
    occluders = [front for front, contact in contacts.items() if contact >= MIN_OCCLUDER_CONTACT * ring_area]
    if not occluders:
        return None
    covering = np.logical_or.reduce([fronts[front] for front in occluders])
    hidden = int((convex_hull_mask(visible) & covering & ~visible).sum())
    contact_share = sum(contacts[front] for front in occluders) / ring_area
    large_hidden = hidden >= MIN_HIDDEN_SHARE * visible.sum() and hidden >= MIN_HIDDEN_AREA * visible.size
    if not large_hidden and contact_share < MIN_CONTACT_SHARE:
        return None
    return Occlusion(name, occluders, max(hidden, int(contact_share * ring_area)))


def complete_objects(
    client: ModelClient, image: Image.Image, direction: ArtDirection, cuts: list[Cut], occlusions: list[Occlusion]
) -> Iterator[tuple[Occlusion, Completion | None]]:
    work = model_sized(image)
    elements = {element.name: element for element in direction.elements}
    masks = visible_masks(cuts)
    with ThreadPoolExecutor(max_workers=PARALLEL_COMPLETIONS) as pool:
        futures = {
            pool.submit(complete_object, client, work, elements, masks, occlusion): occlusion
            for occlusion in occlusions
        }
        for future in as_completed(futures):
            yield futures[future], future.result()


def complete_object(
    client: ModelClient,
    work: Image.Image,
    elements: dict[str, Element],
    masks: dict[str, np.ndarray],
    occlusion: Occlusion,
) -> Completion | None:
    try:
        revealed = edited_image(client, work, reveal_prompt(elements, occlusion))
        hidden_zone = occluder_zone(masks, occlusion.occluders)
        aligned = align_to(work, revealed, hidden_zone)
        if aligned is None:
            logger.info("completion of %s rejected: the repaint moved the scene", occlusion.name)
            return None
        shape = revealed_shape(client, aligned, elements[occlusion.name], masks[occlusion.name], hidden_zone)
        if shape is None:
            logger.info("completion of %s rejected: no matching shape in the repaint", occlusion.name)
            return None
        return Completion(occlusion.name, aligned, shape)
    except (BudgetExceededError, APIError, ValueError):
        logger.exception("completion of %s failed", occlusion.name)
        return None


def reveal_prompt(elements: dict[str, Element], occlusion: Occlusion) -> str:
    occluders = "; ".join(described(elements[name]) for name in occlusion.occluders[:MAX_LISTED_OCCLUDERS])
    return REVEAL_PROMPT.format(occluders=occluders, target=described(elements[occlusion.name]))


def described(element: Element) -> str:
    return f"the {element.name.replace('-', ' ')} ({element.description.rstrip('.')})"


def occluder_zone(masks: dict[str, np.ndarray], occluders: list[str]) -> np.ndarray:
    covering = np.logical_or.reduce([masks[name] for name in occluders])
    return cv2.dilate(covering.astype(np.uint8), ring_kernel()).astype(bool)


def align_to(original: Image.Image, revealed: Image.Image, hidden_zone: np.ndarray) -> Image.Image | None:
    template = grayscale(original)
    moving = grayscale(revealed)
    unchanged = cv2.resize((~hidden_zone).astype(np.uint8), original.size, interpolation=cv2.INTER_NEAREST)
    warp = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, ALIGN_ITERATIONS, ALIGN_EPSILON)
    try:
        correlation, warp = cv2.findTransformECC(template, moving, warp, cv2.MOTION_AFFINE, criteria, unchanged, ALIGN_BLUR)
    except cv2.error:
        return None
    if correlation < MIN_ALIGNMENT or not is_small_warp(warp, original.size):
        return None
    pixels = cv2.warpAffine(
        np.asarray(revealed), warp, original.size, flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return Image.fromarray(pixels)


def grayscale(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("L"), dtype=np.float32) / 255


def is_small_warp(warp: np.ndarray, size: tuple[int, int]) -> bool:
    shift = np.abs(warp[:, 2]) / np.array(size)
    scale = np.abs(warp[:, :2] - np.eye(2))
    return bool(shift.max() <= MAX_SHIFT and scale.max() <= MAX_SCALE_CHANGE)


def revealed_shape(
    client: ModelClient, revealed: Image.Image, element: Element, visible: np.ndarray, hidden_zone: np.ndarray
) -> np.ndarray | None:
    model_image = downscale_for_models(revealed)
    records = parse_mask_records(client.segment(to_data_url(model_image), element.sam_prompt))
    size = (visible.shape[1], visible.shape[0])
    candidates = [np.asarray(render_mask(record, size)) > 0 for record in records]
    fitting = [shape for shape in candidates if fits_visible(shape, visible, hidden_zone)]
    if not fitting:
        return None
    best = max(fitting, key=lambda shape: int((shape & visible).sum()))
    return best | visible


def fits_visible(shape: np.ndarray, visible: np.ndarray, hidden_zone: np.ndarray) -> bool:
    area = int(shape.sum())
    if not area:
        return False
    coverage = (shape & visible).sum() / max(int(visible.sum()), 1)
    spill = (shape & ~visible & ~hidden_zone).sum() / area
    grows = bool((shape & hidden_zone & ~visible).any())
    return coverage >= MIN_VISIBLE_COVERAGE and spill <= MAX_SPILL and grows


def ring_kernel() -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * CONTACT_RING + 1, 2 * CONTACT_RING + 1))
