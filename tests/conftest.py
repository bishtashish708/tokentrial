import json
import shutil
import sys

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

    # Newer pins: same stand-ins in their own directories.
    for old, new in ((tools.RTK, tools.RTK_V120), (tools.CAVEMAN, tools.CAVEMAN_V410)):
        shutil.copytree(tools.tool_dir(old), tools.tool_dir(new))
        (tools.tool_dir(new) / "install.json").write_text(json.dumps({"version": new.version}))

    # headroom stand-in: `proxy --port N` serves {"ok": true} on every GET.
    hr = tools.headroom_bin()
    hr.parent.mkdir(parents=True)
    hr.write_text(
        f"#!{sys.executable}\n"
        "import http.server, json, socketserver, sys\n"
        "if sys.argv[1] == 'proxy':\n"
        "    port = int(sys.argv[sys.argv.index('--port') + 1])\n"
        "    class H(http.server.BaseHTTPRequestHandler):\n"
        "        def do_GET(self):\n"
        "            body = json.dumps({'ok': True}).encode()\n"
        "            self.send_response(200); self.end_headers(); self.wfile.write(body)\n"
        "        def log_message(self, *a): pass\n"
        "    socketserver.TCPServer(('127.0.0.1', port), H).serve_forever()\n"
    )
    hr.chmod(0o755)
    (tools.tool_dir(tools.HEADROOM) / "install.json").write_text(
        json.dumps({"version": tools.HEADROOM.version})
    )
    return isolated_tool_cache
