"""Accumulate events into size-bounded batches."""

import json


class Batcher:
    def __init__(self, max_bytes, max_messages):
        self.max_bytes = max_bytes
        self.max_messages = max_messages
        self._items = []
        self._size = 2  # "[]"

    def __len__(self):
        return len(self._items)

    def add(self, event):
        """Add an event; return a full batch (bytes) if this event did not fit."""
        encoded = json.dumps(event, separators=(",", ":")).encode()
        extra = len(encoded) + (1 if self._items else 0)
        if self._items and (
            self._size + extra > self.max_bytes or len(self._items) >= self.max_messages
        ):
            batch = self.flush()
            self._items.append(encoded)
            self._size += len(encoded)
            return batch
        self._items.append(encoded)
        self._size += extra
        return None

    def flush(self):
        if not self._items:
            return None
        batch = b"[" + b",".join(self._items) + b"]"
        self._items = []
        self._size = 2
        return batch
