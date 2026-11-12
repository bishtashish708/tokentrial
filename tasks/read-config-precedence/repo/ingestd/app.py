"""Wire the components together and run until interrupted."""

import logging
import signal
import threading

from ingestd.http.server import IngestServer
from ingestd.logsetup import configure_logging
from ingestd.metrics import Metrics
from ingestd.queue.client import make_queue
from ingestd.sinks import make_sink
from ingestd.worker.pool import WorkerPool

log = logging.getLogger(__name__)


def run(settings):
    configure_logging(settings["logging"])
    metrics = Metrics()
    queue = make_queue(settings["queue"], metrics)
    sink = make_sink(settings["sink"], settings["service"])
    pool = WorkerPool(settings["worker"], queue, sink, metrics)
    server = IngestServer(settings["http"], queue, metrics)

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    log.info("starting %s (profile=%s)", settings["service"]["name"], settings["service"]["profile"])
    pool.start()
    server.start()
    try:
        stop.wait()
    finally:
        server.stop()
        pool.stop()
        sink.close()
    return 0
