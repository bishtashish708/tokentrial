import json

import pytest


@pytest.fixture(autouse=True)
def isolated_tool_cache(tmp_path, monkeypatch):
    """Never read or write the real ~/.cache/tokentrial or ~/.claude in tests."""
    monkeypatch.setenv("TOKENTRIAL_TOOLS_DIR", str(tmp_path / "tools"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-config"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "home" / ".local" / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "home" / ".config"))
    (tmp_path / "home").mkdir()
    return tmp_path / "tools"


@pytest.fixture
def fake_tools(isolated_tool_cache):
    """Install stand-ins for rtk and caveman into the isolated cache."""
    from tokentrial import tools

    rtk_dir = tools.tool_dir(tools.RTK)
    (rtk_dir / "bin").mkdir(parents=True)
    rtk = rtk_dir / "bin" / "rtk"
    # Mimics rtk 1.1.0: `init -g` writes the hook + RTK.md into $CLAUDE_CONFIG_DIR;
    # `gain -f json` reports commands processed.
    rtk.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = init ]; then\n'
        '  printf \'{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":'
        '[{"type":"command","command":"rtk hook claude"}]}]}}\' '
        '> "$CLAUDE_CONFIG_DIR/settings.json"\n'
        '  echo "# Command output (rtk)" > "$CLAUDE_CONFIG_DIR/RTK.md"\n'
        '  echo "@RTK.md" > "$CLAUDE_CONFIG_DIR/CLAUDE.md"\n'
        'elif [ "$1" = gain ]; then echo \'{"summary":{"total_commands":3}}\'\n'
        "fi\n"
    )
    rtk.chmod(0o755)
    (rtk_dir / "install.json").write_text(json.dumps({"version": tools.RTK.version}))

    cav_dir = tools.tool_dir(tools.CAVEMAN)
    (cav_dir / "src" / ".claude-plugin").mkdir(parents=True)
    (cav_dir / "src" / ".claude-plugin" / "plugin.json").write_text('{"name": "caveman"}')
    (cav_dir / "install.json").write_text(json.dumps({"version": tools.CAVEMAN.version}))
    return isolated_tool_cache
