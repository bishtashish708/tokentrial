"""Naive catalog search."""

from shopcore.catalog.products import PRICES_CENTS


def search(term: str) -> list[str]:
    term = term.lower().strip()
    return sorted(s for s in PRICES_CENTS if term in s)


def cheapest(n: int = 3) -> list[str]:
    return sorted(PRICES_CENTS, key=PRICES_CENTS.__getitem__)[:n]
