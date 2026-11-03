import json
import logging
from dataclasses import asdict
from typing import Iterator

from fastapi import APIRouter, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from app.agents.edit_director import EditRequest
from app.config import Settings, load_settings
from app.guardrails import (
    DRAWING_SLOT,
    admit_conversion,
    admit_edit,
    admit_proposal,
    admit_repaint,
    holding_slot,
    visitor_quota,
)
from app.images import open_image
from app.pipeline import AgentEvent, ProposalError, run_drawing_job, run_edit_job, run_proposal_job, run_repaint_job
from app.scene_repaint import ProposalRequest, RedrawRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Drawlab")
router = APIRouter(prefix="/api")

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
MAX_PROMPT_CHARS = 500
MAX_SVG_CHARS = 8_000_000
MAX_EDIT_LAYERS = 200
MAX_IMAGE_PROMPT_CHARS = 2000
MAX_IMAGE_DATA_CHARS = 20_000_000
MAX_CANVAS_SIDE = 8192


@router.get("/quota")
def quota(request: Request) -> dict[str, object]:
    return asdict(visitor_quota(request, load_settings()))


@router.post("/draw")
async def draw(request: Request, image: UploadFile) -> StreamingResponse:
    settings = load_settings()
    token = admit_conversion(request, settings)
    try:
        picture = await read_upload(image)
    except HTTPException:
        DRAWING_SLOT.release(token)
        raise
    return event_stream(holding_slot(token, run_drawing_job(picture, settings)))


@router.post("/edit")
def edit(request: Request, body: EditRequest) -> dict[str, object]:
    check_edit_request(body)
    settings = load_settings()
    admit_edit(request, settings)
    return asdict(run_edit_job(body, settings))


@router.post("/repaint/proposal")
def repaint_proposal(request: Request, body: ProposalRequest) -> dict[str, str]:
    check_proposal_request(body)
    settings = load_settings()
    admit_proposal(request, settings)
    try:
        return {"image": run_proposal_job(body, settings)}
    except ProposalError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/repaint")
def repaint(request: Request, body: RedrawRequest) -> StreamingResponse:
    check_redraw_request(body)
    settings = load_settings()
    token = admit_repaint(request, settings)
    return event_stream(holding_slot(token, run_repaint_job(body, settings)))


def configure(settings: Settings) -> None:
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )
    app.include_router(router)
    if settings.frontend_dir:
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="site")


configure(load_settings())


def check_proposal_request(request: ProposalRequest) -> None:
    if not request.image_prompt.strip() or len(request.image_prompt) > MAX_IMAGE_PROMPT_CHARS:
        raise HTTPException(status_code=400, detail=f"The instruction must be 1 to {MAX_IMAGE_PROMPT_CHARS} characters")
    if bool(request.svg) == bool(request.image):
        raise HTTPException(status_code=400, detail="Send either the drawing or the proposed image")
    if len(request.svg) > MAX_SVG_CHARS or len(request.image) > MAX_IMAGE_DATA_CHARS:
        raise HTTPException(status_code=413, detail="The drawing is too large to repaint")


def check_redraw_request(request: RedrawRequest) -> None:
    if len(request.image) > MAX_IMAGE_DATA_CHARS or len(request.layer_names) > MAX_EDIT_LAYERS:
        raise HTTPException(status_code=413, detail="The drawing is too large to redraw")
    if not (0 < request.width <= MAX_CANVAS_SIDE and 0 < request.height <= MAX_CANVAS_SIDE):
        raise HTTPException(status_code=400, detail=f"The canvas must be at most {MAX_CANVAS_SIDE} pixels wide")


def check_edit_request(request: EditRequest) -> None:
    if not request.prompt.strip() or len(request.prompt) > MAX_PROMPT_CHARS:
        raise HTTPException(status_code=400, detail=f"The request must be 1 to {MAX_PROMPT_CHARS} characters")
    if len(request.svg) > MAX_SVG_CHARS or len(request.layers) > MAX_EDIT_LAYERS:
        raise HTTPException(status_code=413, detail="The drawing is too large to edit")


async def read_upload(upload: UploadFile) -> Image.Image:
    try:
        return open_image(await upload.read())
    except UnidentifiedImageError as error:
        raise HTTPException(status_code=400, detail="Unsupported image format") from error


def event_stream(events: Iterator[AgentEvent]) -> StreamingResponse:
    return StreamingResponse(to_server_sent_events(events), media_type="text/event-stream", headers=SSE_HEADERS)


def to_server_sent_events(events: Iterator[AgentEvent]) -> Iterator[str]:
    for event in events:
        yield f"data: {json.dumps(asdict(event))}\n\n"
