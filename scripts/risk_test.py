import base64
import io
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from meta_sam_parser import (
    CompletedOutcome,
    SegmentationMaskRecord,
    decode_mask_to_raster,
    image_segmentation_format,
)
from openai import OpenAI
from PIL import Image, ImageChops, ImageOps

ART_DIRECTOR_MODEL = "muse-spark-1.3"
CUTTER_MODEL = "sam-3.1"
MAX_IMAGE_SIDE = 1024
OUTPUT_DIR = Path("output/risk-test")
SPARK_INPUT_USD_PER_TOKEN = 1.25 / 1_000_000
SPARK_OUTPUT_USD_PER_TOKEN = 4.25 / 1_000_000
SAM_USD_PER_IMAGE = 2.50 / 1_000

ART_DIRECTOR_PROMPT = """You are the art director of a vector drawing studio.
Break this image into the distinct visual elements an illustrator would draw as separate layers.
For each element give:
- name: a short kebab-case layer name, such as "sun-body" or "left-hill"
- description: one sentence about its shape and color
- sam_prompt: a short noun phrase a segmentation model can use to find it, such as "yellow sun"
List the elements in drawing order: background first, then large shapes, then details.
Also give the overall style and the main palette as hex colors."""

ART_DIRECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["style", "palette", "elements"],
    "properties": {
        "style": {"type": "string"},
        "palette": {"type": "array", "items": {"type": "string"}},
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "description", "sam_prompt"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "sam_prompt": {"type": "string"},
                },
            },
        },
    },
}


@dataclass
class CallBudget:
    max_calls: int
    calls: int = 0
    cost_usd: float = 0.0

    def reserve(self) -> None:
        if self.calls >= self.max_calls:
            raise RuntimeError(f"API call budget exhausted ({self.max_calls} calls)")
        self.calls += 1

    def record(self, model: str, cost_usd: float, details: str) -> None:
        self.cost_usd += cost_usd
        print(f"[api] call={self.calls} model={model} {details} cost=${cost_usd:.4f}")


def load_image(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    return image


def to_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def ask_art_director(client: OpenAI, budget: CallBudget, image_url: str) -> dict[str, Any]:
    budget.reserve()
    response = client.chat.completions.create(
        model=ART_DIRECTOR_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ART_DIRECTOR_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "ArtDirection", "strict": True, "schema": ART_DIRECTION_SCHEMA},
        },
    )
    record_spark_usage(budget, response.usage)
    return json.loads(response.choices[0].message.content or "{}")


def record_spark_usage(budget: CallBudget, usage: Any) -> None:
    details = usage.completion_tokens_details
    reasoning_tokens = details.reasoning_tokens if details else 0
    cost = usage.prompt_tokens * SPARK_INPUT_USD_PER_TOKEN + usage.completion_tokens * SPARK_OUTPUT_USD_PER_TOKEN
    tokens = f"input={usage.prompt_tokens} output={usage.completion_tokens} reasoning={reasoning_tokens}"
    budget.record(ART_DIRECTOR_MODEL, cost, tokens)


def cut_element(client: OpenAI, budget: CallBudget, image_url: str, prompt: str) -> list[SegmentationMaskRecord]:
    budget.reserve()
    events = client.responses.create(
        model=CUTTER_MODEL,
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
        stream=True,
    )
    output_text = collect_output_text(events)
    budget.record(CUTTER_MODEL, SAM_USD_PER_IMAGE, f'prompt="{prompt}"')
    return parse_mask_records(output_text)


def collect_output_text(events: Iterable[Any]) -> str:
    return "".join(event.delta for event in events if event.type == "response.output_text.delta")


def parse_mask_records(output_text: str) -> list[SegmentationMaskRecord]:
    parser = image_segmentation_format().create_parser()
    parser.push(output_text)
    result = parser.finish(CompletedOutcome()).result
    return [record for record in result.records if isinstance(record, SegmentationMaskRecord)]


def merge_masks(records: list[SegmentationMaskRecord], size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("L", size, 0)
    for record in records:
        canvas = ImageChops.lighter(canvas, place_mask(record, size))
    return canvas


def place_mask(record: SegmentationMaskRecord, size: tuple[int, int]) -> Image.Image:
    raster = decode_mask_to_raster(record.mask)
    mask = Image.frombytes("L", (record.mask.width, record.mask.height), raster).point(lambda value: 255 if value else 0)
    bounds = record.bounds
    left, top = round(bounds.left), round(bounds.top)
    box_size = (max(1, round(bounds.right) - left), max(1, round(bounds.bottom) - top))
    canvas = Image.new("L", size, 0)
    canvas.paste(mask.resize(box_size, Image.Resampling.NEAREST), (left, top))
    return canvas


def count_pixels(mask: Image.Image) -> int:
    return sum(mask.histogram()[1:])


def report_coverage(masks: list[Image.Image], size: tuple[int, int]) -> Image.Image:
    union = Image.new("L", size, 0)
    for mask in masks:
        union = ImageChops.lighter(union, mask)
    total = size[0] * size[1]
    covered = count_pixels(union)
    overlap = sum(count_pixels(mask) for mask in masks) - covered
    print(f"[coverage] covered={covered / total:.1%} uncovered={1 - covered / total:.1%} overlap={overlap / total:.1%}")
    return ImageOps.invert(union)


def save_outputs(
    output_dir: Path, image: Image.Image, direction: dict[str, Any], masks: dict[str, Image.Image], gaps: Image.Image
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    image.save(output_dir / "source.png")
    (output_dir / "art-direction.json").write_text(json.dumps(direction, indent=2), encoding="utf-8")
    for index, (name, mask) in enumerate(masks.items()):
        mask.save(output_dir / f"{index:02d}-{name}.png")
    gaps.save(output_dir / "uncovered.png")


def main(image_path: Path) -> None:
    load_dotenv()
    client = OpenAI(base_url=os.environ["MODEL_API_BASE_URL"], api_key=os.environ["MODEL_API_KEY"])
    budget = CallBudget(max_calls=int(os.environ["MAX_API_CALLS_PER_JOB"]))

    image = load_image(image_path)
    image_url = to_data_url(image)
    print(f"[image] {image_path} sent at {image.width}x{image.height}")

    direction = ask_art_director(client, budget, image_url)
    print(json.dumps(direction, indent=2))

    masks: dict[str, Image.Image] = {}
    for element in direction["elements"]:
        records = cut_element(client, budget, image_url, element["sam_prompt"])
        print(f"[cutter] {element['name']}: {len(records)} match(es)")
        masks[element["name"]] = merge_masks(records, image.size)

    gaps = report_coverage(list(masks.values()), image.size)
    output_dir = OUTPUT_DIR / image_path.stem
    save_outputs(output_dir, image, direction, masks, gaps)
    print(f"[done] calls={budget.calls} cost=${budget.cost_usd:.4f} outputs={output_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/risk_test.py <image-path>")
    main(Path(sys.argv[1]))
