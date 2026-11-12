"""Append-only audit store."""

STORE: list[dict] = []


def append(record: dict) -> None:
    STORE.append(dict(record))
