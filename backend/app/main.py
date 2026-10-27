import json
import logging
from dataclasses import asdict
from typing import Iterator

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image, UnidentifiedImageError

from app.config import load_settings
from app.images import open_image
from app.pipeline import AgentEvent, run_drawing_job
from app.tracing import trace_to_svg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Drawlab")

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@app.post("/trace")
async def trace(image: UploadFile) -> Response:
    svg = trace_to_svg(await read_upload(image))
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/draw")
async def draw(image: UploadFile) -> StreamingResponse:
    events = run_drawing_job(await read_upload(image), load_settings())
    return StreamingResponse(to_server_sent_events(events), media_type="text/event-stream", headers=SSE_HEADERS)


async def read_upload(upload: UploadFile) -> Image.Image:
    try:
        return open_image(await upload.read())
    except UnidentifiedImageError as error:
        raise HTTPException(status_code=400, detail="Unsupported image format") from error


def to_server_sent_events(events: Iterator[AgentEvent]) -> Iterator[str]:
    for event in events:
        yield f"data: {json.dumps(asdict(event))}\n\n"
