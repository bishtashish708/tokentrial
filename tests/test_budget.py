import pytest

from tokentrial.budget import Budget, BudgetExceeded


def test_per_run_cap_resets_between_runs():
    b = Budget(max_run_usd=1.0)
    b.start_run()
    b.charge(0.9)
    b.start_run()
    b.charge(0.9)  # a fresh run, so this stays under the cap
    assert b.spent_total == pytest.approx(1.8)


def test_per_run_cap_aborts():
    b = Budget(max_run_usd=1.0)
    b.start_run()
    b.charge(0.6)
    with pytest.raises(BudgetExceeded, match="per-run"):
        b.charge(0.6)


def test_total_cap_aborts_across_runs():
    b = Budget(max_total_usd=1.0)
    for _ in range(2):
        b.start_run()
        b.charge(0.45)
    b.start_run()
    with pytest.raises(BudgetExceeded, match="--max-usd "):
        b.charge(0.2)


def test_no_caps_never_aborts():
    b = Budget()
    b.charge(1e6)
