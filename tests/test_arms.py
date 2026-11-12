import os

import pytest

from tokentrial import tools
from tokentrial.arms import ArmSetupError, setup_arm, unavailable_arms


def test_tool_arms_unavailable_until_installed():
    reasons = unavailable_arms(["baseline", "noop", "rtk", "caveman", "headroom"])
    assert set(reasons) == {"rtk", "caveman", "headroom"}
    assert "install-arms" in reasons["rtk"]
    assert reasons["headroom"] == "no adapter yet"


def test_tool_arms_available_after_install(fake_tools):
    assert unavailable_arms(["rtk", "caveman"]) == {}


def test_rtk_installs_project_hook_and_puts_rtk_on_path(fake_tools, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    rt = setup_arm("rtk", ws)
    assert "rtk" in (ws / ".claude" / "settings.json").read_text()
    env = rt.apply_env({"PATH": "/usr/bin"})
    assert env["PATH"].split(os.pathsep)[0] == str(tools.rtk_bin_dir())
    assert rt.version == tools.RTK.version


def test_rtk_setup_fails_loudly_if_no_hook_written(fake_tools, tmp_path):
    (tools.rtk_bin_dir() / "rtk").write_text("#!/bin/sh\nexit 0\n")
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(ArmSetupError):
        setup_arm("rtk", ws)


def test_caveman_loads_plugin_per_session_and_cleans_up_state(fake_tools, tmp_path):
    claude_dir = tmp_path / "claude-config"
    (claude_dir / ".caveman-sessions").mkdir(parents=True)
    (claude_dir / ".caveman-sessions" / "keep").write_text("pre-existing")
    rt = setup_arm("caveman", tmp_path)
    assert rt.extra_args == ["--plugin-dir", str(tools.caveman_plugin_dir())]
    assert rt.env["CAVEMAN_DEFAULT_MODE"] == "caveman"
    # Simulate the hooks writing their state during the session.
    (claude_dir / ".caveman-active").write_text("caveman")
    (claude_dir / ".caveman-sessions" / "new-session").write_text("caveman")
    rt.cleanup()
    assert not (claude_dir / ".caveman-active").exists()
    assert [p.name for p in (claude_dir / ".caveman-sessions").iterdir()] == ["keep"]


def test_noop_changes_nothing_the_agent_is_told_about(tmp_path):
    rt = setup_arm("noop", tmp_path)
    assert (rt.extra_args, rt.env, rt.path_prefix) == ([], {}, [])
