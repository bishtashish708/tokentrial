import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "ts": self.formatTime(record),
                "level": record.levelname.lower(),
                "logger": record.name,
                "msg": record.getMessage(),
            }
        )


def configure_logging(cfg):
    handler = logging.StreamHandler(sys.stderr)
    if cfg["json"]:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(cfg["level"].upper())
