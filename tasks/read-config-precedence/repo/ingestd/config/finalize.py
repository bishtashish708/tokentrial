"""Cross-setting validation and adjustments applied after all layers are merged."""

import logging

from ingestd.config.errors import ConfigError

log = logging.getLogger(__name__)

DEFAULT_ALIGN = 4096
LOG_LEVELS = {"debug", "info", "warning", "error"}


def _is_power_of_two(n):
    return n > 0 and n & (n - 1) == 0


def finalize(cfg):
    """Validate and adjust a fully merged, typed settings dict in place."""
    worker, queue, http = cfg["worker"], cfg["queue"], cfg["http"]

    if worker["count"] < 1:
        raise ConfigError("worker.count must be >= 1")
    if not 0 < http["port"] < 65536:
        raise ConfigError("http.port out of range")
    if cfg["logging"]["level"].lower() not in LOG_LEVELS:
        raise ConfigError(f"unknown logging.level {cfg['logging']['level']!r}")
    cfg["logging"]["level"] = cfg["logging"]["level"].lower()

    align = worker["batch_align_bytes"]
    if not _is_power_of_two(align):
        log.warning("worker.batch_align_bytes=%d is not a power of two; using %d", align, DEFAULT_ALIGN)
        align = worker["batch_align_bytes"] = DEFAULT_ALIGN

    # A batch is sent as one queue message, so it must fit in the broker's payload limit
    # after the envelope (headers, routing info, signature) is added.
    if queue["envelope_reserve_bytes"] >= queue["max_payload_bytes"]:
        raise ConfigError("queue.envelope_reserve_bytes must be smaller than queue.max_payload_bytes")
    ceiling = queue["max_payload_bytes"] - queue["envelope_reserve_bytes"]
    if worker["max_batch_bytes"] > ceiling:
        log.info("clamping worker.max_batch_bytes %d -> %d", worker["max_batch_bytes"], ceiling)
        worker["max_batch_bytes"] = ceiling

    # Batches are preallocated in aligned chunks; round down to a whole number of chunks.
    worker["max_batch_bytes"] -= worker["max_batch_bytes"] % align
    if worker["max_batch_bytes"] < align:
        worker["max_batch_bytes"] = align

    if http["max_body_bytes"] < 1024:
        raise ConfigError("http.max_body_bytes must be at least 1KiB")
    return cfg
