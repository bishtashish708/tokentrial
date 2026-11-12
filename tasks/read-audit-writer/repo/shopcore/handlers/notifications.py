"""Customer notifications."""

from shopcore.events.bus import subscribe

OUTBOX: list[tuple[str, str]] = []


@subscribe("order.placed")
def on_placed(payload):
    OUTBOX.append(("order_confirmation", payload["order_id"]))


@subscribe("order.refunded")
def on_refund(payload):
    OUTBOX.append(("refund_confirmation", payload["order_id"]))
