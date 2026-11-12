"""Every task's hidden check must fail on the start state and pass on the solution."""

from pathlib import Path

import pytest

from tokentrial.tasks import load_tasks, materialize, run_check

TASKS = load_tasks(Path(__file__).parent.parent / "tasks")


def test_at_least_one_task():
    assert TASKS


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_check_fails_on_start_state(task, tmp_path):
    ws = materialize(task, tmp_path / "ws")
    assert not run_check(task, ws)


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_check_passes_on_solution(task, tmp_path):
    ws = materialize(task, tmp_path / "ws", with_solution=True)
    assert run_check(task, ws)


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_check_ignores_edited_tests(task, tmp_path):
    ws = materialize(task, tmp_path / "ws")
    for f in (ws / "tests").glob("test_*.py"):
        f.write_text("")  # an agent "fixing" the build by deleting tests
    assert not run_check(task, ws)
