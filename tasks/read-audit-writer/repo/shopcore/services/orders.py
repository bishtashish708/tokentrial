"""Order lifecycle."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from shopcore import settings
from shopcore.catalog.products import price_of
from shopcore.events.bus import publish

_ids = itertools.count(1000)


@dataclass
class Order:
    id: str
    user_id: str
    items: list[tuple[str, int]]
    status: str = "placed"
    total_cents: int = 0
    history: list[str] = field(default_factory=list)


class OrderService:
    def __init__(self, payments):
        self.payments = payments
        self.orders: dict[str, Order] = {}

    def place(self, user_id, items):
        if len(items) > settings.MAX_ITEMS_PER_ORDER:
            raise ValueError("too many items")
        order = Order(f"o{next(_ids)}", user_id, list(items))
        order.total_cents = sum(price_of(sku) * qty for sku, qty in items)
        self.payments.charge(order.id, order.total_cents)
        order.status = "paid"
        self.orders[order.id] = order
        publish("order.placed", {"order_id": order.id, "total_cents": order.total_cents})
        return order.id

    def cancel(self, order_id):
        order = self.orders[order_id]
        order.status = "cancelled"
        publish("order.cancelled", {"order_id": order_id})

    def refund(self, order_id, reason):
        order = self.orders[order_id]
        if order.status != "paid":
            raise ValueError(f"cannot refund order in status {order.status}")
        self.payments.refund(order.id, order.total_cents)
        order.status = "refunded"
        order.history.append(f"refunded:{reason}")
        publish(
            "order.refunded",
            {"order_id": order.id, "amount_cents": order.total_cents, "reason": reason},
        )
