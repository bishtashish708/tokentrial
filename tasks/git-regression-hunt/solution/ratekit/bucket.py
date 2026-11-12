"""Token bucket rate limiter."""

import time


class TokenBucket:
    """Allows `rate` tokens per second, bursting up to `capacity` tokens."""

    def __init__(self, rate: float, capacity: float, clock=time.monotonic):
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate and capacity must be positive")
        self.rate = rate
        self.capacity = capacity
        self.clock = clock
        self.tokens = capacity
        self.updated = clock()

    def _refill(self) -> None:
        now = self.clock()
        elapsed = max(0.0, now - self.updated)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.updated = now

    def try_acquire(self, n: float = 1) -> bool:
        self._refill()
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False

    def wait_time(self, n: float = 1) -> float:
        """Seconds until `n` tokens are available (0 if available now)."""
        self._refill()
        missing = n - self.tokens
        return 0.0 if missing <= 0 else missing / self.rate
