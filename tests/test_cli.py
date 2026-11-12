from typer.testing import CliRunner

from tokentrial.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tokentrial" in result.output


def test_run_dry_run_uses_pilot_defaults():
    result = runner.invoke(app, ["run", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "model=claude-haiku-5-5" in result.output
    assert "repeats=3" in result.output
    assert "arms: baseline, noop, rtk, caveman" in result.output
    assert "total $30.0" in result.output


def test_run_subscription_mode_reports_api_equivalent_cost():
    result = runner.invoke(app, ["run", "--dry-run", "--mode", "subscription"])
    assert result.exit_code == 0, result.output
    assert "API-equivalent cost" in result.output


def test_run_rejects_unknown_arm():
    result = runner.invoke(app, ["run", "--dry-run", "--arm", "nope"])
    assert result.exit_code != 0


def test_run_rejects_negative_budget():
    result = runner.invoke(app, ["run", "--dry-run", "--max-usd", "-1"])
    assert result.exit_code != 0


def test_report_stub_exits_nonzero():
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 2
