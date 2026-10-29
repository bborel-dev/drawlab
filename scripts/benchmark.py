import io
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import cv2
import numpy as np
import resvg_py
from PIL import Image

from app.agents.art_director import ArtDirection, Element
from app.agents.illustrator import assemble_svg, draw_layers
from app.images import open_image
from app.tracing import downscale_for_tracing

SAMPLES_DIR = Path("samples")
OUTPUT_DIR = Path("output/benchmark")
RESULTS_FILE = OUTPUT_DIR / "results.json"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
VISIBLE_DELTA_E = 5.0
HEATMAP_MAX_DELTA_E = 30.0


@dataclass(frozen=True)
class Score:
    mean_delta_e: float
    visible_share: float
    p99_delta_e: float
    size_kb: int
    seconds: float


def geometry_only_direction() -> ArtDirection:
    background = Element("background", "", "", "surface", (0.5, 0.5))
    return ArtDirection(style="", palette=[], elements=[background])


def render(svg: str) -> np.ndarray:
    png = resvg_py.svg_to_bytes(svg_string=svg, background="#ffffff")
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))


def delta_e(reference: np.ndarray, rendered: np.ndarray) -> np.ndarray:
    lab_reference = cv2.cvtColor(reference.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
    lab_rendered = cv2.cvtColor(rendered.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
    return np.linalg.norm(lab_reference - lab_rendered, axis=2)


def heatmap(reference: np.ndarray, distance: np.ndarray) -> Image.Image:
    heat = np.clip(distance / HEATMAP_MAX_DELTA_E * 255, 0, 255).astype(np.uint8)
    colored = cv2.cvtColor(cv2.applyColorMap(heat, cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB)
    gray = np.repeat(cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY)[..., None], 3, axis=2)
    weight = np.clip(distance / VISIBLE_DELTA_E, 0, 1)[..., None]
    return Image.fromarray((gray * 0.35 * (1 - weight) + colored * weight).astype(np.uint8))


def score_image(image_path: Path) -> Score:
    image = open_image(image_path.read_bytes())
    started = time.perf_counter()
    trace_image = downscale_for_tracing(image)
    svg = assemble_svg(trace_image.size, list(draw_layers(image, geometry_only_direction(), [])))
    seconds = time.perf_counter() - started
    reference = np.asarray(trace_image)
    rendered = render(svg)
    distance = delta_e(reference, rendered)
    save_outputs(image_path.stem, svg, rendered, heatmap(reference, distance))
    return Score(
        mean_delta_e=round(float(distance.mean()), 3),
        visible_share=round(float((distance > VISIBLE_DELTA_E).mean()), 4),
        p99_delta_e=round(float(np.percentile(distance, 99)), 2),
        size_kb=len(svg) // 1024,
        seconds=round(seconds, 1),
    )


def save_outputs(stem: str, svg: str, rendered: np.ndarray, heat: Image.Image) -> None:
    output_dir = OUTPUT_DIR / stem
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "drawing.svg").write_text(svg, encoding="utf-8")
    Image.fromarray(rendered).save(output_dir / "rendered.png")
    heat.save(output_dir / "heatmap.png")


def sample_paths(arguments: list[str]) -> list[Path]:
    if arguments:
        return [Path(argument) for argument in arguments]
    return sorted(path for path in SAMPLES_DIR.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)


def load_previous() -> dict[str, dict[str, float]]:
    return json.loads(RESULTS_FILE.read_text(encoding="utf-8")) if RESULTS_FILE.exists() else {}


def report(stem: str, score: Score, previous: dict[str, float] | None) -> str:
    change = ""
    if previous:
        change = f"  (was {previous['mean_delta_e']:.2f} / {previous['visible_share']:.2%} / {previous['size_kb']}KB)"
    return (
        f"{stem:28s} dE={score.mean_delta_e:6.2f}  visible={score.visible_share:7.2%}  "
        f"p99={score.p99_delta_e:6.1f}  {score.size_kb:5d}KB  {score.seconds:5.1f}s{change}"
    )


def main(arguments: list[str]) -> None:
    previous = load_previous()
    results = dict(previous)
    for image_path in sample_paths(arguments):
        score = score_image(image_path)
        print(report(image_path.stem, score, previous.get(image_path.stem)), flush=True)
        results[image_path.stem] = asdict(score)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
