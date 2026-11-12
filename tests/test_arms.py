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


def test_rtk_copies_global_install_into_project_scope(fake_tools, tmp_path):
    import json

    ws = tmp_path / "ws"
    ws.mkdir()
    rt = setup_arm("rtk", ws)
    settings = json.loads((ws / ".claude" / "settings.json").read_text())
    hook = settings["hooks"]["PreToolUse"][0]
    assert hook["matcher"] == "Bash" and hook["hooks"][0]["command"] == "rtk hook claude"
    assert "rtk" in (ws / "CLAUDE.md").read_text()  # RTK.md inlined, no @import
    env = rt.apply_env({"PATH": "/usr/bin"})
    assert env["PATH"].split(os.pathsep)[0] == str(tools.rtk_bin_dir())
    assert env["RTK_TELEMETRY_DISABLED"] == "1"
    assert rt.version == tools.RTK.version
    # The real Claude config dir is untouched.
    assert not (tmp_path / "claude-config" / "settings.json").exists()


def test_rtk_state_is_fresh_per_run_and_gain_is_collected(fake_tools, tmp_path):
    from tokentrial.arms import RTK_MARKER, rtk_state_dirs

    ws = tmp_path / "ws"
    ws.mkdir()
    rt = setup_arm("rtk", ws)
    state = rtk_state_dirs()[0]
    (state / "history.db").write_text("run data")
    rt.cleanup()
    assert rt.metrics["rtk_gain"] == {"summary": {"total_commands": 3}}
    assert [p.name for p in state.iterdir()] == [RTK_MARKER]


def test_rtk_refuses_to_touch_users_own_rtk_state(fake_tools, tmp_path):
    from tokentrial.arms import rtk_state_dirs

    state = rtk_state_dirs()[0]
    state.mkdir(parents=True)
    (state / "history.db").write_text("the user's real history")
    with pytest.raises(ArmSetupError, match="did not create"):
        setup_arm("rtk", tmp_path)
    assert (state / "history.db").read_text() == "the user's real history"


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
