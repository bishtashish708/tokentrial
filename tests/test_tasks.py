"""Every task's hidden check must fail on the start state and pass on the solution."""

from pathlib import Path

import pytest

from tokentrial.tasks import load_tasks, materialize, run_check

TASKS = load_tasks(Path(__file__).parent.parent / "tasks")


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_check_fails_on_start_state(task, tmp_path):
    ws = materialize(task, tmp_path / "ws")
    assert not run_check(task, ws)


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_check_passes_on_solution(task, tmp_path):
    ws = materialize(task, tmp_path / "ws", with_solution=True)
    assert run_check(task, ws)


TEST_TASKS = [t for t in TASKS if (t.dir / "hidden_tests").is_dir()]


@pytest.mark.parametrize("task", TEST_TASKS, ids=lambda t: t.id)
def test_check_ignores_edited_tests(task, tmp_path):
    ws = materialize(task, tmp_path / "ws")
    hidden = {p.name for p in (task.dir / "hidden_tests").iterdir()}
    emptied = [f for f in ws.rglob("*") if f.name in hidden]
    assert emptied, "visible copies of the hidden tests should exist in the repo"
    for f in emptied:
        f.write_text("")  # an agent "fixing" the build by deleting the tests
    assert not run_check(task, ws)


def test_task_set():
    assert len(TASKS) == 10
    assert {t.id for t in TASKS if t.history} == {"git-regression-hunt", "git-config-forensics"}
