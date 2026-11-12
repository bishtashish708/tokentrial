"""HTTP front end: POST /v1/events accepts a JSON array of events."""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)


class IngestServer:
    def __init__(self, cfg, queue, metrics):
        self.cfg = cfg
        self.queue = queue
        self.metrics = metrics
        self._httpd = None
        self._thread = None

    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            timeout = server.cfg["read_timeout_s"]

            def log_message(self, fmt, *args):  # route through logging
                log.debug("%s - " + fmt, self.address_string(), *args)

            def do_GET(self):
                if self.path == "/healthz":
                    return self._reply(200, b"ok\n")
                if self.path == "/metrics":
                    return self._reply(200, server.metrics.render().encode())
                return self._reply(404, b"not found\n")

            def do_POST(self):
                if self.path != "/v1/events":
                    return self._reply(404, b"not found\n")
                length = int(self.headers.get("Content-Length") or 0)
                if length > server.cfg["max_body_bytes"]:
                    server.metrics.incr("rejected_too_large")
                    return self._reply(413, b"body too large\n")
                try:
                    events = json.loads(self.rfile.read(length))
                except ValueError:
                    return self._reply(400, b"invalid json\n")
                if not isinstance(events, list):
                    return self._reply(400, b"expected a JSON array\n")
                for event in events:
                    server.queue.publish_event(event)
                server.metrics.incr("events_accepted", len(events))
                return self._reply(202, b"accepted\n")

            def _reply(self, status, body):
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def start(self):
        self._httpd = ThreadingHTTPServer((self.cfg["bind"], self.cfg["port"]), self._handler())
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        log.info("listening on %s:%d", self.cfg["bind"], self.cfg["port"])

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
