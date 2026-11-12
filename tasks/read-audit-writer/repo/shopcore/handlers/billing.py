"""Billing side effects of order events."""

from shopcore.audit.registry import writer_for
from shopcore.events.bus import subscribe


def _audit(kind: str, payload: dict) -> None:
    writer_for(kind)(payload)


@subscribe("order.placed")
def on_placed(payload):
    _audit("order.placed", payload)


@subscribe("order.refunded")
def on_refund(payload):
    _audit("refund", {**payload, "amount_cents": -payload["amount_cents"]})
