import json
import sys
from pathlib import Path

import pytest

from tokentrial.pricing import load_prices
from tokentrial.runner import Checkpoint, Config, run_experiment
from tokentrial.tasks import load_tasks

ROOT = Path(__file__).parent.parent
FAKE = [sys.executable, str(ROOT / "tests" / "fake_claude.py")]
TASKS = {t.id: t for t in load_tasks(ROOT / "tasks")}
TASK = next(iter(TASKS))
PRICE = load_prices()[("anthropic", "claude-haiku-5-5")]


def _config(**kw):
    base = dict(
        mode="subscription",
        provider="anthropic",
        model="claude-haiku-5-5",
        arms=["baseline", "noop"],
        task_ids=[TASK],
        repeats=2,
        seed=0,
        max_usd=30.0,
        max_usd_per_run=1.0,
    )
    return Config(**{**base, **kw})


@pytest.fixture
def fake_env(monkeypatch):
    monkeypatch.setenv("FAKE_SOLUTION", str(TASKS[TASK].solution))
    return monkeypatch


def _records(out):
    return [json.loads(x) for x in (out / "records.jsonl").read_text().splitlines()]


def test_full_run_records_solved_with_cost(fake_env, tmp_path):
    fake_env.setenv("FAKE_SCENARIO", "solve")
    cfg, ck = _config(), Checkpoint(tmp_path / "exp")
    ck.create(cfg)
    outcome = run_experiment(cfg, TASKS, PRICE, ck, FAKE, log=lambda *_: None)
    recs = _records(tmp_path / "exp")
    assert outcome.finished == 4 and outcome.stopped_reason is None
    assert all(r["status"] == "solved" for r in recs)
    assert all(r["cost_basis"] == "api_equivalent" for r in recs)
    assert recs[0]["usage"]["cache_read"] == 1000  # duplicate events not double counted
    assert recs[0]["cost_usd"]["total"] > 0
    assert (tmp_path / "exp" / "logs" / f"{recs[0]['run_id']}.jsonl").exists()


def test_unsolved_when_agent_does_nothing(fake_env, tmp_path):
    fake_env.setenv("FAKE_SCENARIO", "nothing")
    cfg, ck = _config(repeats=1, arms=["baseline"]), Checkpoint(tmp_path / "exp")
    ck.create(cfg)
    run_experiment(cfg, TASKS, PRICE, ck, FAKE, log=lambda *_: None)
    assert _records(tmp_path / "exp")[0]["status"] == "unsolved"


def test_usage_limit_pauses_and_resume_skips_finished(fake_env, tmp_path):
    fake_env.setenv("FAKE_SCENARIO", "solve")
    fake_env.setenv("FAKE_COUNTER", str(tmp_path / "count"))
    fake_env.setenv("FAKE_LIMIT_AFTER", "1")
    cfg, ck = _config(), Checkpoint(tmp_path / "exp")
    ck.create(cfg)

    first = run_experiment(cfg, TASKS, PRICE, ck, FAKE, log=lambda *_: None)
    assert first.stopped_reason == "usage_limit"
    assert first.reset_epoch == 1893456000
    assert first.finished == 1
    assert len(_records(tmp_path / "exp")) == 1  # the limited run is not recorded

    fake_env.setenv("FAKE_LIMIT_AFTER", "999")  # limit has reset
    second = run_experiment(
        cfg, TASKS, PRICE, Checkpoint(tmp_path / "exp"), FAKE, log=lambda *_: None
    )
    assert second.stopped_reason is None
    assert (second.skipped, second.finished) == (1, 3)
    ids = [r["run_id"] for r in _records(tmp_path / "exp")]
    assert len(ids) == len(set(ids)) == 4


def test_per_run_cap_aborts_run_but_continues(fake_env, tmp_path):
    fake_env.setenv("FAKE_SCENARIO", "expensive")
    cfg = _config(arms=["baseline"], repeats=2, max_usd_per_run=0.01)
    ck = Checkpoint(tmp_path / "exp")
    ck.create(cfg)
    outcome = run_experiment(cfg, TASKS, PRICE, ck, FAKE, log=lambda *_: None)
    recs = _records(tmp_path / "exp")
    assert [r["status"] for r in recs] == ["aborted_budget", "aborted_budget"]
    assert outcome.stopped_reason is None


def test_total_cap_stops_experiment(fake_env, tmp_path):
    fake_env.setenv("FAKE_SCENARIO", "expensive")
    cfg = _config(arms=["baseline"], repeats=3, max_usd=0.01, max_usd_per_run=None)
    ck = Checkpoint(tmp_path / "exp")
    ck.create(cfg)
    outcome = run_experiment(cfg, TASKS, PRICE, ck, FAKE, log=lambda *_: None)
    assert outcome.stopped_reason == "budget"
    assert len(_records(tmp_path / "exp")) == 1


def test_auth_failure_stops_without_recording(fake_env, tmp_path):
    fake_env.setenv("FAKE_SCENARIO", "auth_fail")
    cfg, ck = _config(), Checkpoint(tmp_path / "exp")
    ck.create(cfg)
    outcome = run_experiment(cfg, TASKS, PRICE, ck, FAKE, log=lambda *_: None)
    assert outcome.stopped_reason == "fatal"
    assert not (tmp_path / "exp" / "records.jsonl").exists()


def test_api_error_is_recorded_as_retryable_error(fake_env, tmp_path):
    fake_env.setenv("FAKE_SCENARIO", "api_error")
    cfg, ck = _config(arms=["baseline"], repeats=1), Checkpoint(tmp_path / "exp")
    ck.create(cfg)
    run_experiment(cfg, TASKS, PRICE, ck, FAKE, log=lambda *_: None)
    assert _records(tmp_path / "exp")[0]["status"] == "error"
    fake_env.setenv("FAKE_SCENARIO", "solve")
    again = run_experiment(
        cfg, TASKS, PRICE, Checkpoint(tmp_path / "exp"), FAKE, log=lambda *_: None
    )
    assert again.finished == 1  # the errored run was retried


def test_tool_arms_run_with_their_runtime(fake_env, fake_tools, tmp_path):
    fake_env.setenv("FAKE_SCENARIO", "solve")
    fake_env.setenv("FAKE_ARGV_LOG", str(tmp_path / "argv.log"))
    cfg = _config(arms=["rtk", "caveman"], repeats=1)
    ck = Checkpoint(tmp_path / "exp")
    ck.create(cfg)
    outcome = run_experiment(cfg, TASKS, PRICE, ck, FAKE, log=lambda *_: None)
    assert outcome.stopped_reason is None
    recs = {r["arm"]: r for r in _records(tmp_path / "exp")}
    assert recs["rtk"]["arm_version"] == "v1.1.0"
    assert recs["caveman"]["arm_version"] == "v4.0.1"
    argv = (tmp_path / "argv.log").read_text()
    assert "--plugin-dir" in argv


def test_arm_setup_failure_stops_experiment(fake_env, fake_tools, tmp_path):
    from tokentrial import tools

    (tools.rtk_bin_dir() / "rtk").write_text("#!/bin/sh\nexit 1\n")
    cfg = _config(arms=["rtk"], repeats=1)
    ck = Checkpoint(tmp_path / "exp")
    ck.create(cfg)
    outcome = run_experiment(cfg, TASKS, PRICE, ck, FAKE, log=lambda *_: None)
    assert outcome.stopped_reason == "fatal"
    assert "setup failed" in outcome.message
