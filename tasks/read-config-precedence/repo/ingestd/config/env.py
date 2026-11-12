"""Settings from environment variables."""

import logging

log = logging.getLogger(__name__)

PREFIX = "INGESTD_"

# Used for choosing files, not settings.
RESERVED = {"INGESTD_CONFIG", "INGESTD_PROFILE"}

# Names from ingestd 1.x, before the INGESTD_<SECTION>__<NAME> scheme.
ENV_ALIASES = {
    "INGESTD_PORT": "http.port",
    "INGESTD_WORKERS": "worker.count",
    "INGESTD_LOG_LEVEL": "logging.level",
    "INGESTD_BATCH_BYTES": "worker.max_batch_bytes",
    "INGESTD_ENVELOPE_RESERVE": "queue.envelope_reserve_bytes",
    "INGESTD_QUEUE_URL": "queue.url",
}


def env_name_to_key(name):
    """INGESTD_WORKER__MAX_BATCH_BYTES -> "worker.max_batch_bytes" (None if not of that form)."""
    if not name.startswith(PREFIX):
        return None
    parts = name[len(PREFIX):].split("__")
    if len(parts) != 2 or not all(parts):
        return None
    return f"{parts[0].lower()}.{parts[1].lower()}"


def env_layer(environ):
    """Return the settings layer for `environ` as a flat {"section.name": str} dict."""
    layer = {}
    for name in sorted(environ):
        if not name.startswith(PREFIX) or name in RESERVED or name in ENV_ALIASES:
            continue
        key = env_name_to_key(name)
        if key is None:
            log.warning("ignoring environment variable %s (expected %s<SECTION>__<NAME>)", name, PREFIX)
            continue
        layer[key] = environ[name]

    # Old names are applied last: deployments that still export them must keep the
    # behaviour they had before the rename, even if a new-style name is also present.
    for old_name, key in ENV_ALIASES.items():
        if old_name in environ:
            if key in layer:
                log.warning("%s overrides the value set for %s", old_name, key)
            layer[key] = environ[old_name]
    return layer
