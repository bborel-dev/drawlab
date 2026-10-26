import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_API_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MAX_API_CALLS_PER_JOB = 20


@dataclass(frozen=True)
class Settings:
    model_api_key: str
    model_api_base_url: str
    max_api_calls_per_job: int
    mock_agents: bool


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        model_api_key=os.environ.get("MODEL_API_KEY", ""),
        model_api_base_url=os.environ.get("MODEL_API_BASE_URL", DEFAULT_API_BASE_URL),
        max_api_calls_per_job=int(os.environ.get("MAX_API_CALLS_PER_JOB", DEFAULT_MAX_API_CALLS_PER_JOB)),
        mock_agents=os.environ.get("MOCK_AGENTS", "true").lower() == "true",
    )
