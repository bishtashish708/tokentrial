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


def usage_from_api(raw: dict) -> Usage:
    """Build a Usage from an Anthropic API / Claude Code `usage` object.

    Cache writes are split by TTL when `cache_creation` gives the breakdown;
    otherwise they are all counted as 5-minute writes.
    """
    split = raw.get("cache_creation") or {}
    w5 = split.get("ephemeral_5m_input_tokens")
    w1 = split.get("ephemeral_1h_input_tokens")
    total_write = int(raw.get("cache_creation_input_tokens") or 0)
    if w5 is None and w1 is None:
        w5, w1 = total_write, 0
    return Usage(
        input=int(raw.get("input_tokens") or 0),
        cache_write_5m=int(w5 or 0),
        cache_write_1h=int(w1 or 0),
        cache_read=int(raw.get("cache_read_input_tokens") or 0),
        output=int(raw.get("output_tokens") or 0),
    )


def add_usage(a: Usage, b: Usage) -> Usage:
    return Usage(**{t: getattr(a, t) + getattr(b, t) for t in TOKEN_TYPES})
