import json
import logging
from dataclasses import asdict
from typing import Iterator

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image, UnidentifiedImageError

from app.agents.edit_director import EditRequest
from app.config import load_settings
from app.images import open_image
from app.pipeline import AgentEvent, run_drawing_job, run_edit_job, run_repaint_job
from app.scene_repaint import RepaintRequest
from app.tracing import trace_to_svg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Drawlab")

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
MAX_PROMPT_CHARS = 500
MAX_SVG_CHARS = 8_000_000
MAX_EDIT_LAYERS = 200
MAX_IMAGE_PROMPT_CHARS = 2000


@app.post("/trace")
async def trace(image: UploadFile) -> Response:
    svg = trace_to_svg(await read_upload(image))
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/draw")
async def draw(image: UploadFile) -> StreamingResponse:
    events = run_drawing_job(await read_upload(image), load_settings())
    return StreamingResponse(to_server_sent_events(events), media_type="text/event-stream", headers=SSE_HEADERS)


@app.post("/edit")
def edit(request: EditRequest) -> dict[str, object]:
    check_edit_request(request)
    return asdict(run_edit_job(request, load_settings()))


@app.post("/repaint")
def repaint(request: RepaintRequest) -> StreamingResponse:
    check_repaint_request(request)
    events = run_repaint_job(request, load_settings())
    return StreamingResponse(to_server_sent_events(events), media_type="text/event-stream", headers=SSE_HEADERS)


def check_repaint_request(request: RepaintRequest) -> None:
    if not request.image_prompt.strip() or len(request.image_prompt) > MAX_IMAGE_PROMPT_CHARS:
        raise HTTPException(status_code=400, detail=f"The instruction must be 1 to {MAX_IMAGE_PROMPT_CHARS} characters")
    if len(request.svg) > MAX_SVG_CHARS or len(request.layer_names) > MAX_EDIT_LAYERS:
        raise HTTPException(status_code=413, detail="The drawing is too large to repaint")


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


def to_server_sent_events(events: Iterator[AgentEvent]) -> Iterator[str]:
    for event in events:
        yield f"data: {json.dumps(asdict(event))}\n\n"
