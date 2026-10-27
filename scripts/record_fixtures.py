import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.agents.art_director import ArtDirection, ask_art_director
from app.agents.cutter import cut_elements
from app.budget import CallBudget
from app.config import load_settings
from app.fixtures import FIXTURE_DIR
from app.images import open_image
from app.model_client import ModelClient


def raw_art_direction(direction: ArtDirection) -> dict[str, Any]:
    elements = [
        {
            "name": element.name,
            "description": element.description,
            "sam_prompt": element.sam_prompt,
            "kind": element.kind,
            "center_x": element.center[0],
            "center_y": element.center[1],
        }
        for element in direction.elements
    ]
    return {"style": direction.style, "palette": direction.palette, "elements": elements}


def main(image_path: Path) -> None:
    settings = load_settings()
    if settings.mock_agents:
        sys.exit("set MOCK_AGENTS=false to record fixtures from the real models")
    budget = CallBudget(max_calls=settings.max_api_calls_per_job)
    client = ModelClient(settings, budget)
    image = open_image(image_path.read_bytes())
    direction = ask_art_director(client, image)
    cuts = list(cut_elements(client, image, direction))
    masks_dir = FIXTURE_DIR / "masks"
    shutil.rmtree(masks_dir, ignore_errors=True)
    masks_dir.mkdir(parents=True)
    (FIXTURE_DIR / "art-direction.json").write_text(json.dumps(raw_art_direction(direction), indent=2), encoding="utf-8")
    for cut in cuts:
        if cut.mask:
            cut.mask.save(masks_dir / f"{cut.element_name}.png")
    missing = [cut.element_name for cut in cuts if cut.mask is None]
    print(f"[fixtures] elements={len(direction.elements)} masks={len(cuts) - len(missing)} missing={missing}")
    print(f"[done] calls={budget.calls} cost=${budget.cost_usd:.4f} outputs={FIXTURE_DIR}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/record_fixtures.py <image-path>")
    main(Path(sys.argv[1]))
