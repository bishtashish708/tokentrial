"""Default audit writer."""

from shopcore.audit import store


def write_entry(payload: dict) -> None:
    store.append({"schema": 1, **payload})
