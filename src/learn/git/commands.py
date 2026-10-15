"""Git-like command dispatcher over model.Repo, now backed by real file content (PLAN.md section
4): a working tree you `edit`, `commit` to snapshot, and real 3-way merges (diff3.py) for merge,
rebase and cherry-pick alike - all three are "replay someone else's change against my current
content", so they share one `_apply_three_way` primitive. A genuine conflict leaves `<<<<<<<`
markers in the working tree; `resolve <path> ours|theirs|both` (or manual `edit`) fixes it, then
`merge --continue` / `rebase --continue` / `cherry-pick --continue` finishes the commit."""
import shlex

from . import diff3, model


class GitEngine:
    def __init__(self, seed_files: dict[str, list[str]] | None = None):
        self.repo = model.Repo(seed_files)
        self.working: dict[str, list[str]] = self.repo.files_at(self.repo.head)
        self.pending: dict | None = None  # {"kind","parents","message","chain"?}
        self.conflicts: set[str] = set()
        self._hunks: dict[str, diff3.FileMerge] = {}

    def run(self, line: str) -> str:
        parts = shlex.split(line)
        if not parts:
            return ""
        cmd, args = parts[0], parts[1:]
        handler = getattr(self, f"_cmd_{cmd.replace('-', '_')}", None)
        if handler is None:
            return f"git: '{cmd}' is not a command"
        self.repo.snapshot()
        try:
            return handler(args)
        except model.GitError as exc:
            self.repo.drop_snapshot()
            return f"error: {exc}"

    def undo(self) -> str:
        msg = self.repo.undo()
        self.working = self.repo.files_at(self.repo.head)
        self.pending, self.conflicts, self._hunks = None, set(), {}
        return msg

    # ---- ref resolution --------------------------------------------------
    def ref(self, name: str) -> str:
        if name == "HEAD":
            return self.repo.head
        if name.startswith("HEAD~"):
            cid = self.repo.head
            for _ in range(int(name[5:])):
                parents = self.repo.commits[cid].parents
                if not parents:
                    raise model.GitError(f"{name}: not enough history")
                cid = parents[0]
            return cid
        if name in self.repo.branches:
            return self.repo.branches[name]
        if name in self.repo.commits:
            return name
        raise model.GitError(f"unknown ref '{name}'")

    def where(self) -> str:
        return self.repo.head_branch or f"detached HEAD @ {self.repo.head_commit}"

    def _dirty(self) -> bool:
        return self.working != self.repo.files_at(self.repo.head)

    # ---- the shared 3-way primitive used by merge/rebase-step/cherry-pick -
    def _apply_three_way(self, base_files, ours_files, theirs_files, message, parents, pending_extra) -> str:
        merged: dict[str, list[str]] = {}
        hunks: dict[str, diff3.FileMerge] = {}
        conflicts: set[str] = set()
        for path in set(base_files) | set(ours_files) | set(theirs_files):
            fm = diff3.merge_file(base_files.get(path, []), ours_files.get(path, []), theirs_files.get(path, []))
            if fm.conflict:
                merged[path] = diff3.conflict_markers(fm, "ours", "theirs")
                hunks[path] = fm
                conflicts.add(path)
            else:
                merged[path] = fm.lines
        if conflicts:
            self.pending = {"parents": parents, "message": message, **pending_extra}
            self.conflicts = conflicts
            self._hunks = hunks
            self.working = merged
            cont = pending_extra["continue_cmd"]
            return f"CONFLICT in {', '.join(sorted(conflicts))} - resolve <path> ours|theirs|both, then {cont}"
        commit = self.repo.new_commit(parents, message, {p: tuple(ls) for p, ls in merged.items()})
        self.repo.set_head(commit.id)
        self.working = self.repo.files_at(commit.id)
        return f'created commit {commit.id} "{message}"'

    def _finalize_pending(self) -> model.Commit:
        if self.conflicts:
            raise model.GitError(f"unresolved: {', '.join(sorted(self.conflicts))}")
        commit = self.repo.new_commit(
            self.pending["parents"], self.pending["message"], {p: tuple(ls) for p, ls in self.working.items()}
        )
        self.repo.set_head(commit.id)
        self.working = self.repo.files_at(commit.id)
        return commit

    # ---- working tree -------------------------------------------------------
    def _cmd_edit(self, args: list[str]) -> str:
        path, sub = args[0], args[1]
        lines = self.working.setdefault(path, [])
        if sub == "set":
            lineno, text = int(args[2]), " ".join(args[3:])
            if not (1 <= lineno <= len(lines)):
                raise model.GitError(f"{path}: no line {lineno}")
            lines[lineno - 1] = text
        elif sub == "append":
            lines.append(" ".join(args[2:]))
        elif sub == "delete":
            lineno = int(args[2])
            if not (1 <= lineno <= len(lines)):
                raise model.GitError(f"{path}: no line {lineno}")
            del lines[lineno - 1]
        else:
            raise model.GitError(f"edit: unknown mode '{sub}' (use set/append/delete)")
        if path in self.conflicts and not any(
            ln.startswith(("<<<<<<<", "=======", ">>>>>>>")) for ln in self.working[path]
        ):
            self.conflicts.discard(path)
            return f"edited {path} - conflict markers gone, '{path}' resolved"
        return f"edited {path}"

    # ---- commands ---------------------------------------------------------
    def _cmd_commit(self, args: list[str]) -> str:
        message = "update"
        i = 0
        while i < len(args):
            if args[i] == "-m" and i + 1 < len(args):
                message = args[i + 1]
                i += 2
            else:
                i += 1
        commit = self.repo.new_commit([self.repo.head], message, {p: tuple(ls) for p, ls in self.working.items()})
        self.repo.set_head(commit.id)
        self.working = self.repo.files_at(commit.id)
        self.repo.reflog.append(f"commit: {commit.id} {message}")
        return f'created commit {commit.id} "{message}" on {self.where()}'

    def _cmd_branch(self, args: list[str]) -> str:
        if not args:
            return ", ".join(sorted(self.repo.branches)) or "(no branches)"
        if args[0] == "-d":
            name = args[1]
            if name == self.repo.head_branch:
                raise model.GitError("cannot delete the branch you are on")
            if name not in self.repo.branches:
                raise model.GitError(f"branch '{name}' not found")
            del self.repo.branches[name]
            return f"deleted branch {name}"
        name = args[0]
        self.repo.branches[name] = self.repo.head
        return f"created branch {name} at {self.repo.head}"

    def _cmd_switch(self, args: list[str]) -> str:
        if not args:
            raise model.GitError("switch needs a branch, commit, or -b <name>")
        if args[0] == "-b":
            name = args[1]
            self.repo.branches[name] = self.repo.head
            self.repo.head_branch, self.repo.head_commit = name, None
            return f"created and switched to branch {name}"
        if self._dirty():
            raise model.GitError("you have uncommitted edits - commit them first")
        target = args[0]
        if target in self.repo.branches:
            self.repo.head_branch, self.repo.head_commit = target, None
        else:
            cid = self.ref(target)
            self.repo.head_branch, self.repo.head_commit = None, cid
        self.working = self.repo.files_at(self.repo.head)
        return f"switched to {self.where()}"

    def _cmd_merge(self, args: list[str]) -> str:
        if args and args[0] == "--continue":
            if not self.pending:
                raise model.GitError("no merge in progress")
            commit = self._finalize_pending()
            self.pending = None
            return f"merge completed, created commit {commit.id}"
        if args and args[0] == "--abort":
            self.pending, self.conflicts, self._hunks = None, set(), {}
            self.working = self.repo.files_at(self.repo.head)
            return "merge aborted"
        if not args:
            raise model.GitError("merge needs a branch name")
        no_ff = "--no-ff" in args
        branch = next(a for a in args if not a.startswith("--"))
        if branch not in self.repo.branches:
            raise model.GitError(f"branch '{branch}' not found")
        ours, other = self.repo.head, self.repo.branches[branch]
        if ours == other:
            return "already up to date"
        base = self.repo.merge_base(ours, other)
        if base == ours and not no_ff:
            self.repo.set_head(other)
            self.working = self.repo.files_at(other)
            return f"fast-forwarded {self.where()} to {other}"
        return self._apply_three_way(
            self.repo.files_at(base), self.repo.files_at(ours), self.repo.files_at(other),
            f"merge {branch} into {self.where()}", [ours, other],
            {"continue_cmd": "merge --continue"},
        )

    def _cmd_resolve(self, args: list[str]) -> str:
        if not self.pending:
            raise model.GitError("no merge/rebase/cherry-pick in progress")
        path, choice = args[0], args[1]
        if path not in self.conflicts:
            raise model.GitError(f"'{path}' is not conflicted")
        fm = self._hunks[path]
        if choice == "ours":
            self.working[path] = fm.pre + fm.ours_hunk + fm.post
        elif choice == "theirs":
            self.working[path] = fm.pre + fm.theirs_hunk + fm.post
        elif choice == "both":
            self.working[path] = fm.pre + fm.ours_hunk + fm.theirs_hunk + fm.post
        else:
            raise model.GitError("resolve: choose ours, theirs, or both")
        self.conflicts.discard(path)
        return f"resolved '{path}' ({choice})"

    def _replay_rebase(self, chain: list[str], parent: str) -> str:
        parent_files = self.repo.files_at(parent)
        for idx, cid in enumerate(chain):
            old = self.repo.commits[cid]
            old_parent_files = self.repo.files_at(old.parents[0]) if old.parents else {}
            result = self._apply_three_way(
                old_parent_files, parent_files, self.repo.files_at(cid), old.message, [parent],
                {"continue_cmd": "rebase --continue", "chain": chain[idx + 1:]},
            )
            if self.pending:
                return result
            parent = self.repo.head
            parent_files = self.repo.files_at(parent)
        return f"rebase complete, new tip {parent}"

    def _cmd_rebase(self, args: list[str]) -> str:
        if args and args[0] == "--continue":
            if not self.pending or "chain" not in self.pending:
                raise model.GitError("no rebase in progress")
            rest = self.pending["chain"]
            commit = self._finalize_pending()
            self.pending = None
            if rest:
                return self._replay_rebase(rest, commit.id)
            return f"rebase complete, new tip {commit.id}"
        onto_tip = self.ref(args[0])
        base = self.repo.merge_base(self.repo.head, onto_tip)
        chain = self.repo.linear_chain(base, self.repo.head)
        if not chain:
            self.repo.set_head(onto_tip)
            self.working = self.repo.files_at(onto_tip)
            return f"nothing to replay, {self.where()} now points at {onto_tip}"
        return self._replay_rebase(chain, onto_tip)

    def _cmd_cherry_pick(self, args: list[str]) -> str:
        if args and args[0] == "--continue":
            if not self.pending:
                raise model.GitError("no cherry-pick in progress")
            commit = self._finalize_pending()
            self.pending = None
            return f"cherry-picked as {commit.id}"
        cid = self.ref(args[0])
        old = self.repo.commits[cid]
        old_parent_files = self.repo.files_at(old.parents[0]) if old.parents else {}
        return self._apply_three_way(
            old_parent_files, self.repo.files_at(self.repo.head), self.repo.files_at(cid),
            old.message, [self.repo.head], {"continue_cmd": "cherry-pick --continue"},
        )

    def _cmd_reset(self, args: list[str]) -> str:
        mode = "--mixed"
        rest = args
        if args and args[0].startswith("--"):
            mode, rest = args[0], args[1:]
        cid = self.ref(rest[0]) if rest else self.repo.head
        self.repo.set_head(cid)
        if mode != "--soft":
            self.working = self.repo.files_at(cid)
        self.repo.reflog.append(f"reset {mode}: {self.where()} -> {cid}")
        return f"reset ({mode}) {self.where()} to {cid}"

    def _cmd_revert(self, args: list[str]) -> str:
        cid = self.ref(args[0])
        old = self.repo.commits[cid]
        old_parent_files = self.repo.files_at(old.parents[0]) if old.parents else {}
        # reverting = replaying the INVERSE of that commit's change onto HEAD: base=old's own
        # content, "ours"=current HEAD, "theirs"=the pre-commit content (undoing old's edit)
        return self._apply_three_way(
            {p: list(ls) for p, ls in old.files.items()}, self.repo.files_at(self.repo.head), old_parent_files,
            f"revert {old.message}", [self.repo.head], {"continue_cmd": "revert --continue"},
        )

    def _cmd_tag(self, args: list[str]) -> str:
        name = args[0]
        self.repo.tags[name] = self.repo.head
        return f"tagged {self.repo.head} as '{name}'"

    def _cmd_reflog(self, args: list[str]) -> str:
        return "\n".join(self.repo.reflog[-10:])

    def _cmd_log(self, args: list[str]) -> str:
        return f"HEAD -> {self.where()} @ {self.repo.head}"
