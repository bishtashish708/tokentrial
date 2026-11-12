import pytest

from tokentrial.pricing import TOKEN_TYPES, Price, Usage, cost_breakdown, load_prices


def test_prices_load_and_are_complete():
    prices = load_prices()
    assert ("anthropic", "claude-sonnet-5-5") in prices
    for p in prices.values():
        for t in TOKEN_TYPES:
            assert getattr(p, t) >= 0


def test_cost_breakdown_sums_token_types():
    price = Price(
        "x", "m", input=2, cache_write_5m=2.5, cache_write_1h=4, cache_read=0.1, output=10
    )
    usage = Usage(input=1_000_000, cache_read=2_000_000, output=500_000)
    parts = cost_breakdown(usage, price)
    assert parts["input"] == pytest.approx(2.0)
    assert parts["cache_read"] == pytest.approx(0.2)
    assert parts["output"] == pytest.approx(5.0)
    assert parts["total"] == pytest.approx(7.2)


def test_all_prices_verified_with_source_and_date():
    for p in load_prices().values():
        assert p.verified and p.source.startswith("https://") and p.checked, p


def test_haiku_55_long_context_tier_loaded():
    p = load_prices()[("anthropic", "claude-haiku-5-5")]
    assert p.long_threshold == 100_000 and p.long.input == 0.50 and p.long.output == 2.50


def test_tiered_cost_prices_long_calls_at_long_rate():
    from tokentrial.pricing import tiered_cost

    p = load_prices()[("anthropic", "claude-haiku-5-5")]
    short = Usage(input=0, cache_read=50_000, output=10)
    long = Usage(input=0, cache_read=150_000, output=10)
    total = Usage(cache_read=200_000, output=1000)
    parts, n_long = tiered_cost(total, p, [short, long])
    assert n_long == 1
    # 50K reads at $0.01 + 150K at $0.05; output split 50/50 by snapshot share
    assert parts["cache_read"] == pytest.approx(0.0005 + 0.0075)
    assert parts["output"] == pytest.approx(500 * 0.50 / 1e6 + 500 * 2.50 / 1e6)
    standard, n = tiered_cost(total, p, [short])
    assert n == 0 and standard["cache_read"] == pytest.approx(0.002)
