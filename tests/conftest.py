import json

import pytest


@pytest.fixture(autouse=True)
def isolated_tool_cache(tmp_path, monkeypatch):
    """Never read or write the real ~/.cache/tokentrial or ~/.claude in tests."""
    monkeypatch.setenv("TOKENTRIAL_TOOLS_DIR", str(tmp_path / "tools"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-config"))
    return tmp_path / "tools"


@pytest.fixture
def fake_tools(isolated_tool_cache):
    """Install stand-ins for rtk and caveman into the isolated cache."""
    from tokentrial import tools

    rtk_dir = tools.tool_dir(tools.RTK)
    (rtk_dir / "bin").mkdir(parents=True)
    rtk = rtk_dir / "bin" / "rtk"
    rtk.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = init ]; then mkdir -p .claude && '
        'echo \'{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":'
        '[{"type":"command","command":"rtk hook claude"}]}]}}\' > .claude/settings.json'
        " && echo '# RTK' > RTK.md; fi\n"
    )
    rtk.chmod(0o755)
    (rtk_dir / "install.json").write_text(json.dumps({"version": tools.RTK.version}))

    cav_dir = tools.tool_dir(tools.CAVEMAN)
    (cav_dir / "src" / ".claude-plugin").mkdir(parents=True)
    (cav_dir / "src" / ".claude-plugin" / "plugin.json").write_text('{"name": "caveman"}')
    (cav_dir / "install.json").write_text(json.dumps({"version": tools.CAVEMAN.version}))
    return isolated_tool_cache
