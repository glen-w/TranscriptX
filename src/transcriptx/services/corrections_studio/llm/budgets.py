"""Interactive runtime budgets for corrections LLM discovery."""

from __future__ import annotations

import time
from dataclasses import dataclass

# Matches Ollama client default transport retries so a single chunk's
# worst-case retry budget stays within remaining wall clock.
DEFAULT_TRANSPORT_MAX_ATTEMPTS = 3


@dataclass
class BudgetTracker:
    request_timeout_seconds: float
    total_wall_clock_seconds: float
    max_chunks: int
    _started: float
    chunks_started: int = 0
    transport_max_attempts: int = DEFAULT_TRANSPORT_MAX_ATTEMPTS

    @classmethod
    def start(
        cls,
        *,
        request_timeout_seconds: float,
        total_wall_clock_seconds: float,
        max_chunks: int,
        transport_max_attempts: int = DEFAULT_TRANSPORT_MAX_ATTEMPTS,
    ) -> "BudgetTracker":
        return cls(
            request_timeout_seconds=float(request_timeout_seconds),
            total_wall_clock_seconds=float(total_wall_clock_seconds),
            max_chunks=int(max_chunks),
            _started=time.monotonic(),
            transport_max_attempts=max(1, int(transport_max_attempts)),
        )

    def elapsed(self) -> float:
        return time.monotonic() - self._started

    def remaining_wall(self) -> float:
        return max(0.0, self.total_wall_clock_seconds - self.elapsed())

    def can_start_chunk(self) -> tuple[bool, str | None]:
        if self.chunks_started >= self.max_chunks:
            return False, "max_chunks"
        if self.remaining_wall() <= 0:
            return False, "budget_exhausted"
        return True, None

    def note_chunk_started(self) -> float:
        self.chunks_started += 1
        # Cap by remaining wall, then divide by transport retries so the
        # worst-case (all attempts timing out) stays within the budget.
        wall_cap = min(self.request_timeout_seconds, max(1.0, self.remaining_wall()))
        return max(1.0, wall_cap / float(self.transport_max_attempts))
