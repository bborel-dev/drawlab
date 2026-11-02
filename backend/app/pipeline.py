import logging
from dataclasses import dataclass
from typing import Iterator, Literal

from openai import APIError
from PIL import Image

from app.agents.art_director import ArtDirection, ask_art_director, parse_art_direction
from app.agents.completer import Completion, Occlusion, complete_objects, find_occlusions
from app.agents.cutter import Cut, arrange_cuts, cut_elements, mock_cut_elements
from app.agents.edit_director import EditPlan, EditRequest, mock_plan_edits, plan_edits
from app.scene_repaint import RepaintRequest, repainted_scene
from app.agents.mask_reviewer import MaskFix, check_masks
from app.agents.illustrator import BACKGROUND_COLOR_LAYER, draw_layers
from app.budget import BudgetExceededError, CallBudget
from app.config import Settings
from app.fixtures import load_art_direction
from app.masks import mask_outline
from app.model_client import ModelClient
from app.tracing import downscale_for_tracing

logger = logging.getLogger("drawlab.pipeline")

AgentName = Literal["art-director", "cutter", "completer", "illustrator"]
AgentStatus = Literal["working", "done", "error"]


@dataclass(frozen=True)
class Canvas:
    width: int
    height: int


@dataclass(frozen=True)
class MaskOutline:
    name: str
    path: str
    width: int
    height: int


@dataclass(frozen=True)
class AgentEvent:
    agent: AgentName
    status: AgentStatus
    message: str
    layer: str | None = None
    canvas: Canvas | None = None
    mask: MaskOutline | None = None


def run_drawing_job(image: Image.Image, settings: Settings) -> Iterator[AgentEvent]:
    budget = CallBudget(max_calls=settings.max_api_calls_per_job)
    client = None if settings.mock_agents else ModelClient(settings, budget)
    current_agent: AgentName = "art-director"
    try:
        for event in draw(client, image):
            current_agent = event.agent
            yield event
    except BudgetExceededError as error:
        yield AgentEvent(current_agent, "error", str(error))
    except Exception:
        logger.exception("drawing job failed")
        yield AgentEvent(current_agent, "error", "Something went wrong while drawing")
    logger.info("job finished calls=%d cost=$%.4f", budget.calls, budget.cost_usd)


def run_edit_job(request: EditRequest, settings: Settings) -> EditPlan:
    if settings.mock_agents:
        return mock_plan_edits(request)
    budget = CallBudget(max_calls=settings.max_api_calls_per_job)
    try:
        return plan_edits(ModelClient(settings, budget), request)
    except (BudgetExceededError, APIError, ValueError, KeyError):
        logger.exception("edit job failed")
        return EditPlan("I could not edit the drawing this time, please try again.", "", [])
    finally:
        logger.info("edit finished calls=%d cost=$%.4f", budget.calls, budget.cost_usd)


def run_repaint_job(request: RepaintRequest, settings: Settings) -> Iterator[AgentEvent]:
    if settings.mock_agents:
        yield AgentEvent("art-director", "error", "Repainting needs the real models, set MOCK_AGENTS=false")
        return
    budget = CallBudget(max_calls=settings.max_api_calls_per_job)
    client = ModelClient(settings, budget)
    current_agent: AgentName = "art-director"
    try:
        yield AgentEvent("art-director", "working", "Muse Image is repainting the whole scene")
        edited = repainted_scene(client, request)
        names = [name for name in request.layer_names if name != BACKGROUND_COLOR_LAYER]
        for event in draw(client, edited, names):
            current_agent = event.agent
            yield event
    except BudgetExceededError as error:
        yield AgentEvent(current_agent, "error", str(error))
    except Exception:
        logger.exception("repaint job failed")
        yield AgentEvent(current_agent, "error", "Something went wrong while repainting")
    logger.info("repaint finished calls=%d cost=$%.4f", budget.calls, budget.cost_usd)


def draw(
    client: ModelClient | None, image: Image.Image, previous_names: list[str] | None = None
) -> Iterator[AgentEvent]:
    planned = yield from direct_art(client, image, previous_names)
    direction, cuts = yield from cut_objects(client, image, planned)
    completions = yield from complete_hidden(client, image, direction, cuts)
    yield from illustrate(image, direction, cuts, completions)


