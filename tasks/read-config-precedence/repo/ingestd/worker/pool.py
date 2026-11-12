"""Worker threads: pull events from the queue, batch them, publish batches to the sink."""

import logging
import threading

from ingestd.worker.batcher import Batcher

log = logging.getLogger(__name__)


class WorkerPool:
    def __init__(self, cfg, queue, sink, metrics):
        self.cfg = cfg
        self.queue = queue
        self.sink = sink
        self.metrics = metrics
        self._stop = threading.Event()
        self._threads = []

    def start(self):
        for i in range(self.cfg["count"]):
            t = threading.Thread(target=self._loop, name=f"worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self):
        self._stop.set()
        for t in self._threads:
            t.join(timeout=5)

    def _loop(self):
        batcher = Batcher(self.cfg["max_batch_bytes"], self.cfg["max_batch_messages"])
        interval = self.cfg["flush_interval_ms"] / 1000
        while not self._stop.is_set():
            for event in self.queue.take_events(self.cfg["max_batch_messages"], interval):
                full = batcher.add(event)
                if full is not None:
                    self._emit(full)
            if len(batcher):
                self._emit(batcher.flush())
        leftover = batcher.flush()
        if leftover:
            self._emit(leftover)

    def _emit(self, batch):
        try:
            self.sink.write(batch)
            self.metrics.incr("batches_written")
        except OSError:
            log.exception("sink write failed")
            self.metrics.incr("sink_errors")
