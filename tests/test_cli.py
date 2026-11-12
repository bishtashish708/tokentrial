import sys
from pathlib import Path

from typer.testing import CliRunner

from tokentrial.cli import app

runner = CliRunner()
FAKE = f"{sys.executable} {Path(__file__).parent / 'fake_claude.py'}"


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tokentrial" in result.output


def test_run_dry_run_defaults_to_subscription_pilot():
    result = runner.invoke(app, ["run", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "mode=subscription" in result.output
    assert "model=claude-haiku-5-5" in result.output
    assert "repeats=3" in result.output
    assert "arms: baseline, noop, rtk, caveman" in result.output
    assert "API-equivalent cost" in result.output
    assert "arm rtk: not installed" in result.output
    assert "arm caveman: not installed" in result.output


def test_run_api_mode_reports_billed_cost():
    result = runner.invoke(app, ["run", "--dry-run", "--mode", "api"])
    assert result.exit_code == 0, result.output
    assert "billed cost" in result.output


def test_run_refuses_arms_without_adapter():
    result = runner.invoke(app, ["run", "--claude-bin", FAKE])
    assert result.exit_code == 2
    assert "install-arms" in result.output


def test_run_rejects_unknown_arm():
    result = runner.invoke(app, ["run", "--dry-run", "--arm", "nope"])
    assert result.exit_code != 0


def test_run_rejects_negative_budget():
    result = runner.invoke(app, ["run", "--dry-run", "--max-usd", "-1"])
    assert result.exit_code != 0


def test_resume_without_experiment_fails(tmp_path):
    result = runner.invoke(app, ["run", "--resume", "--out", str(tmp_path / "none")])
    assert result.exit_code != 0


def test_end_to_end_with_fake_claude_and_resume_refusal(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_SCENARIO", "nothing")
    out = tmp_path / "exp"
    args = [
        "run",
        "--arm",
        "baseline",
        "--task",
        "py-ledger-parens",
        "--repeats",
        "1",
        "--out",
        str(out),
        "--claude-bin",
        FAKE,
    ]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert (out / "records.jsonl").exists()
    again = runner.invoke(app, args)
    assert again.exit_code == 2 and "--resume" in again.output
    resumed = runner.invoke(app, ["run", "--resume", "--out", str(out), "--claude-bin", FAKE])
    assert resumed.exit_code == 0, resumed.output
    assert "skipped 1" in resumed.output


def test_doctor_with_fake_claude():
    result = runner.invoke(app, ["doctor", "--claude-bin", FAKE])
    assert result.exit_code == 0, result.output
    assert "ready for --mode subscription" in result.output


def test_report_without_records_fails(tmp_path):
    result = runner.invoke(app, ["report", "--runs", str(tmp_path)])
    assert result.exit_code == 2


def test_report_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_SCENARIO", "solve")
    monkeypatch.setenv("FAKE_SOLUTION", str(Path("tasks/py-ledger-parens/solution").resolve()))
    exp = tmp_path / "exp"
    run = runner.invoke(
        app,
        [
            "run",
            "--arm",
            "baseline",
            "--arm",
            "noop",
            "--task",
            "py-ledger-parens",
            "--repeats",
            "2",
            "--out",
            str(exp),
            "--claude-bin",
            FAKE,
        ],
    )
    assert run.exit_code == 0, run.output
    out = tmp_path / "res"
    rep = runner.invoke(
        app, ["report", "--runs", str(exp), "--out", str(out), "--resamples", "200"]
    )
    assert rep.exit_code == 0, rep.output
    assert (out / "summary.json").exists() and "`noop`" in (out / "summary.md").read_text()


def _fake_args(out, *extra):
    return [
        "run",
        "--arm",
        "baseline",
        "--task",
        "py-ledger-parens",
        "--repeats",
        "1",
        "--out",
        str(out),
        "--claude-bin",
        FAKE,
        *extra,
    ]


def test_several_models_get_one_experiment_each(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("FAKE_SCENARIO", "nothing")
    log = tmp_path / "argv.log"
    monkeypatch.setenv("FAKE_ARGV_LOG", str(log))
    out = tmp_path / "exp"
    args = _fake_args(out, "--model", "claude-haiku-5-5", "--model", "claude-sonnet-5-5")
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert json.loads((out / "models.json").read_text()) == [
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
    ]
    for m in ("claude-haiku-5-5", "claude-sonnet-5-5"):
        manifest = json.loads((out / m / "manifest.json").read_text())
        assert manifest["model"] == m
        rec = json.loads((out / m / "records.jsonl").read_text().splitlines()[0])
        assert rec["model"] == m
    calls = [line for line in log.read_text().splitlines() if "--print" in line]
    assert "claude-haiku-5-5" in calls[0] and "claude-sonnet-5-5" in calls[1]
    assert runner.invoke(app, args).exit_code == 2
    resumed = runner.invoke(app, ["run", "--resume", "--out", str(out), "--claude-bin", FAKE])
    assert resumed.exit_code == 0, resumed.output
    assert resumed.output.count("skipped 1") == 2


def test_dry_run_rejects_unpriced_model():
    result = runner.invoke(app, ["run", "--dry-run", "--model", "claude-nope"])
    assert result.exit_code != 0 and "no price" in result.output


def test_pause_at_utilization_stops_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_SCENARIO", "nothing")
    monkeypatch.setenv("FAKE_UTILIZATION", "0.75")
    out = tmp_path / "exp"
    args = _fake_args(out, "--repeats", "2", "--pause-at-utilization", "0.7")
    paused = runner.invoke(app, args)
    assert paused.exit_code == 3, paused.output
    assert "75%" in paused.output and "--resume" in paused.output
    assert len((out / "records.jsonl").read_text().splitlines()) == 1
    monkeypatch.setenv("FAKE_UTILIZATION", "0.2")
    resumed = runner.invoke(app, ["run", "--resume", "--out", str(out), "--claude-bin", FAKE])
    assert resumed.exit_code == 0, resumed.output
    assert "skipped 1" in resumed.output
