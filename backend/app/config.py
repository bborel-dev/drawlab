import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_API_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MAX_API_CALLS_PER_JOB = 60
DEFAULT_MAX_DAILY_SPEND_USD = 5.0
DEFAULT_MAX_CONVERSIONS_PER_VISITOR = 5
DEFAULT_MAX_EDITS_PER_VISITOR = 5
DEFAULT_MAX_PROPOSALS_PER_VISITOR = 30


@dataclass(frozen=True)
class Settings:
    model_api_key: str
    model_api_base_url: str
    max_api_calls_per_job: int
    mock_agents: bool
    max_daily_spend_usd: float
    max_conversions_per_visitor: int
    max_edits_per_visitor: int
    max_proposals_per_visitor: int
    allowed_origins: tuple[str, ...]


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        model_api_key=os.environ.get("MODEL_API_KEY", ""),
        model_api_base_url=os.environ.get("MODEL_API_BASE_URL", DEFAULT_API_BASE_URL),
        max_api_calls_per_job=int(os.environ.get("MAX_API_CALLS_PER_JOB", DEFAULT_MAX_API_CALLS_PER_JOB)),
        mock_agents=os.environ.get("MOCK_AGENTS", "true").lower() == "true",
        max_daily_spend_usd=float(os.environ.get("MAX_DAILY_SPEND_USD", DEFAULT_MAX_DAILY_SPEND_USD)),
        max_conversions_per_visitor=int(
            os.environ.get("MAX_CONVERSIONS_PER_VISITOR", DEFAULT_MAX_CONVERSIONS_PER_VISITOR)
        ),
        max_edits_per_visitor=int(os.environ.get("MAX_EDITS_PER_VISITOR", DEFAULT_MAX_EDITS_PER_VISITOR)),
        max_proposals_per_visitor=int(
            os.environ.get("MAX_PROPOSALS_PER_VISITOR", DEFAULT_MAX_PROPOSALS_PER_VISITOR)
        ),
        allowed_origins=origin_list(os.environ.get("ALLOWED_ORIGINS", "")),
    )


def origin_list(raw: str) -> tuple[str, ...]:
    return tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())
