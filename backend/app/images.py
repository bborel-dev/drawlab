import base64
import io

from PIL import Image, ImageOps

MAX_MODEL_IMAGE_SIDE = 1024
PAPER_COLOR = (255, 255, 255, 255)


def open_image(data: bytes) -> Image.Image:
    return on_paper(ImageOps.exif_transpose(Image.open(io.BytesIO(data))))


def on_paper(image: Image.Image) -> Image.Image:
    if not has_transparency(image):
        return image.convert("RGB")
    paper = Image.new("RGBA", image.size, PAPER_COLOR)
    return Image.alpha_composite(paper, image.convert("RGBA")).convert("RGB")


def has_transparency(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info


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
