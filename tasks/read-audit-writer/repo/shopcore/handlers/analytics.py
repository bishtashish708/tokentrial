"""Analytics counters."""

from collections import Counter

from shopcore.events.bus import subscribe

COUNTS: Counter = Counter()


@subscribe("order.placed")
def count_placed(payload):
    COUNTS["placed"] += 1


@subscribe("order.refunded")
def count_refunded(payload):
    COUNTS["refunded"] += 1
