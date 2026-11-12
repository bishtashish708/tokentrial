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
