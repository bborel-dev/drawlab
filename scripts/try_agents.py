import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from PIL import Image, ImageChops, ImageDraw

from app.agents.art_director import ArtDirection, ask_art_director, parse_art_direction
from app.agents.cutter import Cut, cut_elements, mock_cut_elements
from app.budget import CallBudget
from app.config import load_settings
from app.fixtures import load_art_direction
from app.images import downscale_for_models, open_image
from app.model_client import ModelClient

OUTPUT_DIR = Path("output/agents")
TILE_SIZE = (384, 256)
COLUMNS = 4


def run_agents(image: Image.Image) -> tuple[ArtDirection, list[Cut], CallBudget]:
    settings = load_settings()
    budget = CallBudget(max_calls=settings.max_api_calls_per_job)
    if settings.mock_agents:
        direction = parse_art_direction(load_art_direction())
        return direction, list(mock_cut_elements(direction)), budget
    client = ModelClient(settings, budget)
    direction = ask_art_director(client, image)
    return direction, list(cut_elements(client, image, direction)), budget


def build_contact_sheet(model_image: Image.Image, cuts: list[Cut]) -> Image.Image:
    rows = (len(cuts) + COLUMNS) // COLUMNS
    sheet = Image.new("RGB", (TILE_SIZE[0] * COLUMNS, (TILE_SIZE[1] + 20) * rows), "white")
    draw = ImageDraw.Draw(sheet)
    dimmed = model_image.point(lambda value: value // 3)
    tiles = [("source", model_image)] + [(cut_label(cut), highlight(dimmed, cut.mask)) for cut in cuts]
    for index, (label, tile) in enumerate(tiles):
        x, y = (index % COLUMNS) * TILE_SIZE[0], (index // COLUMNS) * (TILE_SIZE[1] + 20)
        sheet.paste(tile.resize(TILE_SIZE), (x, y + 20))
        draw.text((x + 4, y + 4), label, fill="black")
    return sheet


def cut_label(cut: Cut) -> str:
    status = "" if cut.mask else " (no match)"
    return f"{cut.element_name} [{cut.prompt}]{status}"


def highlight(dimmed: Image.Image, mask: Image.Image | None) -> Image.Image:
    if mask is None:
        return Image.new("RGB", dimmed.size, "black")
    return Image.composite(Image.new("RGB", dimmed.size, (255, 0, 120)), dimmed, mask)


def coverage(cuts: list[Cut], size: tuple[int, int]) -> float:
    union = Image.new("L", size, 0)
    for cut in cuts:
        if cut.mask:
            union = ImageChops.lighter(union, cut.mask)
    return sum(union.histogram()[1:]) / (size[0] * size[1])


def main(image_path: Path) -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    image = open_image(image_path.read_bytes())
    direction, cuts, budget = run_agents(image)
    model_image = downscale_for_models(image)
    output_dir = OUTPUT_DIR / image_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "art-direction.json").write_text(json.dumps(asdict(direction), indent=2), encoding="utf-8")
    build_contact_sheet(model_image, cuts).save(output_dir / "contact-sheet.png")
    found = sum(1 for cut in cuts if cut.mask)
    print(f"[done] objects={len(cuts)} found={found} object_coverage={coverage(cuts, model_image.size):.1%}")
    print(f"[done] calls={budget.calls} cost=${budget.cost_usd:.4f} outputs={output_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/try_agents.py <image-path>")
    main(Path(sys.argv[1]))
