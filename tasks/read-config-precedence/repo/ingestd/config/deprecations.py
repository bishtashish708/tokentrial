"""Renamed settings that are still accepted."""

import logging
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger(__name__)


def _kb_to_bytes(value):
    # batch_size_kb predates the size parser. It was always documented as a whole number
    # of kilobytes (1 kB = 1000 bytes); keep that meaning when translating.
    return int(str(value).strip()) * 1000


@dataclass(frozen=True)
class Deprecation:
    new_key: str
    convert: Optional[Callable] = None
    since: str = ""


DEPRECATED = {
    "worker.batch_size_kb": Deprecation("worker.max_batch_bytes", _kb_to_bytes, since="2.0"),
    "queue.reserve_bytes": Deprecation("queue.envelope_reserve_bytes", since="2.1"),
    "http.listen": Deprecation("http.bind", since="1.8"),
    "worker.threads": Deprecation("worker.count", since="1.5"),
}


def translate(layer, source):
    """Rewrite deprecated keys in one layer to their new names.

    If a layer sets both the old and the new key, the new key wins within that layer.
    """
    out = {k: v for k, v in layer.items() if k not in DEPRECATED}
    for old_key, value in layer.items():
        dep = DEPRECATED.get(old_key)
        if dep is None:
            continue
        if dep.new_key in layer:
            log.warning("%s: both %s and %s are set; ignoring %s", source, old_key, dep.new_key, old_key)
            continue
        log.warning("%s: %s is deprecated (since %s), use %s", source, old_key, dep.since, dep.new_key)
        out[dep.new_key] = dep.convert(value) if dep.convert else value
    return out