def direct_art(
    client: ModelClient | None, image: Image.Image, previous_names: list[str] | None
) -> Iterator[AgentEvent]:
    yield AgentEvent("art-director", "working", "Studying the image")
    if client is None:
        direction = parse_art_direction(load_art_direction())
    else:
        direction = ask_art_director(client, image, previous_names)
    names = ", ".join(element.name for element in direction.elements)
    yield AgentEvent("art-director", "done", f"Planned {len(direction.elements)} elements: {names}")
    return direction


def cut_objects(client: ModelClient | None, image: Image.Image, planned: ArtDirection) -> Iterator[AgentEvent]:
    yield AgentEvent("cutter", "working", "Segmenting each object")
    if client is None:
        checked = list(mock_cut_elements(planned))
    else:
        checked = yield from cut_and_check(client, image, planned)
    direction, cuts = arrange_cuts(planned, checked)
    for cut in cuts:
        yield AgentEvent("cutter", "working", cut_message(cut), mask=outline_of(cut))
    found = sum(1 for cut in cuts if cut.mask)
    yield AgentEvent("cutter", "done", f"Found {found} of {len(cuts)} objects")
    return direction, cuts


def cut_and_check(client: ModelClient, image: Image.Image, direction: ArtDirection) -> Iterator[AgentEvent]:
    cuts = list(cut_elements(client, image, direction))
    yield AgentEvent("cutter", "working", f"Checking {len(cuts)} masks with Muse Spark")
    check = check_masks(client, image, direction, cuts)
    if check.fixes:
        yield AgentEvent("cutter", "working", fix_message(check.fixes))
    return check.cuts


def cut_message(cut: Cut) -> str:
    return f"Found {cut.element_name}" if cut.mask else f"Could not find {cut.element_name}"


def fix_message(fixes: list[MaskFix]) -> str:
    return "Re-cut " + ", ".join(fix.element_name for fix in fixes) + " with boxes"


def outline_of(cut: Cut) -> MaskOutline | None:
    if cut.mask is None:
        return None
    path = mask_outline(cut.mask)
    width, height = cut.mask.size
    return MaskOutline(cut.element_name, path, width, height) if path else None


def complete_hidden(
    client: ModelClient | None, image: Image.Image, direction: ArtDirection, cuts: list[Cut]
) -> Iterator[AgentEvent]:
    occlusions = find_occlusions(direction, cuts) if client else []
    if client is None or not occlusions:
        yield AgentEvent("completer", "done", "No hidden object to complete")
        return []
    names = ", ".join(occlusion.name for occlusion in occlusions)
    yield AgentEvent("completer", "working", f"Muse Image is completing what hides behind other objects: {names}")
    completions: list[Completion] = []
    for occlusion, completion in complete_objects(client, image, direction, cuts, occlusions):
        if completion:
            completions.append(completion)
        yield AgentEvent("completer", "working", completion_message(occlusion, completion))
    yield AgentEvent("completer", "done", f"Completed {len(completions)} of {len(occlusions)} hidden objects")
    return completions


def completion_message(occlusion: Occlusion, completion: Completion | None) -> str:
    if completion is None:
        return f"Kept {occlusion.name} as it is"
    return f"Completed {occlusion.name} behind " + ", ".join(occlusion.occluders)


def illustrate(
    image: Image.Image, direction: ArtDirection, cuts: list[Cut], completions: list[Completion]
) -> Iterator[AgentEvent]:
    width, height = downscale_for_tracing(image).size
    yield AgentEvent("illustrator", "working", "Tracing the layers", canvas=Canvas(width, height))
    layer_count = 0
    for layer in draw_layers(image, direction, cuts, completions):
        layer_count += 1
        yield AgentEvent("illustrator", "working", f"Drew {layer.name} ({strokes(layer.path_count)})", layer=layer.svg)
    yield AgentEvent("illustrator", "done", f"Finished {layer_count} layers")


def strokes(count: int) -> str:
    return f"{count} stroke" if count == 1 else f"{count} strokes"
