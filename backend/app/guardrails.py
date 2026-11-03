import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Generator, TypeVar

from fastapi import HTTPException, Request

from app.budget import DAILY_LIMIT_MESSAGE, DAILY_SPEND
from app.config import Settings

logger = logging.getLogger("drawlab.guardrails")

QUOTA_WINDOW_SECONDS = 24 * 3600
STALE_JOB_SECONDS = 15 * 60
TOO_MANY_REQUESTS = 429
BUSY_MESSAGE = "Drawlab is drawing for someone else right now, please try again in a minute"
T = TypeVar("T")


class RateLimiter:
    def __init__(self, window_seconds: float = QUOTA_WINDOW_SECONDS) -> None:
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int) -> bool:
        with self._lock:
            hits = self._recent_hits(key)
            if len(hits) >= limit:
                return False
            hits.append(time.monotonic())
            return True

    def remaining(self, key: str, limit: int) -> int:
        with self._lock:
            return max(limit - len(self._recent_hits(key)), 0)

    def _recent_hits(self, key: str) -> deque[float]:
        cutoff = time.monotonic() - self._window
        for other in list(self._hits):
            hits = self._hits[other]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if not hits and other != key:
                del self._hits[other]
        return self._hits.setdefault(key, deque())


class JobSlot:
    def __init__(self, stale_after_seconds: float = STALE_JOB_SECONDS) -> None:
        self._stale_after = stale_after_seconds
        self._holder: tuple[int, str, float] | None = None
        self._next_token = 0
        self._lock = threading.Lock()

    def try_acquire(self, owner: str) -> int | None:
        now = time.monotonic()
        with self._lock:
            if self._holder and self._holder[1] != owner and now - self._holder[2] < self._stale_after:
                return None
            self._next_token += 1
            self._holder = (self._next_token, owner, now)
            return self._next_token

    def holds(self, token: int) -> bool:
        with self._lock:
            return self._is_holder(token)

    def release(self, token: int) -> None:
        with self._lock:
            if self._is_holder(token):
                self._holder = None

    def _is_holder(self, token: int) -> bool:
        return self._holder is not None and self._holder[0] == token


@dataclass(frozen=True)
class Allowance:
    left: int
    limit: int


@dataclass(frozen=True)
class Quota:
    conversions: Allowance
    edits: Allowance
    open: bool


CONVERSIONS = RateLimiter()
EDITS = RateLimiter()
REPAINTS = RateLimiter()
PROPOSALS = RateLimiter()
DRAWING_SLOT = JobSlot()


def client_ip(request: Request, settings: Settings) -> str:
    chain = [address.strip() for address in request.headers.get("x-forwarded-for", "").split(",") if address.strip()]
    if chain:
        return chain[-min(settings.forwarded_hops, len(chain))]
    return request.client.host if request.client else "unknown"


def visitor_quota(request: Request, settings: Settings) -> Quota:
    visitor = client_ip(request, settings)
    logger.info("quota visitor=%s forwarded=%r", visitor, request.headers.get("x-forwarded-for", ""))
    return Quota(
        conversions=Allowance(
            CONVERSIONS.remaining(visitor, settings.max_conversions_per_visitor), settings.max_conversions_per_visitor
        ),
        edits=Allowance(EDITS.remaining(visitor, settings.max_edits_per_visitor), settings.max_edits_per_visitor),
        open=DAILY_SPEND.has_room(settings.max_daily_spend_usd),
    )


def admit_conversion(request: Request, settings: Settings) -> int:
    return admit_drawing(request, settings, CONVERSIONS, settings.max_conversions_per_visitor, "conversions")


def admit_repaint(request: Request, settings: Settings) -> int:
    return admit_drawing(request, settings, REPAINTS, settings.max_edits_per_visitor, "redraws")


def admit_edit(request: Request, settings: Settings) -> None:
    admit(request, settings, EDITS, settings.max_edits_per_visitor, "AI edits")


def admit_proposal(request: Request, settings: Settings) -> None:
    admit(request, settings, PROPOSALS, settings.max_proposals_per_visitor, "repaints")


def admit(request: Request, settings: Settings, limiter: RateLimiter, limit: int, kind: str) -> None:
    ensure_daily_room(settings)
    if not limiter.allow(client_ip(request, settings), limit):
        raise HTTPException(status_code=TOO_MANY_REQUESTS, detail=quota_message(kind))


def admit_drawing(request: Request, settings: Settings, limiter: RateLimiter, limit: int, kind: str) -> int:
    ensure_daily_room(settings)
    token = DRAWING_SLOT.try_acquire(client_ip(request, settings))
    if token is None:
        raise HTTPException(status_code=TOO_MANY_REQUESTS, detail=BUSY_MESSAGE)
    try:
        admit(request, settings, limiter, limit, kind)
    except HTTPException:
        DRAWING_SLOT.release(token)
        raise
    return token


def ensure_daily_room(settings: Settings) -> None:
    if not DAILY_SPEND.has_room(settings.max_daily_spend_usd):
        raise HTTPException(status_code=TOO_MANY_REQUESTS, detail=DAILY_LIMIT_MESSAGE)


def holding_slot(token: int, events: Generator[T, None, None]) -> Generator[T, None, None]:
    try:
        for event in events:
            if not DRAWING_SLOT.holds(token):
                return
            yield event
    finally:
        events.close()
        DRAWING_SLOT.release(token)


def quota_message(kind: str) -> str:
    return f"You used all your {kind} for today, please come back tomorrow"
