"""Price tables and per-run cost, split by token type."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib.resources import files

TOKEN_TYPES = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")


@dataclass(frozen=True)
class Price:
    """USD per 1M tokens for each token type."""

    provider: str
    model: str
    input: float
    cache_write_5m: float
    cache_write_1h: float
    cache_read: float
    output: float
    source: str = ""
    verified: bool = False


@dataclass(frozen=True)
class Usage:
    """Token counts for one agent run, summed over every API call in it."""

    input: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    output: int = 0


def load_prices() -> dict[tuple[str, str], Price]:
    raw = tomllib.loads(files("tokentrial").joinpath("data/pricing.toml").read_text())
    prices: dict[tuple[str, str], Price] = {}
    for provider, models in raw.items():
        for model, row in models.items():
            prices[(provider, model)] = Price(
                provider=provider,
                model=model,
                **{k: float(row[k]) for k in TOKEN_TYPES},
                source=row.get("source", ""),
                verified=bool(row.get("verified", False)),
            )
    return prices


def cost_breakdown(usage: Usage, price: Price) -> dict[str, float]:
    """USD cost per token type, plus a `total` key."""
    parts = {t: getattr(usage, t) * getattr(price, t) / 1_000_000 for t in TOKEN_TYPES}
    parts["total"] = sum(parts.values())
    return parts
