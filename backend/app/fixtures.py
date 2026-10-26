import json
from pathlib import Path
from typing import Any

from PIL import Image

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "flat-landscape"


def load_art_direction() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "art-direction.json").read_text(encoding="utf-8"))


def load_mask(element_name: str) -> Image.Image | None:
    path = FIXTURE_DIR / "masks" / f"{element_name}.png"
    return Image.open(path).convert("L") if path.exists() else None
