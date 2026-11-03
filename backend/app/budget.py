import logging
import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("drawlab.budget")

DAILY_LIMIT_MESSAGE = "Drawlab reached its daily budget, please come back tomorrow"


class BudgetExceededError(RuntimeError):
    pass


@dataclass
class DailySpend:
    day: str = ""
    spent_usd: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def has_room(self, limit_usd: float) -> bool:
        with self._lock:
            self._roll_over()
            return self.spent_usd < limit_usd

    def add(self, cost_usd: float) -> float:
        with self._lock:
            self._roll_over()
            self.spent_usd += cost_usd
            return self.spent_usd

    def _roll_over(self) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self.day:
            self.day, self.spent_usd = today, 0.0


DAILY_SPEND = DailySpend()


@dataclass
class CallBudget:
    max_calls: int
    daily_limit_usd: float = math.inf
    calls: int = 0
    cost_usd: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def reserve(self) -> None:
        if not DAILY_SPEND.has_room(self.daily_limit_usd):
            raise BudgetExceededError(DAILY_LIMIT_MESSAGE)
        with self._lock:
            if self.calls >= self.max_calls:
                raise BudgetExceededError(f"API call budget exhausted ({self.max_calls} calls)")
            self.calls += 1

    def record(self, model: str, cost_usd: float, details: str) -> None:
        today = DAILY_SPEND.add(cost_usd)
        with self._lock:
            self.cost_usd += cost_usd
            total = self.cost_usd
        logger.info(
            "call=%d model=%s %s cost=$%.4f total=$%.4f today=$%.4f",
            self.calls, model, details, cost_usd, total, today,
        )
