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
    checked: str = ""
    # Prices for a request whose prompt (input + cache reads + cache writes) exceeds
    # long_threshold tokens; each request is priced on its own.
    long_threshold: int | None = None
    long: Price | None = None


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
            long_row = row.get("long_context")
            long = (
                Price(provider, model, **{k: float(long_row[k]) for k in TOKEN_TYPES})
                if long_row
                else None
            )
            prices[(provider, model)] = Price(
                provider=provider,
                model=model,
                **{k: float(row[k]) for k in TOKEN_TYPES},
                source=row.get("source", ""),
                verified=bool(row.get("verified", False)),
                checked=row.get("checked", ""),
                long_threshold=int(long_row["threshold"]) if long_row else None,
                long=long,
            )
    return prices


def prompt_tokens(u: Usage) -> int:
    """A request's prompt length as used for long-context pricing."""
    return u.input + u.cache_write_5m + u.cache_write_1h + u.cache_read


def price_for_call(price: Price, call: Usage) -> Price:
    if price.long and price.long_threshold and prompt_tokens(call) > price.long_threshold:
        return price.long
    return price


def tiered_cost(usage: Usage, price: Price, calls: list[Usage]) -> tuple[dict[str, float], int]:
    """Cost of `usage` (session totals) with long-context calls priced at the long tier.

    Input-side tokens of long calls come exactly from their per-call usage. Their output
    is estimated: per-call output counts in the stream are mid-stream snapshots, so the
    session's final output is split in proportion to the long calls' snapshot share.
    Returns (cost by type, number of long-context calls).
    """
    long_calls = [c for c in calls if price_for_call(price, c) is not price]
    if not long_calls:
        return cost_breakdown(usage, price), 0
    long_in = {
        t: min(sum(getattr(c, t) for c in long_calls), getattr(usage, t))
        for t in ("input", "cache_write_5m", "cache_write_1h", "cache_read")
    }
    snap_out = sum(c.output for c in calls)
    share = (
        sum(c.output for c in long_calls) / snap_out if snap_out else len(long_calls) / len(calls)
    )
    long_usage = Usage(**long_in, output=round(usage.output * share))
    short_usage = Usage(**{t: getattr(usage, t) - getattr(long_usage, t) for t in TOKEN_TYPES})
    a, b = cost_breakdown(short_usage, price), cost_breakdown(long_usage, price.long)
    return {k: a[k] + b[k] for k in a}, len(long_calls)


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
