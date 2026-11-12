"""Spending caps: abort a run, or the whole experiment, once a USD limit is passed."""

from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """Raised when a per-run or total spending cap is exceeded."""


@dataclass
class Budget:
    """Tracks spend against an optional total cap and an optional per-run cap.

    In subscription mode, the amounts are API-equivalent costs. Nothing is
    actually billed, but the caps still limit how much of the usage allowance
    a run can use.
    """

    max_total_usd: float | None = None
    max_run_usd: float | None = None
    spent_total: float = 0.0
    spent_run: float = field(default=0.0, init=False)

    def start_run(self) -> None:
        self.spent_run = 0.0

    def charge(self, usd: float) -> None:
        """Record spend from one API call; raise if a cap is now exceeded."""
        self.spent_run += usd
        self.spent_total += usd
        if self.max_run_usd is not None and self.spent_run > self.max_run_usd:
            raise BudgetExceeded(
                f"run cost ${self.spent_run:.4f} exceeded --max-usd-per-run ${self.max_run_usd}"
            )
        if self.max_total_usd is not None and self.spent_total > self.max_total_usd:
            raise BudgetExceeded(
                f"total cost ${self.spent_total:.4f} exceeded --max-usd ${self.max_total_usd}"
            )
