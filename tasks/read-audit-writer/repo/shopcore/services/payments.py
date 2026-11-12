"""Payment gateway stub."""

from shopcore.audit.logging import log_audit


class PaymentGateway:
    def __init__(self):
        self.ledger: list[tuple[str, str, int]] = []

    def charge(self, order_id: str, cents: int) -> None:
        self.ledger.append(("charge", order_id, cents))

    def refund(self, order_id: str, cents: int) -> None:
        self.ledger.append(("refund", order_id, -cents))
        # Legacy hook: only active when the legacy_audit_logger feature flag is on.
        log_audit("payment.refund", {"order_id": order_id, "cents": cents})
