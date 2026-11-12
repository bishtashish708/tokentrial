"""Experiment arms: the baseline, a no-op control, and the tools under test."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


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
            "Command-output compression via a shell proxy.",
            "https://github.com/rtk-ai/rtk",
        ),
        Arm(
            "caveman",
            "tool",
            "Terse-output prompting to cut output tokens.",
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


# --- Adapters: prepare a fresh workspace for an arm -------------------------

NOOP_MARKER = ".tokentrial-noop"


def _setup_baseline(workspace: Path) -> None:
    return None


def _setup_noop(workspace: Path) -> None:
    # Runs a setup step like a real tool would, but changes nothing that affects
    # the agent: a marker file that is never referenced.
    (workspace / NOOP_MARKER).write_text("tokentrial no-op control arm\n")


ADAPTERS: dict[str, Callable[[Path], None]] = {
    "baseline": _setup_baseline,
    "noop": _setup_noop,
    # "rtk" and "caveman" adapters land on plan day 4, pinned to specific versions.
}


def missing_adapters(arms: list[str]) -> list[str]:
    return [a for a in arms if a not in ADAPTERS]


def setup_arm(name: str, workspace: Path) -> None:
    ADAPTERS[name](workspace)
