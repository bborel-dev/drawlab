import logging

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import UnidentifiedImageError

from app.images import open_image
from app.tracing import trace_to_svg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Drawlab")


@app.post("/trace")
async def trace(image: UploadFile) -> Response:
    try:
        svg = trace_to_svg(open_image(await image.read()))
    except UnidentifiedImageError as error:
        raise HTTPException(status_code=400, detail="Unsupported image format") from error
    return Response(content=svg, media_type="image/svg+xml")
