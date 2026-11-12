"""Experiment arms: the baseline, a no-op control, and the tools under test.

Each arm has an adapter that prepares a fresh workspace and returns any extra
Claude Code arguments and environment it needs. Tools are installed per
workspace (project scope) or per session, never into the user's global config.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tokentrial import tools


@dataclass(frozen=True)
class Arm:
    name: str
    kind: str  # "baseline" | "control" | "tool"
    description: str
    upstream: str | None = None


ARMS: dict[str, Arm] = {
    a.name: a
    for a in [
        Arm("baseline", "baseline", "Unmodified agent, default configuration."),
        Arm(
            "noop",
            "control",
            "Same setup as baseline plus an install step that changes nothing. "
            "Estimates run-to-run noise: any 'saving' it shows is not a real effect.",
        ),
        Arm(
            "rtk",
            "tool",
            "Command-output compression: a PreToolUse hook rewrites Bash commands to `rtk ...`.",
            "https://github.com/rtk-ai/rtk",
        ),
        Arm(
            "caveman",
            "tool",
            "Terse-output mode loaded as a Claude Code plugin, default mode `caveman`.",
            "https://github.com/JuliusBrussee/caveman",
        ),
        Arm(
            "headroom",
            "tool",
            "Context compression layer.",
            "https://github.com/headroomlabs-ai/headroom",
        ),
    ]
}

# v0.1 pilot arms. headroom is defined but joins in the v0.2 scale-up.
PILOT_ARMS = ("baseline", "noop", "rtk", "caveman")


class ArmSetupError(RuntimeError):
    pass


@dataclass
class ArmRuntime:
    """What an arm adds to one Claude Code session."""

    extra_args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    path_prefix: list[str] = field(default_factory=list)
    version: str | None = None
    cleanup: Callable[[], None] | None = None
    # Filled by cleanup with arm-specific evidence (e.g. rtk's own command count).
    metrics: dict = field(default_factory=dict)

    def apply_env(self, env: dict[str, str]) -> dict[str, str]:
        out = {**env, **self.env}
        if self.path_prefix:
            out["PATH"] = os.pathsep.join([*self.path_prefix, env.get("PATH", "")])
        return out


# --- Adapters -----------------------------------------------------------------

NOOP_MARKER = ".tokentrial-noop"


def _setup_baseline(workspace: Path) -> ArmRuntime:
    return ArmRuntime()


def _setup_noop(workspace: Path) -> ArmRuntime:
    # A setup step like a real tool's, but nothing the agent is told about.
    (workspace / NOOP_MARKER).write_text("tokentrial no-op control arm\n")
    return ArmRuntime()


# rtk's Claude Code hook is only installed by the global `rtk init -g` (a project-scoped
# `rtk init` adds instructions but registers no hook). So the global install is generated
# in a throwaway HOME and its output copied into the workspace's project settings:
#   ~/.claude/settings.json  (PreToolUse/Bash -> `rtk hook claude`) -> ws/.claude/settings.json
#   ~/.claude/RTK.md, referenced by @RTK.md in ~/.claude/CLAUDE.md   -> ws/CLAUDE.md (inlined)
RTK_INIT_ARGS = ["init", "-g", "--auto-patch", "--no-trust-filters"]
RTK_MARKER = ".tokentrial-managed"


def rtk_state_dirs() -> list[Path]:
    """Where rtk keeps history.db and user filters for the real HOME."""
    home = Path.home()
    if platform.system() == "Darwin":
        return [home / "Library" / "Application Support" / "rtk"]
    data = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    config = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return [data / "rtk", config / "rtk"]


def _reset_rtk_state() -> None:
    """Give each run a fresh rtk state, refusing to touch rtk data tokentrial didn't create."""
    for d in rtk_state_dirs():
        if d.exists() and not (d / RTK_MARKER).exists():
            raise ArmSetupError(
                f"{d} holds rtk data tokentrial did not create (your own rtk install?). "
                "Move it aside before running the rtk arm."
            )
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        (d / RTK_MARKER).write_text("rtk state for tokentrial runs; reset before every run\n")


