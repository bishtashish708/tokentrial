"""Shipping labels."""

from shopcore.events.bus import subscribe

LABELS: list[str] = []


@subscribe("order.placed")
def create_label(payload):
    LABELS.append(f"label:{payload['order_id']}")


@subscribe("order.cancelled")
def void_label(payload):
    label = f"label:{payload['order_id']}"
    if label in LABELS:
        LABELS.remove(label)
