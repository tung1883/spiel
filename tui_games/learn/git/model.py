"""In-memory git simulation: commits, branches, tags, HEAD. No real git/subprocess involved.

A commit snapshots the FULL content of every tracked file as a tuple of lines (small repos, small
files - a few dozen commits and a handful of 3-8 line files is all this game needs, so snapshotting
is simpler and just as correct as diff-chaining). Commit ids are a deterministic hash of (parents,
message, file content, a repo-wide counter), so replaying the same command script on a fresh Repo
always reproduces the same ids - used by levels.py to compute solution/ref strings ahead of time.
"""
import hashlib
from collections import deque
from dataclasses import dataclass, field


class GitError(Exception):
    pass


@dataclass
class Commit:
    id: str
    parents: list[str]
    message: str
    files: dict[str, tuple[str, ...]] = field(default_factory=dict)


class Repo:
    def __init__(self, seed_files: dict[str, list[str]] | None = None):
        self.commits: dict[str, Commit] = {}
        self.branches: dict[str, str] = {}
        self.tags: dict[str, str] = {}
        self.head_branch: str | None = "main"
        self.head_commit: str | None = None  # set when HEAD is detached
        self.reflog: list[str] = []
        self._counter = 0
        self._undo_stack: list[tuple] = []
        seed = {p: tuple(lines) for p, lines in (seed_files or {}).items()}
        root = self.new_commit([], "root", seed)
        self.branches["main"] = root.id
        self.reflog.append(f"commit (root): {root.id}")

    # ---- ids / commits -------------------------------------------------
    def new_commit(self, parents: list[str], message: str, files: dict[str, tuple[str, ...]]) -> Commit:
        self._counter += 1
        fingerprint = sorted((p, lines) for p, lines in files.items())
        digest = hashlib.sha1(f"{parents}|{message}|{fingerprint}|{self._counter}".encode()).hexdigest()
        commit = Commit(digest[:7], list(parents), message, dict(files))
        self.commits[commit.id] = commit
        return commit

    @property
    def head(self) -> str:
        return self.head_commit if self.head_branch is None else self.branches[self.head_branch]

    def set_head(self, commit_id: str) -> None:
        if self.head_branch is None:
            self.head_commit = commit_id
        else:
            self.branches[self.head_branch] = commit_id

    def files_at(self, commit_id: str) -> dict[str, list[str]]:
        return {p: list(lines) for p, lines in self.commits[commit_id].files.items()}

    # ---- graph queries ---------------------------------------------------
    def ancestors(self, commit_id: str) -> set[str]:
        seen, stack = set(), [commit_id]
        while stack:
            cid = stack.pop()
            if cid in seen:
                continue
            seen.add(cid)
            stack.extend(self.commits[cid].parents)
        return seen

    def is_ancestor(self, maybe_ancestor: str, commit_id: str) -> bool:
        return maybe_ancestor in self.ancestors(commit_id)

    def merge_base(self, a: str, b: str) -> str | None:
        anc_a = self.ancestors(a)
        seen, queue = set(), deque([b])
        while queue:
            cid = queue.popleft()
            if cid in anc_a:
                return cid
            if cid in seen:
                continue
            seen.add(cid)
            queue.extend(self.commits[cid].parents)
        return None

    def linear_chain(self, base: str, tip: str) -> list[str]:
        """Commits from (exclusive) base to tip along first-parent, oldest first.
        Reduced-scope rebase only replays a single unbranched line - good enough for this level set.
        """
        chain = []
        cid = tip
        while cid != base:
            chain.append(cid)
            parents = self.commits[cid].parents
            if not parents:
                break
            cid = parents[0]
        return list(reversed(chain))

    # ---- undo -------------------------------------------------------------
    def snapshot(self) -> None:
        self._undo_stack.append((
            dict(self.commits), dict(self.branches), dict(self.tags),
            self.head_branch, self.head_commit, list(self.reflog), self._counter,
        ))

    def drop_snapshot(self) -> None:
        if self._undo_stack:
            self._undo_stack.pop()

    def undo(self) -> str:
        if not self._undo_stack:
            return "nothing to undo"
        (self.commits, self.branches, self.tags, self.head_branch,
         self.head_commit, self.reflog, self._counter) = self._undo_stack.pop()
        return "undone"
