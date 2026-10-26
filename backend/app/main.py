from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import UnidentifiedImageError

from app.tracing import trace_to_svg

app = FastAPI(title="Drawlab")


@app.post("/trace")
async def trace(image: UploadFile) -> Response:
    try:
        svg = trace_to_svg(await image.read())
    except UnidentifiedImageError as error:
        raise HTTPException(status_code=400, detail="Unsupported image format") from error
    return Response(content=svg, media_type="image/svg+xml")
