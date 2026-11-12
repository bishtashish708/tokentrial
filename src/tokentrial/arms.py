"""Experiment arms: the baseline, a no-op control, and the tools under test."""

from __future__ import annotations

from dataclasses import dataclass


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

V1_ARMS = ("baseline", "noop", "rtk", "caveman", "headroom")
