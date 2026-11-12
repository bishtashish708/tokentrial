"""Queue backends. Only the in-memory backend ships in this repo; AMQP lives in the
deployment image."""

import collections
import json
import logging
import threading

from ingestd.queue.envelope import unwrap, wrap

log = logging.getLogger(__name__)


class MemoryQueue:
    def __init__(self, cfg, metrics):
        self.cfg = cfg
        self.metrics = metrics
        self._events = collections.deque()
        self._batches = collections.deque()
        self._cond = threading.Condition()

    def publish_event(self, event):
        with self._cond:
            self._events.append(event)
            self._cond.notify()

    def take_events(self, max_count, timeout):
        with self._cond:
            if not self._events:
                self._cond.wait(timeout)
            out = []
            while self._events and len(out) < max_count:
                out.append(self._events.popleft())
            return out

    def publish_batch(self, payload: bytes):
        message = wrap(payload)
        if len(message) > self.cfg["max_payload_bytes"]:
            self.metrics.incr("batches_dropped_oversize")
            log.error("dropping batch of %d bytes: over queue.max_payload_bytes", len(message))
            return False
        with self._cond:
            self._batches.append(message)
        self.metrics.incr("batches_published")
        return True

    def drain_batches(self):
        with self._cond:
            items, self._batches = list(self._batches), collections.deque()
        return [json.loads(unwrap(m)) for m in items]


def make_queue(cfg, metrics):
    if cfg["url"].startswith("memory://"):
        return MemoryQueue(cfg, metrics)
    raise RuntimeError(f"queue backend for {cfg['url']!r} is not available in this build")
