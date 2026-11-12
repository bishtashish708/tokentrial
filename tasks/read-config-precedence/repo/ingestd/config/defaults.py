"""Built-in defaults. Every valid setting must appear here.

The type of each default decides how values from files, the environment and the command
line are converted: settings whose name ends in `_bytes` are sizes (see units.py).
"""

DEFAULTS = {
    "service": {
        "name": "ingestd",
        "profile": "dev",
        "data_dir": "./var",
    },
    "http": {
        "bind": "127.0.0.1",
        "port": 8040,
        "max_body_bytes": "2MiB",
        "read_timeout_s": 15.0,
    },
    "queue": {
        "url": "memory://",
        "max_payload_bytes": "4MiB",
        "envelope_reserve_bytes": "16KiB",
        "ack_timeout_s": 30.0,
    },
    "worker": {
        "count": 2,
        "max_batch_bytes": "1MiB",
        "max_batch_messages": 500,
        "batch_align_bytes": "4KiB",
        "flush_interval_ms": 250,
    },
    "sink": {
        "kind": "file",
        "path": "./var/out",
        "compress": False,
    },
    "logging": {
        "level": "info",
        "json": False,
    },
}


def known_keys():
    return {f"{section}.{name}" for section, values in DEFAULTS.items() for name in values}
