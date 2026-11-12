import os
from pathlib import Path

import pytest

from tokentrial import tools
from tokentrial.arms import ArmSetupError, setup_arm, unavailable_arms


def test_tool_arms_unavailable_until_installed():
    arms = ["baseline", "noop", "rtk", "rtk-v1.2.0", "caveman", "caveman-v4.1.0", "headroom"]
    reasons = unavailable_arms(arms)
    assert set(reasons) == {"rtk", "rtk-v1.2.0", "caveman", "caveman-v4.1.0", "headroom"}
    assert all("install-arms" in r for r in reasons.values())
    assert unavailable_arms(["nope"]) == {"nope": "no adapter yet"}


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
    shim = Path(env["PATH"].split(os.pathsep)[0]) / "rtk"
    # The shim shows rtk (only) a config view that has its global hook.
    assert "CLAUDE_CONFIG_DIR=" in shim.read_text() and str(tools.rtk_bin_dir()) in shim.read_text()
    assert env["RTK_TELEMETRY_DISABLED"] == "1"
    assert "CLAUDE_CONFIG_DIR" not in rt.env  # Claude Code's own config is unchanged
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
    rt.cleanup()
    assert rt.extra_args == ["--plugin-dir", str(tools.caveman_plugin_dir())]
    assert rt.env["CAVEMAN_DEFAULT_MODE"] == "caveman"
    (claude_dir / ".caveman-config-keep").write_text("pre-existing")
    rt = setup_arm("caveman", tmp_path)
    # Simulate the hooks writing their state during the session (names seen in real runs).
    (claude_dir / ".caveman-active").write_text("caveman")
    (claude_dir / ".caveman-mode-log.jsonl").write_text("{}")
    (claude_dir / ".caveman-nudge-shown").write_text("1")
    (claude_dir / ".caveman-sessions" / "new-session").write_text("caveman")
    rt.cleanup()
    assert sorted(p.name for p in claude_dir.glob(".caveman*")) == [
        ".caveman-config-keep",
        ".caveman-sessions",
    ]
    assert [p.name for p in (claude_dir / ".caveman-sessions").iterdir()] == ["keep"]


def test_noop_changes_nothing_the_agent_is_told_about(tmp_path):
    rt = setup_arm("noop", tmp_path)
    assert (rt.extra_args, rt.env, rt.path_prefix) == ([], {}, [])


def test_caveman_seeds_nudge_shown_and_removes_all_run_state(fake_tools, tmp_path):
    claude_dir = tmp_path / "claude-config"
    rt = setup_arm("caveman", tmp_path)
    assert (claude_dir / ".caveman-nudge-shown").read_text() == "1"  # long-time user
    # State observed from real caveman v4.0.1 sessions:
    (claude_dir / "hooks").mkdir()
    (claude_dir / "hooks" / "caveman-statusline.sh").write_text("#!/bin/sh")
    (claude_dir / "plugins" / "data" / "caveman-inline").mkdir(parents=True)
    (claude_dir / ".caveman-mode-log.jsonl").write_text("{}")
    rt.cleanup()
    assert not (claude_dir / "hooks").exists()
    assert not (claude_dir / "plugins" / "data").exists()
    assert not list(claude_dir.glob(".caveman*"))


def test_caveman_keeps_users_existing_hooks_dir(fake_tools, tmp_path):
    claude_dir = tmp_path / "claude-config"
    (claude_dir / "hooks").mkdir(parents=True)
    (claude_dir / "hooks" / "my-hook.sh").write_text("mine")
    (claude_dir / ".caveman-nudge-shown").write_text("1")
    rt = setup_arm("caveman", tmp_path)
    (claude_dir / "hooks" / "caveman-statusline.sh").write_text("#!/bin/sh")
    rt.cleanup()
    assert [p.name for p in (claude_dir / "hooks").iterdir()] == ["my-hook.sh"]
    assert (claude_dir / ".caveman-nudge-shown").exists()  # pre-existing: left alone


def test_noop_hook_installs_only_a_noop_sessionstart_hook(tmp_path):
    import json

    rt = setup_arm("noop-hook", tmp_path)
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings == {
        "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "true"}]}]}
    }
    assert (rt.extra_args, rt.env, rt.path_prefix) == ([], {}, [])


def test_versioned_arms_use_their_own_pins(fake_tools, tmp_path):
    from tokentrial.arms import setup_arm

    assert unavailable_arms(["rtk-v1.2.0", "caveman-v4.1.0"]) == {}
    ws = tmp_path / "ws"
    ws.mkdir()
    rt = setup_arm("rtk-v1.2.0", ws)
    try:
        assert rt.version == tools.RTK_V120.version
        shim = Path(rt.path_prefix[0]) / "rtk"
        assert str(tools.rtk_bin_dir(tools.RTK_V120)) in shim.read_text()
    finally:
        rt.cleanup()
    ws2 = tmp_path / "ws2"
    ws2.mkdir()
    rt = setup_arm("caveman-v4.1.0", ws2)
    assert rt.version == tools.CAVEMAN_V410.version
    assert rt.extra_args == ["--plugin-dir", str(tools.caveman_plugin_dir(tools.CAVEMAN_V410))]
    rt.cleanup()


def test_headroom_runs_a_proxy_and_registers_its_mcp_server(fake_tools, tmp_path):
    import json
    import urllib.request

    from tokentrial.arms import setup_arm

    ws = tmp_path / "ws"
    ws.mkdir()
    rt = setup_arm("headroom", ws)
    url = rt.env["ANTHROPIC_BASE_URL"]
    try:
        assert url.startswith("http://127.0.0.1:")
        assert rt.env["ENABLE_TOOL_SEARCH"] == "true"
        assert rt.allowed_tools == ["mcp__headroom"]
        cfg = json.loads(Path(rt.extra_args[1]).read_text())
        server = cfg["mcpServers"]["headroom"]
        assert server["args"] == ["mcp", "serve"]
        assert server["env"]["HEADROOM_PROXY_URL"] == url
        assert server["env"]["HEADROOM_TELEMETRY"] == "off"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"{url}/stats", timeout=5) as resp:
            assert json.load(resp)["ok"] is True
    finally:
        rt.cleanup()
    assert rt.metrics["headroom_stats"] == {"ok": True}
    # Nothing was written into the workspace or the real HOME.
    assert list(ws.iterdir()) == []
