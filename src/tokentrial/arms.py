"""Experiment arms: the baseline, a no-op control, and the tools under test.

Each arm has an adapter that prepares a fresh workspace and returns any extra
Claude Code arguments and environment it needs. Tools are installed per
workspace (project scope) or per session, never into the user's global config.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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


# `rtk init` without -g is project-scoped: it writes ./.claude/settings.json (the
# Bash PreToolUse hook), ./RTK.md and an @RTK.md reference in ./CLAUDE.md.
RTK_INIT_ARGS = ["init"]


def _setup_rtk(workspace: Path) -> ArmRuntime:
    bin_dir = tools.rtk_bin_dir()
    runtime = ArmRuntime(path_prefix=[str(bin_dir)], version=tools.RTK.version)
    env = runtime.apply_env(dict(os.environ))
    proc = subprocess.run(
        [str(bin_dir / "rtk"), *RTK_INIT_ARGS],
        cwd=workspace,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    settings = workspace / ".claude" / "settings.json"
    if proc.returncode != 0 or not settings.exists() or "rtk" not in settings.read_text():
        raise ArmSetupError(
            f"rtk init did not install a project hook (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()[:300]}"
        )
    return runtime


def _claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def _setup_caveman(workspace: Path) -> ArmRuntime:
    plugin = tools.caveman_plugin_dir()
    if not (plugin / ".claude-plugin" / "plugin.json").exists():
        raise ArmSetupError(f"caveman plugin not found at {plugin}")

    # caveman's hooks keep state in the Claude config dir. Remember what exists
    # so the run's own state files can be removed afterwards.
    claude_dir = _claude_dir()
    flag = claude_dir / ".caveman-active"
    sessions = claude_dir / ".caveman-sessions"
    had_flag = flag.exists()
    had_sessions = sessions.exists()
    before = set(sessions.iterdir()) if had_sessions else set()

    def cleanup() -> None:
        if not had_flag:
            flag.unlink(missing_ok=True)
        if not had_sessions:
            shutil.rmtree(sessions, ignore_errors=True)
        elif sessions.exists():
            for p in set(sessions.iterdir()) - before:
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
