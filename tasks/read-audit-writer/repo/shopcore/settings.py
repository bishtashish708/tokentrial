"""Runtime settings. Values here are read at import time by the modules that use them."""

CURRENCY = "USD"
MAX_ITEMS_PER_ORDER = 50
EVENT_BUS_SYNC = True

# Audit writers by event kind. Values are "module:function" paths, resolved lazily by
# shopcore.audit.registry. "*" is the fallback for kinds without their own writer.
AUDIT_WRITERS = {
    "*": "shopcore.audit.default:write_entry",
    "order.placed": "shopcore.audit.default:write_entry",
    "refund": "shopcore.audit.ledger:write_refund_entry",
}

# Writers migrated to the v2 ledger schema (see docs in shopcore/audit/ledger.py).
# Applied last so they take precedence over the table above.
_MIGRATED_WRITERS = {
    "refund": "shopcore.audit.ledger:write_refund_entry_v2",
}
AUDIT_WRITERS.update(_MIGRATED_WRITERS)

FEATURE_FLAGS = {
    "split_shipments": False,
    "gift_wrap": True,
    "legacy_audit_logger": False,
}
