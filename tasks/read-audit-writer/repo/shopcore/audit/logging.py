"""Deprecated audit logger, kept behind the legacy_audit_logger flag."""

from shopcore import settings
from shopcore.audit import store


def log_audit(kind: str, payload: dict) -> None:
    if not settings.FEATURE_FLAGS.get("legacy_audit_logger"):
        return
    store.append({"schema": 0, "kind": kind, **payload})
