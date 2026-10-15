"""Git Trivia: a quick multiple-choice quiz, a lighter companion to Branch Forest's hands-on
levels (inspired by the format of guess-the-answer git quiz games - all questions/answers here are
original, written for this repo). A round is 10 questions drawn at random from the bank below."""
import random
from dataclasses import dataclass


@dataclass
class Question:
    prompt: str
    options: list[str]
    correct: int  # index into options
    explain: str


BANK: list[Question] = [
    Question("You committed, then realised you forgot one file. Which command fixes the last "
             "commit instead of making a new one?", ["git commit --amend", "git commit -f", "git recommit",
             "git commit --redo"], 0, "--amend replaces the tip commit with a new one."),
    Question("Which command moves a branch's commits onto a new base, rewriting their ids?",
             ["git rebase", "git merge", "git graft", "git transplant"], 0,
             "rebase replays commits one by one onto the target; merge instead creates a new commit."),
    Question("You want your branch's history to stay a single straight line when it joins main. "
             "Which merge flag forces that (when a fast-forward is possible)?",
             ["--no-ff", "--ff-only", "--squash", "--linear"], 1,
             "--ff-only merges only if it can be a fast-forward, refusing otherwise."),
    Question("Which command undoes a commit by making a new commit that reverses it, instead of "
             "removing it from history?", ["git revert", "git reset", "git undo", "git uncommit"], 0,
             "revert is the safe undo for shared history; reset rewrites it."),
    Question("`git reset --hard HEAD~1` on a branch nobody else has pulled - what happens to the "
             "undone commit's working-tree changes?", ["Discarded", "Staged", "Stashed automatically",
             "Kept as untracked files"], 0, "--hard resets the index AND the working tree to match."),
    Question("You're mid-merge with conflict markers in a file. After editing the file by hand, "
             "what's the next step before finishing the merge?", ["git add <file>", "git merge --accept",
             "git resolve", "nothing - commit directly"], 0, "add marks the conflict as resolved."),
    Question("Which command lets you grab one specific commit from another branch without merging "
             "the whole branch?", ["git cherry-pick", "git graft", "git pluck", "git take"], 0,
             "cherry-pick replays a single commit onto the current branch."),
    Question("You deleted a branch by mistake, but it had unmerged commits. Where can you find "
             "its last commit id to recover it?", ["git reflog", "git log --lost", "git fsck --branches",
             "it's gone for good"], 0, "reflog tracks where HEAD and branches have pointed, even after deletion."),
    Question("What's the main practical difference between `git merge` and `git rebase` for a "
             "feature branch's history?", ["merge keeps the branch's own commits and ids, adding a merge "
             "commit; rebase replays and changes their ids", "merge is read-only, rebase writes",
             "they produce identical history", "rebase only works on remote branches"], 0,
             "That id change is why you never rebase commits others have already pulled."),
    Question("Which flag on `push` lets you overwrite a remote branch, but refuses if someone else "
             "pushed to it since you last fetched?", ["--force-with-lease", "--force", "--safe-force",
             "--overwrite"], 0, "--force-with-lease checks the remote hasn't moved first; plain --force doesn't."),
    Question("You want to save your uncommitted changes temporarily to switch branches, then bring "
             "them back later. What do you use?", ["git stash", "git shelve", "git pocket", "git park"],
             0, "stash pushes a snapshot onto a stack; `stash pop` brings the latest one back."),
    Question("A commit on `main` has a bug. Which approach finds the exact commit that introduced "
             "it by testing midpoints of a commit range?", ["git bisect", "git blame --range", "git search",
             "git trace"], 0, "bisect binary-searches history between a known-good and known-bad commit."),
    Question("What does `HEAD` point to right after `git checkout <commit-hash>` (not a branch "
             "name)?", ["The commit directly - you're in \"detached HEAD\" state", "The branch that commit "
             "is on", "Nothing, it errors", "The previous branch"], 0,
             "Committing here moves HEAD but not any branch, so those commits are easy to lose track of."),
    Question("Which command shows you exactly which commit last changed each line of a file?",
             ["git blame", "git log --lines", "git trace <file>", "git whodid"], 0,
             "blame annotates each line with the commit (and author) that last touched it."),
    Question("You squashed 5 commits into 1 during an interactive rebase. What happens to the 4 "
             "extra commit ids?", ["They stop being reachable from any branch, but still exist until "
             "garbage-collected", "They're deleted immediately and unrecoverable", "They become tags",
             "Nothing changes - squash is just a label"], 0,
             "That's also how reflog can rescue them for a while after a rebase goes wrong."),
]


def new_round(n: int = 10) -> list[Question]:
    return random.sample(BANK, min(n, len(BANK)))
