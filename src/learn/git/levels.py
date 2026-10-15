"""Branch Forest levels (PLAN.md section 4), 18 levels over real file content: every merge,
rebase, cherry-pick and revert runs a genuine line-based 3-way merge (diff3.py) against real
`{path: [lines]}` snapshots, so a "conflict" is two edits to the same line of a real file, not an
abstract tag overlap - resolved with `resolve <path> ours|theirs|both` or by hand-editing the
`<<<<<<<` markers with `edit`. All scenario text/content is original.

Commit ids are deterministic (model.Repo.new_commit), so `_sim` below replays a level's own setup
script once at import time to compute the exact ids a solution needs to reference (e.g. the commit
a revert should target) - re-running the same script at play time reproduces the same ids.
"""
from dataclasses import dataclass, field
from typing import Callable

from .commands import GitEngine


@dataclass
class Level:
    title: str
    teach: str
    goal: str
    seed: dict[str, list[str]]
    start: list[str]
    check: Callable[[GitEngine], bool]
    par: int
    solution: list[str]
    hints: list[str] = field(default_factory=list)


class LevelRun:
    """One attempt at a Level."""

    def __init__(self, level: Level):
        self.level = level
        self.engine = GitEngine(level.seed)
        for line in level.start:
            self.engine.run(line)
        self.count = 0
        self.log: list[str] = []
        self.done = level.check(self.engine)

    def run(self, line: str) -> str:
        if self.done:
            return ""
        msg = self.engine.run(line)
        self.count += 1
        self.log.append(f"$ {line}\n  {msg}")
        if self.level.check(self.engine):
            self.done = True
        return msg

    def undo(self) -> str:
        msg = self.engine.undo()
        self.count = max(0, self.count - 1)
        return msg


def solve(level: Level) -> LevelRun:
    run = LevelRun(level)
    for line in level.solution:
        run.run(line)
    return run


def _sim(seed: dict[str, list[str]], start: list[str]) -> GitEngine:
    engine = GitEngine(seed)
    for line in start:
        engine.run(line)
    return engine


_root_engine = GitEngine({"notes.txt": ["base"]})
_ROOT_ID = _root_engine.repo.branches["main"]

_sim_lost = _sim({"notes.txt": []}, [
    'edit notes.txt append "good work"', 'commit -m "good work"',
    'edit notes.txt append "more good work"', 'commit -m "more good work"',
])
_LOST_ID = _sim_lost.repo.branches["main"]

_sim_v1 = _sim({"notes.txt": ["base"]}, ['edit notes.txt append "v1"', 'commit -m v1'])
_V1_ID = _sim_v1.repo.branches["main"]

