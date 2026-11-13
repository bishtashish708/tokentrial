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


def test_export_raw_scrubs_home_path(tmp_path, monkeypatch):
    import json
    import tarfile
    from pathlib import Path

    from tokentrial.report import export_raw

    home = str(Path.home())
    exp = tmp_path / "exp"
    (exp / "logs").mkdir(parents=True)
    (exp / "manifest.json").write_text(json.dumps({"x": 1}))
    (exp / "records.jsonl").write_text(json.dumps({"p": f"{home}/.cache/x"}) + "\n")
    import getpass

    me = getpass.getuser()
    (exp / "logs" / "a.jsonl").write_text(
        f'{{"path": "{home}/.claude/projects/y", "ls": "-rw-r--r--  1 {me}  staff  29", '
        f'"ps": "3\\n{me}  84061  2.0  python3"}}\n'
    )
    out = export_raw(exp, tmp_path / "raw")
    assert home not in (tmp_path / "raw" / "records.jsonl").read_text()
    with tarfile.open(out[-1]) as tar:
        text = tar.extractfile("logs/a.jsonl").read().decode()
    assert home not in text and "~/.claude/projects/y" in text
    assert me not in text and "1 user  staff" in text
    assert "3\\nuser  84061" in text


def test_tools_compared_with_noop_hook_control():
    from tokentrial.report import to_markdown

    s = summarize(
        _records({"baseline": 1.2, "noop": 1.2, "noop-hook": 1.0, "caveman": 1.0}), n_boot=300
    )
    vs = s["arms"]["caveman"]["vs_noop_hook"]
    assert abs(vs["point"]) < 1e-9  # same as the hook control: no tool effect
    assert s["arms"]["caveman"]["vs_baseline"]["point"] < -0.1
    assert "verdict" not in s["arms"]["noop-hook"]
    md = to_markdown(
        s,
        {
            "model": "m",
            "mode": "subscription",
            "task_ids": list("abcde"),
            "arms": list(s["arms"]),
            "repeats": 3,
        },
    )
    assert "vs the `noop-hook` control" in md


def test_tools_are_compared_with_their_matched_control():
    costs = {"baseline": 1.0, "noop": 1.0, "headroom-passthrough": 0.8, "headroom": 0.8}
    costs |= {"rtk": 1.3, "caveman": 0.9}
    s = summarize(_records(costs), n_boot=200)["arms"]
    assert s["headroom"]["matched_control"] == "headroom-passthrough"
    assert abs(s["headroom"]["vs_matched_control"]["point"]) < 1e-9
    assert s["headroom"]["vs_baseline"]["point"] < -0.15
    assert s["rtk"]["vs_matched_control"] == s["rtk"]["vs_baseline"]
    # noop-hook absent: caveman has no matched comparison rather than a wrong one.
    assert "vs_matched_control" not in s["caveman"]
    assert "verdict" not in s["headroom-passthrough"]