def _generate_rtk_global_install(rtk: Path) -> tuple[dict, str]:
    with tempfile.TemporaryDirectory(prefix="tokentrial-rtk-home-") as tmp:
        home = Path(tmp)
        (home / ".claude").mkdir()
        env = {
            **os.environ,
            "HOME": str(home),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "RTK_TELEMETRY_DISABLED": "1",
        }
        proc = subprocess.run(
            [str(rtk), *RTK_INIT_ARGS],
            cwd=home,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
        settings_path = home / ".claude" / "settings.json"
        if proc.returncode != 0 or not settings_path.exists():
            raise ArmSetupError(
                f"rtk init -g failed (exit {proc.returncode}): "
                f"{(proc.stderr or proc.stdout).strip()[:300]}"
            )
        settings = json.loads(settings_path.read_text())
        rtk_md = home / ".claude" / "RTK.md"
        instructions = rtk_md.read_text() if rtk_md.exists() else ""
    hooks = json.dumps(settings.get("hooks", {}))
    if "rtk hook" not in hooks:
        raise ArmSetupError(f"rtk init -g registered no rtk hook: {hooks[:300]}")
    return {"hooks": settings["hooks"]}, instructions


def _write_rtk_shim(rtk: Path, settings: dict) -> Path:
    """An `rtk` wrapper that shows rtk a Claude config dir containing its global hook.

    rtk checks the user's Claude settings for its hook and, when missing, prints a
    "No hook installed" warning into every command's output, which the agent then
    reads. A user with the real global install never sees it, so rtk alone is pointed
    at a per-run config view that has the hook. Claude Code itself is unaffected.
    """
    root = Path(tempfile.mkdtemp(prefix="tokentrial-rtk-"))
    (root / "claude-view").mkdir()
    (root / "claude-view" / "settings.json").write_text(json.dumps(settings) + "\n")
    (root / "bin").mkdir()
    shim = root / "bin" / "rtk"
    shim.write_text(f"#!/bin/sh\nCLAUDE_CONFIG_DIR='{root / 'claude-view'}' exec '{rtk}' \"$@\"\n")
    shim.chmod(0o755)
    return root


def _setup_rtk(workspace: Path) -> ArmRuntime:
    rtk = tools.rtk_bin_dir() / "rtk"
    _reset_rtk_state()
    settings, instructions = _generate_rtk_global_install(rtk)
    (workspace / ".claude").mkdir(exist_ok=True)
    (workspace / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    if instructions:
        (workspace / "CLAUDE.md").write_text(instructions)
    shim_root = _write_rtk_shim(rtk, settings)

    runtime = ArmRuntime(
        path_prefix=[str(shim_root / "bin")],
        # Telemetry off: no effect on what the agent sees; no usage data leaves the machine.
        env={"RTK_TELEMETRY_DISABLED": "1"},
        version=tools.RTK.version,
    )

    def cleanup() -> None:
        proc = subprocess.run(
            [str(shim_root / "bin" / "rtk"), "gain", "-f", "json"],
            cwd=workspace,
            env=runtime.apply_env(dict(os.environ)),
            capture_output=True,
            text=True,
            timeout=60,
        )
        try:
            runtime.metrics["rtk_gain"] = json.loads(proc.stdout)
        except json.JSONDecodeError:
            runtime.metrics["rtk_gain_error"] = (proc.stderr or proc.stdout).strip()[:300]
        for d in rtk_state_dirs():
            if (d / RTK_MARKER).exists():
                for p in d.iterdir():
                    if p.name != RTK_MARKER:
                        shutil.rmtree(p) if p.is_dir() else p.unlink()
        shutil.rmtree(shim_root, ignore_errors=True)

    runtime.cleanup = cleanup
    return runtime


def _claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def _setup_caveman(workspace: Path) -> ArmRuntime:
    plugin = tools.caveman_plugin_dir()
    if not (plugin / ".claude-plugin" / "plugin.json").exists():
        raise ArmSetupError(f"caveman plugin not found at {plugin}")

    # caveman's hooks keep state in the Claude config dir (.caveman-active,
    # .caveman-sessions/, .caveman-mode-log.jsonl, .caveman-nudge-shown, ...). Some of it
    # changes later sessions (e.g. a one-time nudge), so everything a run creates is
    # removed afterwards; entries that existed before the run are left alone.
    claude_dir = _claude_dir()
    sessions = claude_dir / ".caveman-sessions"
    before = {p.name for p in claude_dir.glob(".caveman*")}
    sessions_before = set(sessions.iterdir()) if sessions.is_dir() else set()

    def cleanup() -> None:
        for p in claude_dir.glob(".caveman*"):
            if p.name not in before:
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
        if sessions.name in before and sessions.is_dir():
            for p in set(sessions.iterdir()) - sessions_before:
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)

    return ArmRuntime(
        extra_args=["--plugin-dir", str(plugin)],
        # Headless sessions start with caveman off unless a default mode is set.
        env={"CAVEMAN_DEFAULT_MODE": "caveman"},
        version=tools.CAVEMAN.version,
        cleanup=cleanup,
    )


ADAPTERS: dict[str, Callable[[Path], ArmRuntime]] = {
    "baseline": _setup_baseline,
    "noop": _setup_noop,
    "rtk": _setup_rtk,
    "caveman": _setup_caveman,
}

# Arms whose tool must be installed with `tokentrial install-arms` first.
NEEDS_INSTALL = {"rtk": "rtk", "caveman": "caveman"}


def unavailable_arms(arms: list[str]) -> dict[str, str]:
    """Arm name -> reason it cannot run yet."""
    out = {}
    for a in arms:
        if a not in ADAPTERS:
            out[a] = "no adapter yet"
        elif a in NEEDS_INSTALL and not tools.installed(NEEDS_INSTALL[a]):
            out[a] = "not installed (run: tokentrial install-arms)"
    return out


def setup_arm(name: str, workspace: Path) -> ArmRuntime:
    return ADAPTERS[name](workspace)


def describe_versions(arms: list[str]) -> dict[str, str | None]:
    info = {}
    for a in arms:
        pin = tools.PINS.get(NEEDS_INSTALL.get(a, ""))
        if pin:
            meta = tools.tool_dir(pin) / "install.json"
            info[a] = json.loads(meta.read_text()).get("version") if meta.exists() else None
    return info
