import math

from tokentrial.report import bootstrap, summarize


def _rec(arm, task, rep, solved, cost):
    usage = {t: 0 for t in ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")}
    cost_usd = {t: 0.0 for t in usage} | {"output": cost, "total": cost}
    return {
        "run_id": f"{task}__{arm}__r{rep}",
        "arm": arm,
        "task": task,
        "repeat": rep,
        "status": "solved" if solved else "unsolved",
        "solved": solved,
        "usage": usage,
        "cost_usd": cost_usd,
        "cost_main_usd": cost,
        "num_turns": 3,
        "duration_s": 1.0,
    }


def _records(costs):
    recs = []
    for arm, c in costs.items():
        for t in range(5):
            for r in range(3):
                recs.append(_rec(arm, f"t{t}", r, True, c * (1 + 0.05 * ((t + r) % 3))))
    return recs


def test_cost_per_solved_counts_failed_runs_cost():
    recs = [_rec("baseline", "t", 0, True, 1.0), _rec("baseline", "t", 1, False, 1.0)]
    s = summarize(recs, n_boot=100)
    assert s["arms"]["baseline"]["cost_per_solved"] == 2.0
    assert s["arms"]["baseline"]["solve_rate"] == 0.5


def test_clear_saving_beats_noise_floor():
    s = summarize(_records({"baseline": 1.0, "noop": 1.0, "cheap": 0.5}), n_boot=500)
    assert s["arms"]["cheap"]["verdict"].startswith("cheaper")
    assert s["arms"]["cheap"]["vs_baseline"]["point"] < -0.4


def test_no_difference_is_inconclusive():
    s = summarize(_records({"baseline": 1.0, "noop": 1.0, "same": 1.0}), n_boot=500)
    assert s["arms"]["same"]["verdict"].startswith("inconclusive")


def test_bootstrap_is_seeded_and_handles_no_solves():
    by = {"a": {"t": [_rec("a", "t", 0, False, 1.0)]}}
    s1 = bootstrap(by, n=50, seed=1)
    assert all(math.isinf(v) for v in s1["a"])
    by2 = {"a": {"t": [_rec("a", "t", 0, True, 1.0), _rec("a", "t", 1, True, 2.0)]}}
    assert bootstrap(by2, n=50, seed=3) == bootstrap(by2, n=50, seed=3)
