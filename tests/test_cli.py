from typer.testing import CliRunner

from tokentrial.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tokentrial" in result.output


def test_run_dry_run_lists_all_v1_arms():
    result = runner.invoke(app, ["run", "--dry-run"])
    assert result.exit_code == 0, result.output
    for arm in ("baseline", "noop", "rtk", "caveman", "headroom"):
        assert arm in result.output


def test_run_rejects_unknown_arm():
    result = runner.invoke(app, ["run", "--dry-run", "--arm", "nope"])
    assert result.exit_code != 0


def test_report_stub_exits_nonzero():
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 2
