import base64
import io

from PIL import Image

MAX_MODEL_IMAGE_SIDE = 1024


def open_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def downscale_for_models(image: Image.Image) -> Image.Image:
    model_image = image.copy()
    model_image.thumbnail((MAX_MODEL_IMAGE_SIDE, MAX_MODEL_IMAGE_SIDE))
    return model_image


def to_png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def to_data_url(image: Image.Image) -> str:
    return "data:image/png;base64," + base64.b64encode(to_png_bytes(image)).decode("ascii")
