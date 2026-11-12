"""Ledger-style audit writers for money movements.

v1 records (write_refund_entry) store the raw payload. v2 records add an explicit sign and
currency. New kinds should be written with v2; see settings._MIGRATED_WRITERS.
"""

from shopcore import settings
from shopcore.audit import store
from shopcore.audit.default import write_entry


def write_refund_entry(payload: dict) -> None:
    """v1: kept for replaying old events."""
    write_entry({"kind": "refund", **payload})


def _v2_record(payload: dict) -> dict:
    return {
        "schema": 2,
        "kind": "refund",
        "currency": settings.CURRENCY,
        "sign": -1,
        **payload,
    }


def write_refund_entry_v2(payload: dict) -> None:
    store.append(_v2_record(payload))
