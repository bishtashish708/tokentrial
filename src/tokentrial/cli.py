"""Command-line entry point: `tokentrial run` and `tokentrial report`."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from tokentrial import __version__
from tokentrial.arms import ARMS, PILOT_ARMS
from tokentrial.pricing import load_prices

app = typer.Typer(
    help="Measure whether token-saving tools reduce cost per correctly solved task.",
    no_args_is_help=True,
)


class Mode(StrEnum):
    api = "api"
    subscription = "subscription"


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


@app.command()
def run(
    arms: Annotated[
        list[str] | None, typer.Option("--arm", "-a", help="Arm to run (repeatable).")
    ] = None,
    tasks: Annotated[Path, typer.Option(help="Directory of task definitions.")] = Path("tasks"),
    mode: Annotated[
        Mode,
        typer.Option(
            help="api: bill an API key. subscription: use a logged-in Claude Code "
            "subscription and report API-equivalent cost."
        ),
    ] = Mode.api,
    provider: Annotated[str, typer.Option(help="Price table: anthropic | bedrock")] = "anthropic",
    model: Annotated[str, typer.Option(help="Model ID priced in pricing.toml.")] = (
        "claude-haiku-5-5"
    ),
    repeats: Annotated[int, typer.Option(min=1, help="Runs per (task, arm) pair.")] = 3,
    max_usd: Annotated[
        float | None,
        typer.Option(min=0, help="Abort the whole experiment once total cost exceeds this."),
    ] = 30.0,
    max_usd_per_run: Annotated[
        float | None,
        typer.Option(min=0, help="Abort a single agent run once its cost exceeds this."),
    ] = 1.0,
    out: Annotated[Path, typer.Option(help="Where raw run records are written.")] = Path("runs"),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print the plan and exit.")] = False,
) -> None:
    """Run every task under every arm and record token usage and correctness."""
    selected = list(arms or PILOT_ARMS)
    unknown = [a for a in selected if a not in ARMS]
    if unknown:
        raise typer.BadParameter(f"unknown arm(s): {', '.join(unknown)}", param_hint="--arm")
    if mode is Mode.subscription and provider != "anthropic":
        raise typer.BadParameter("subscription mode is priced against the anthropic table")

    prices = load_prices()
    price_key = (provider, model if provider == "anthropic" else f"anthropic.{model}")
    if price_key not in prices:
        raise typer.BadParameter(f"no price for {price_key[0]}/{price_key[1]}")

    n_tasks = len(list(tasks.glob("*/task.toml"))) if tasks.is_dir() else 0
    cost_label = "API-equivalent cost" if mode is Mode.subscription else "billed cost"
    typer.echo(f"mode={mode.value} provider={provider} model={model} repeats={repeats}")
    typer.echo(f"arms: {', '.join(selected)}")
    typer.echo(f"tasks found in {tasks}/: {n_tasks}")
    typer.echo(f"planned agent runs: {n_tasks * len(selected) * repeats}")
    typer.echo(f"caps ({cost_label}): total ${max_usd}, per run ${max_usd_per_run}")
    if not prices[price_key].verified:
        typer.echo("warning: price entry is unverified; results cannot be published.")

    if dry_run:
        return
    typer.echo("Execution is not implemented yet (see docs/PLAN.md, week 1).", err=True)
    raise typer.Exit(code=2)


@app.command()
def report(
    runs: Annotated[Path, typer.Option(help="Directory of raw run records.")] = Path("runs"),
    out: Annotated[Path, typer.Option(help="Leaderboard output directory.")] = Path("site"),
) -> None:
    """Aggregate runs into cost per solved task with bootstrap CIs; build the leaderboard."""
    typer.echo("Reporting is not implemented yet (see docs/PLAN.md, week 2).", err=True)
    raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
