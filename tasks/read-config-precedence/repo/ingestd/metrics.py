"""Tiny in-process counters, exposed on GET /metrics."""

import threading
from collections import Counter


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters = Counter()

    def incr(self, name, n=1):
        with self._lock:
            self._counters[name] += n

    def snapshot(self):
        with self._lock:
            return dict(self._counters)

    def render(self):
        return "".join(f"ingestd_{k} {v}\n" for k, v in sorted(self.snapshot().items()))
