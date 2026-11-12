"""Public API. Thin wrappers over the service layer."""

from shopcore.services.orders import OrderService
from shopcore.services.payments import PaymentGateway

_service = OrderService(PaymentGateway())


def place_order(user_id: str, items: list[tuple[str, int]]) -> str:
    return _service.place(user_id, items)


def cancel_order(order_id: str) -> None:
    _service.cancel(order_id)


def refund_order(order_id: str, reason: str = "customer_request") -> None:
    """Refund a paid order in full."""
    _service.refund(order_id, reason=reason)
