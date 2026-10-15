import pytest

from src.learn.shell.levels import MISSIONS, MissionRun


@pytest.mark.parametrize("i", range(len(MISSIONS)))
def test_not_solved_at_start(i):
    assert not MissionRun(MISSIONS[i]).done


@pytest.mark.parametrize("i", range(len(MISSIONS)))
def test_reference_solution_completes_mission(i):
    m = MISSIONS[i]
    run = MissionRun(m)
    for line in m.solution:
        run.run(line)
    assert run.done, (m.id, run.history)
    assert run.commands_used == len(m.solution)
