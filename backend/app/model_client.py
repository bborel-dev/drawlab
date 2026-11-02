import base64
import io
import json
from typing import Any, Iterable, Literal

from openai import OpenAI
from PIL import Image

from app.budget import CallBudget
from app.config import Settings

SPARK_MODEL = "muse-spark-1.3"
SAM_MODEL = "sam-3.1"
IMAGE_MODEL = "muse-image-1.0"
SPARK_INPUT_USD_PER_TOKEN = 1.25 / 1_000_000
SPARK_OUTPUT_USD_PER_TOKEN = 4.25 / 1_000_000
SAM_USD_PER_IMAGE = 2.50 / 1_000
IMAGE_USD_PER_IMAGE = 0.01

ReasoningEffort = Literal["minimal", "low", "medium", "high"]


class ModelClient:
    def __init__(self, settings: Settings, budget: CallBudget) -> None:
        self._client = OpenAI(base_url=settings.model_api_base_url, api_key=settings.model_api_key)
        self._budget = budget

    def ask_for_json(
        self,
        prompt: str,
        image_urls: list[str],
        schema_name: str,
        schema: dict[str, Any],
        reasoning_effort: ReasoningEffort | None = None,
    ) -> dict[str, Any]:
        self._budget.reserve()
        images = [{"type": "image_url", "image_url": {"url": image_url}} for image_url in image_urls]
        effort = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        response = self._client.chat.completions.create(
            model=SPARK_MODEL,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, *images]}],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
            **effort,
        )
        self._record_spark_usage(response.usage)
        return json.loads(response.choices[0].message.content or "{}")

    def segment(self, image_url: str, prompt: str) -> str:
        self._budget.reserve()
        events = self._client.responses.create(
            model=SAM_MODEL,
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
        self._budget.record(SAM_MODEL, SAM_USD_PER_IMAGE, f'prompt="{prompt}"')
        return output_text

    def edit_image(self, image: Image.Image, prompt: str) -> Image.Image:
        self._budget.reserve()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        response = self._client.images.edit(
            model=IMAGE_MODEL,
            image=("drawing.png", buffer.getvalue(), "image/png"),
            prompt=prompt,
            n=1,
            size=f"{image.width}x{image.height}",
            extra_body={"output_format": "png"},
        )
        self._budget.record(IMAGE_MODEL, IMAGE_USD_PER_IMAGE, f'prompt="{prompt[:80]}"')
        encoded = response.data[0].b64_json if response.data else None
        if not encoded:
            raise ValueError("the image model returned no image")
        return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")

    def _record_spark_usage(self, usage: Any) -> None:
        if usage is None:
            self._budget.record(SPARK_MODEL, 0.0, "usage=missing")
            return
        details = usage.completion_tokens_details
        reasoning_tokens = details.reasoning_tokens if details else 0
        cost = usage.prompt_tokens * SPARK_INPUT_USD_PER_TOKEN + usage.completion_tokens * SPARK_OUTPUT_USD_PER_TOKEN
        tokens = f"input={usage.prompt_tokens} output={usage.completion_tokens} reasoning={reasoning_tokens}"
        self._budget.record(SPARK_MODEL, cost, tokens)


def collect_output_text(events: Iterable[Any]) -> str:
    return "".join(event.delta for event in events if event.type == "response.output_text.delta")
