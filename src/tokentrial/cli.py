"""Command-line entry point: `tokentrial run`, `tokentrial report`, `tokentrial doctor`."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from tokentrial import __version__, tools
from tokentrial.arms import ARMS, PILOT_ARMS, unavailable_arms
from tokentrial.claude_code import API_CREDENTIAL_VARS, auth_status
from tokentrial.pricing import load_prices
from tokentrial.runner import Checkpoint, Config, run_experiment
from tokentrial.tasks import load_tasks

app = typer.Typer(
    help="Measure whether token-saving tools reduce cost per correctly solved task.",
    no_args_is_help=True,
)

EXIT_NOT_READY = 2
EXIT_USAGE_LIMIT = 3
EXIT_BUDGET = 4
EXIT_FATAL = 5


class Mode(StrEnum):
    subscription = "subscription"
    api = "api"


def _version(value: bool) -> None:
    if value:
        typer.echo(f"tokentrial {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
    ] = False,
) -> None:
    pass


def _claude_bin(value: str) -> list[str]:
    return shlex.split(value)


def _preflight(mode: Mode, claude_bin: list[str]) -> list[str]:
    """Problems that would stop a real run, as human-readable strings."""
    if not shutil.which(claude_bin[0]):
        return [f"`{claude_bin[0]}` not found on PATH. Install Claude Code first."]
    problems = []
    status = auth_status(claude_bin, mode.value)
    if mode is Mode.subscription:
        if not status.get("loggedIn"):
            problems.append("Claude Code is not logged in. Run: claude auth login")
        elif status.get("authMethod") != "claude.ai":
            problems.append(
                f"Claude Code auth method is {status.get('authMethod')!r}, not a claude.ai "
                "subscription. Run: claude auth login"
            )
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        problems.append("--mode api needs ANTHROPIC_API_KEY in the environment.")
    return problems


@app.command()
def doctor(
    mode: Annotated[Mode, typer.Option(help="Mode to check.")] = Mode.subscription,
    claude_bin: Annotated[str, typer.Option(help="Claude Code command.", hidden=True)] = "claude",
) -> None:
    """Check that Claude Code is installed and logged in. Makes no model calls."""
    cmd = _claude_bin(claude_bin)
    if shutil.which(cmd[0]):
        ver = subprocess.run([*cmd, "--version"], capture_output=True, text=True).stdout.strip()
        typer.echo(f"claude: {ver}")
        status = auth_status(cmd, mode.value)
        typer.echo(
            f"auth: loggedIn={status.get('loggedIn')} method={status.get('authMethod')} "
            f"plan={status.get('subscriptionType')}"
        )
    if mode is Mode.subscription and any(os.environ.get(v) for v in API_CREDENTIAL_VARS):
        typer.echo(
            "note: ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN is set; it will be removed from "
            "the agent's environment so runs use the subscription."
        )
    problems = _preflight(mode, cmd)
    for p in problems:
        typer.echo(f"problem: {p}", err=True)
    if problems:
        raise typer.Exit(code=EXIT_NOT_READY)
    typer.echo(f"ready for --mode {mode.value}")


@app.command()
def run(
    arms: Annotated[
        list[str] | None, typer.Option("--arm", "-a", help="Arm to run (repeatable).")
    ] = None,
    tasks_dir: Annotated[Path, typer.Option("--tasks", help="Task directory.")] = Path("tasks"),
    task_ids: Annotated[
        list[str] | None, typer.Option("--task", "-t", help="Only these task IDs (repeatable).")
    ] = None,
    mode: Annotated[
        Mode,
        typer.Option(
            help="subscription: logged-in Claude Code, API-equivalent cost (default). "
            "api: bill ANTHROPIC_API_KEY."
        ),
    ] = Mode.subscription,
    provider: Annotated[str, typer.Option(help="Price table: anthropic | bedrock")] = "anthropic",
    model: Annotated[str, typer.Option(help="Model ID priced in pricing.toml.")] = (
        "claude-haiku-5-5"
    ),
    repeats: Annotated[int, typer.Option(min=1, help="Runs per (task, arm) pair.")] = 3,
    seed: Annotated[int, typer.Option(help="Seed for the interleaved run order.")] = 0,
    max_usd: Annotated[
        float | None,
        typer.Option(min=0, help="Stop the experiment once total cost exceeds this."),
    ] = 30.0,
    max_usd_per_run: Annotated[
        float | None,
        typer.Option(min=0, help="Abort a single agent run once its cost exceeds this."),
    ] = 1.0,
    out: Annotated[Path, typer.Option(help="Experiment directory.")] = Path("runs/pilot"),
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Continue the experiment in --out, skipping finished runs."),
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print the plan and exit.")] = False,
    claude_bin: Annotated[str, typer.Option(help="Claude Code command.", hidden=True)] = "claude",
) -> None:
    """Run every task under every arm and record token usage and correctness."""
    ckpt = Checkpoint(out)
    if resume:
        if not ckpt.exists():
            raise typer.BadParameter(f"nothing to resume in {out}/", param_hint="--out")
        config = ckpt.load_config()
        typer.echo(f"resuming {out}/ with its saved configuration (other options ignored)")
    else:
        all_tasks = [t.id for t in load_tasks(tasks_dir)] if tasks_dir.is_dir() else []
        selected_tasks = list(task_ids) if task_ids else all_tasks
        unknown_tasks = sorted(set(selected_tasks) - set(all_tasks))
        if unknown_tasks:
            raise typer.BadParameter(f"unknown task(s): {', '.join(unknown_tasks)}")
        config = Config(
            mode=mode.value,
            provider=provider,
            model=model,
            arms=list(arms or PILOT_ARMS),
            task_ids=selected_tasks,
            repeats=repeats,
            seed=seed,
            max_usd=max_usd,
            max_usd_per_run=max_usd_per_run,
        )

    unknown = [a for a in config.arms if a not in ARMS]
    if unknown:
        raise typer.BadParameter(f"unknown arm(s): {', '.join(unknown)}", param_hint="--arm")
    if config.mode == Mode.subscription and config.provider != "anthropic":
        raise typer.BadParameter("subscription mode is priced against the anthropic table")
    prices = load_prices()
    key = (
        config.provider,
        config.model if config.provider == "anthropic" else f"anthropic.{config.model}",
    )
    if key not in prices:
        raise typer.BadParameter(f"no price for {key[0]}/{key[1]}")

    cost_label = "API-equivalent cost" if config.mode == Mode.subscription else "billed cost"
    n_runs = len(config.task_ids) * len(config.arms) * config.repeats
    typer.echo(
        f"mode={config.mode} provider={config.provider} model={config.model} "
        f"repeats={config.repeats}"
    )
    typer.echo(f"arms: {', '.join(config.arms)}")
    typer.echo(f"tasks: {', '.join(config.task_ids) or '(none)'}")
    typer.echo(f"planned agent runs: {n_runs}")
    typer.echo(f"caps ({cost_label}): total ${config.max_usd}, per run ${config.max_usd_per_run}")
    if not prices[key].verified:
        typer.echo("warning: price entry is unverified; results cannot be published.")
    not_ready = unavailable_arms(config.arms)
    for arm_name, reason in not_ready.items():
        typer.echo(f"warning: arm {arm_name}: {reason}")

    if dry_run:
        return

    if n_runs == 0:
        typer.echo("No runs planned (no tasks found).", err=True)
        raise typer.Exit(code=EXIT_NOT_READY)
    if not_ready:
        typer.echo(
            "Some arms cannot run yet (see warnings). Install them with "
            "`tokentrial install-arms`, or pick others with --arm.",
            err=True,
        )
        raise typer.Exit(code=EXIT_NOT_READY)
    if not resume and ckpt.exists():
        typer.echo(
            f"{out}/ already has an experiment. Use --resume to continue it, "
            "or choose a new --out.",
            err=True,
        )
        raise typer.Exit(code=EXIT_NOT_READY)
    cmd = _claude_bin(claude_bin)
    problems = _preflight(Mode(config.mode), cmd)
    if problems:
        for p in problems:
            typer.echo(f"problem: {p}", err=True)
        raise typer.Exit(code=EXIT_NOT_READY)

    if not resume:
        ckpt.create(config)
    tasks = {t.id: t for t in load_tasks(tasks_dir)}
    aux_prices = {
        m: p for (prov, m), p in prices.items() if prov == config.provider and m != key[1]
    }
    outcome = run_experiment(
        config, tasks, prices[key], ckpt, cmd, log=typer.echo, aux_prices=aux_prices
    )

    typer.echo(f"finished {outcome.finished} run(s), skipped {outcome.skipped} already done")
    if outcome.stopped_reason == "usage_limit":
        when = (
            datetime.fromtimestamp(outcome.reset_epoch).strftime("%Y-%m-%d %H:%M")
            if outcome.reset_epoch
            else "later"
        )
        typer.echo(
            f"Paused: usage limit reached. Progress is saved. Continue after {when} with:\n"
            f"  tokentrial run --resume --out {out}"
        )
        raise typer.Exit(code=EXIT_USAGE_LIMIT)
    if outcome.stopped_reason == "fatal":
        typer.echo(
            f"Stopped: {outcome.message}\nIf this is an auth error, run `claude auth login` in a "
            f"terminal, then: tokentrial run --resume --out {out}",
            err=True,
        )
        raise typer.Exit(code=EXIT_FATAL)
    if outcome.stopped_reason == "budget":
        typer.echo(f"Stopped: total budget ${config.max_usd} reached. Results so far are saved.")
        raise typer.Exit(code=EXIT_BUDGET)


@app.command("install-arms")
def install_arms(
    arms: Annotated[
        list[str] | None, typer.Option("--arm", "-a", help="Tool to install (repeatable).")
    ] = None,
) -> None:
    """Download the pinned versions of the tools under test into a local cache.

    rtk: release binary from GitHub, verified against the release checksums.
    caveman: git clone of the pinned tag, verified against the pinned commit.
    Nothing is written to your global Claude Code configuration.
    """
    names = list(arms or tools.INSTALLERS)
    unknown = [n for n in names if n not in tools.INSTALLERS]
    if unknown:
        raise typer.BadParameter(f"nothing to install for: {', '.join(unknown)}")
    for name in names:
        pin = tools.PINS[name]
        typer.echo(f"{name} {pin.version} ({pin.source}) -> {tools.tool_dir(pin)}")
        tools.INSTALLERS[name](log=lambda m: typer.echo(f"  {m}"))
        typer.echo("  ok")


@app.command()
def report(
    runs: Annotated[Path, typer.Option(help="Experiment directory.")] = Path("runs/pilot"),
    out: Annotated[Path, typer.Option(help="Leaderboard output directory.")] = Path("site"),
) -> None:
    """Aggregate runs into cost per solved task with bootstrap CIs; build the leaderboard."""
    typer.echo("Reporting is not implemented yet (see docs/PLAN.md, week 2).", err=True)
    raise typer.Exit(code=EXIT_NOT_READY)


if __name__ == "__main__":
    app()