LEVELS: list[Level] = [
    Level(
        "First branch", "commit saves work on HEAD; switch -b makes and moves to a new branch.",
        "put one commit on a new branch 'feature' ahead of main.",
        {"notes.txt": ["base"]}, [],
        lambda e: "feature" in e.repo.branches and e.repo.branches["feature"] != e.repo.branches["main"]
        and e.repo.is_ancestor(e.repo.branches["main"], e.repo.branches["feature"]),
        3, ["switch -b feature", 'edit notes.txt append "feature work"', 'commit -m "add feature work"'],
    ),
    Level(
        "Fast-forward", "merge <branch> moves your branch forward when there is no divergence.",
        "merge feature into main.",
        {"notes.txt": ["base"]},
        ["switch -b feature", 'edit notes.txt append "header"', 'commit -m "add header"', "switch main"],
        lambda e: e.repo.branches["main"] == e.repo.branches["feature"],
        1, ["merge feature"],
    ),
    Level(
        "Edit and commit", "edit <path> set/append/delete changes your working tree; commit snapshots it.",
        "add a third line to notes.txt and commit it.",
        {"notes.txt": ["first line", "second line"]}, [],
        lambda e: e.repo.commits[e.repo.head].files.get("notes.txt") == ("first line", "second line", "third line"),
        2, ['edit notes.txt append "third line"', 'commit -m "add third line"'],
    ),
    Level(
        "A real merge", "when two branches change different lines of the same file, merge combines both for real.",
        "feature changed the greeting, main changed the return value - merge them.",
        {"app.py": ["def greet():", "    pass", "    return True"]},
        ["switch -b feature"],
        lambda e: e.working.get("app.py") == ["def greet():", "    print('hi')", "    return False"],
        6, ['edit app.py set 2 "    print(\'hi\')"', 'commit -m "feature: greet prints"', "switch main",
            'edit app.py set 3 "    return False"', 'commit -m "main: fix return value"', "merge feature"],
    ),
    Level(
        "Conflict!", "two branches editing the SAME line really do conflict. resolve <path> ours|theirs|both.",
        "merge feature into main, keeping BOTH port lines.",
        {"config.py": ["DEBUG = False", "PORT = 8000"]},
        ["switch -b feature"],
        lambda e: e.pending is None and "PORT = 8080" in e.working.get("config.py", [])
        and "PORT = 9000" in e.working.get("config.py", []),
        8, ['edit config.py set 2 "PORT = 9000"', 'commit -m "feature: change port"', "switch main",
            'edit config.py set 2 "PORT = 8080"', 'commit -m "main: change port too"', "merge feature",
            "resolve config.py both", "merge --continue"],
    ),
    Level(
        "Conflict, resolve by hand", "you don't need `resolve` - edit the <<<<<<< markers directly, then commit.",
        "merge feature into main, then hand-edit config.py down to just the right port (drop the markers and DEBUG).",
        {"config.py": ["DEBUG = False", "PORT = 8000"]},
        ["switch -b feature"],
        lambda e: e.pending is None and e.working.get("config.py") == ["DEBUG = False", "PORT = 9999"],
        12, ['edit config.py set 2 "PORT = 9000"', 'commit -m "feature: change port"', "switch main",
             'edit config.py set 2 "PORT = 8080"', 'commit -m "main: change port too"', "merge feature",
             'edit config.py set 3 "PORT = 9999"', "edit config.py delete 2", "edit config.py delete 3",
             "edit config.py delete 3", "edit config.py delete 3", "merge --continue"],
        hints=["After the conflict, config.py has 6 lines with <<<<<<<, =======, >>>>>>> in it - "
               "set the line you want to keep, then delete the other five."],
    ),
    Level(
        "Rebase for a clean line", "rebase replays your commits onto another branch's tip - one history, no merge bubble.",
        "rebase feature onto main so main's hotfix becomes an ancestor of feature.",
        {"notes.txt": ["base"]},
        ["switch -b feature", 'edit notes.txt append "feature work"', 'commit -m "feature step"', "switch main",
         'edit notes.txt append "hotfix"', 'commit -m hotfix', "switch feature"],
        lambda e: e.repo.is_ancestor(e.repo.branches["main"], e.repo.branches["feature"]),
        1, ["rebase main"],
    ),
    Level(
        "Rebase, with a conflict", "a rebase can conflict too, commit by commit - resolve, then rebase --continue.",
        "rebase feature onto main, keeping main's port number.",
        {"config.py": ["PORT = 8000"]},
        ["switch -b feature", 'edit config.py set 1 "PORT = 9000"', 'commit -m "feature: change port"',
         "switch main", 'edit config.py set 1 "PORT = 8080"', 'commit -m "main: change port too"', "switch feature"],
        lambda e: e.working.get("config.py") == ["PORT = 8080"] and e.repo.is_ancestor(e.repo.branches["main"], e.repo.head),
        3, ["rebase main", "resolve config.py ours", "rebase --continue"],
    ),
    Level(
        "Cherry-pick the fix", "cherry-pick <commit> copies one commit onto HEAD without merging the whole branch.",
        "bring just the urgent fix onto main, then clean up the feature branch.",
        {"notes.txt": ["base"]},
        ["switch -b feature", 'edit notes.txt set 1 "feature change"', 'commit -m "urgent fix"', "switch main"],
        lambda e: e.working.get("notes.txt") == ["feature change"]
        and e.repo.commits[e.repo.head].message == "urgent fix" and "feature" not in e.repo.branches,
        2, ["cherry-pick feature", "branch -d feature"],
    ),
    Level(
        "Cherry-pick, with a conflict", "cherry-pick is a 3-way merge too - it can conflict just like a real merge.",
        "cherry-pick the urgent fix onto main, keeping main's own port number.",
        {"config.py": ["PORT = 8000"]},
        ["switch -b feature", 'edit config.py set 1 "PORT = 9000"', 'commit -m "urgent fix"', "switch main",
         'edit config.py set 1 "PORT = 7000"', 'commit -m "main changed it too"'],
        lambda e: e.pending is None and e.working.get("config.py") == ["PORT = 7000"]
        and e.repo.commits[e.repo.head].message == "urgent fix",
        3, ["cherry-pick feature", "resolve config.py ours", "cherry-pick --continue"],
    ),
    Level(
        "Keep it, just undo it", "revert makes a NEW commit that undoes an old one - history keeps the mistake visible.",
        "revert the buggy commit at HEAD.",
        {"notes.txt": ["good line"]},
        ['edit notes.txt append "buggy line"', 'commit -m "v2 - buggy"'],
        lambda e: e.working.get("notes.txt") == ["good line"] and e.repo.commits[e.repo.head].message.startswith("revert"),
        1, ["revert HEAD"],
    ),
    Level(
        "Reflog rescue", "reset --hard can lose a branch's only pointer to a commit, but the commit survives until overwritten.",
        f"main lost its tip after a bad reset; recover it (the lost commit is {_LOST_ID}).",
        {"notes.txt": []},
        ['edit notes.txt append "good work"', 'commit -m "good work"',
         'edit notes.txt append "more good work"', 'commit -m "more good work"', "reset --hard HEAD~1"],
        lambda e, lost=_LOST_ID: e.repo.branches["main"] == lost,
        1, [f"reset --hard {_LOST_ID}"],
    ),
    Level(
        "Squash the WIP commits", "reset --soft moves your branch pointer back but keeps the work - commit again to squash.",
        f"squash the two WIP commits into one, parented on the root ({_ROOT_ID}).",
        {"notes.txt": ["base"]},
        ['edit notes.txt append "wip part 1"', 'commit -m "wip part 1"',
         'edit notes.txt append "wip part 2"', 'commit -m "wip part 2"'],
        lambda e, root=_ROOT_ID: e.repo.commits[e.repo.head].parents == [root]
        and e.working.get("notes.txt") == ["base", "wip part 1", "wip part 2"],
        2, [f"reset --soft {_ROOT_ID}", 'commit -m "add feature (squashed)"'],
    ),
    Level(
        "Detached HEAD", "switch <commit id> moves HEAD to a commit directly, off any branch - handy for a quick look.",
        f"check out the old v1 commit ({_V1_ID}) directly.",
        {"notes.txt": ["base"]},
        ['edit notes.txt append "v1"', 'commit -m v1', 'edit notes.txt append "v2"', 'commit -m v2'],
        lambda e, v1=_V1_ID: e.repo.head_branch is None and e.repo.head_commit == v1,
        1, [f"switch {_V1_ID}"],
    ),
    Level(
        "Clean up a stale branch", "branch -d removes a branch pointer; its commits stay if another ref still reaches them.",
        "delete the old-feature branch.",
        {"notes.txt": []},
        ["switch -b old-feature", 'commit -m abandoned', "switch main"],
        lambda e: "old-feature" not in e.repo.branches,
        1, ["branch -d old-feature"],
    ),
    Level(
        "Tag a release", "tag <name> marks the current commit by name, forever (branches move, tags don't).",
        "tag the current commit v1.0.",
        {"notes.txt": []}, ['commit -m "release work"'],
        lambda e: e.repo.tags.get("v1.0") == e.repo.head,
        1, ["tag v1.0"],
    ),
    Level(
        "Merge --no-ff", "--no-ff forces a merge commit even when a fast-forward was possible, keeping the branch's shape in history.",
        "merge feature into main with --no-ff.",
        {"notes.txt": []},
        ["switch -b feature", 'edit notes.txt append "small tweak"', 'commit -m "small tweak"', "switch main"],
        lambda e: len(e.repo.commits[e.repo.head].parents) == 2,
        1, ["merge feature --no-ff"],
    ),
    Level(
        "The incident (boss)",
        "a messy merge plus a leaked secret. Resolve the merge keeping main's setting, then scrub the secret with a plain commit.",
        "after the merge, config.py keeps main's DEBUG line and secrets.txt is scrubbed back to '(empty)'.",
        {"config.py": ["DEBUG = False"], "secrets.txt": ["(empty)"]},
        ["switch -b feature", 'edit secrets.txt set 1 "API_KEY=sk-leaked-12345"', 'commit -m "oops: committed a secret"',
         'edit config.py set 1 "DEBUG = True"', 'commit -m "feature: enable debug"', "switch main",
         'edit config.py set 1 "DEBUG = False  # prod"', 'commit -m "main: keep debug off in prod"', "merge feature"],
        lambda e: e.pending is None and e.repo.commits[e.repo.head].message == "scrub leaked secret"
        and e.working.get("secrets.txt") == ["(empty)"] and e.working.get("config.py") == ["DEBUG = False  # prod"],
        4, ["resolve config.py ours", "merge --continue", 'edit secrets.txt set 1 "(empty)"', 'commit -m "scrub leaked secret"'],
    ),
]
