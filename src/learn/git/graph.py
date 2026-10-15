"""Render the reachable commit graph as plain monospace text, oldest first, with branch/tag/HEAD
labels on their tips. Reduced scope: a generation-ordered list rather than a full lane/column
Sugiyama layout (PLAN.md section 4 calls for lanes; this reads fine for the small graphs these
levels produce - revisit if a later pass wants the full layout)."""
from .commands import GitEngine


def render(engine: GitEngine) -> str:
    repo = engine.repo
    heads = set(repo.branches.values()) | set(repo.tags.values()) | {repo.head}
    all_ids: set[str] = set()
    for h in heads:
        all_ids |= repo.ancestors(h)
    if not all_ids:
        return "(empty)"

    depth: dict[str, int] = {}

    def gen(cid: str) -> int:
        if cid not in depth:
            parents = repo.commits[cid].parents
            depth[cid] = 0 if not parents else 1 + max(gen(p) for p in parents)
        return depth[cid]

    for cid in all_ids:
        gen(cid)

    lines = []
    for cid in sorted(all_ids, key=lambda c: (gen(c), c)):
        labels = [name for name, bid in repo.branches.items() if bid == cid]
        labels += [f"tag:{name}" for name, tid in repo.tags.items() if tid == cid]
        if cid == repo.head:
            labels.append("HEAD" if repo.head_branch is None else f"HEAD->{repo.head_branch}")
        marker = "@" if cid == repo.head else "o"
        suffix = f"  ({', '.join(labels)})" if labels else ""
        lines.append(f"{marker} {cid}  {repo.commits[cid].message}{suffix}")
    return "\n".join(lines)
