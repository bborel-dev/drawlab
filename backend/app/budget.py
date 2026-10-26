import logging
from dataclasses import dataclass

logger = logging.getLogger("drawlab.budget")


class BudgetExceededError(RuntimeError):
    pass


@dataclass
class CallBudget:
    max_calls: int
    calls: int = 0
    cost_usd: float = 0.0

    def reserve(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceededError(f"API call budget exhausted ({self.max_calls} calls)")
        self.calls += 1

    def record(self, model: str, cost_usd: float, details: str) -> None:
        self.cost_usd += cost_usd
        logger.info("call=%d model=%s %s cost=$%.4f total=$%.4f", self.calls, model, details, cost_usd, self.cost_usd)
