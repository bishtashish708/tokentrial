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
    args = ["run", "--arm", "baseline", "--repeats", "1", "--out", str(out), "--claude-bin", FAKE]
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


def test_report_stub_exits_nonzero():
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 2
