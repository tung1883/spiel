"""Rank ladder and region list for the Learn to Code hub. Lore text stays short (terse mentors)."""

RANKS: list[tuple[int, str]] = [
    (0, "Novice"),
    (100, "Apprentice"),
    (300, "Journeyman"),
    (700, "Adept"),
    (1500, "Archmage"),
]


def rank_for(xp: int) -> str:
    title = RANKS[0][1]
    for threshold, name in RANKS:
        if xp >= threshold:
            title = name
    return title


# (id, title, blurb) - one row per region in the hub, in PLAN.md's intended order.
REGIONS: list[tuple[str, str, str]] = [
    ("regex", "Pattern Marsh", "the witch golfs a pattern"),
    ("git", "Branch Forest", "the cartographer maps a graph"),
    ("shell", "Terminal Caverns", "the blacksmith forges a pipeline"),
    ("sql", "Archive of Queries", "the archivist follows a clue"),
    ("bughunt", "Bug Swamp", "the exterminator hunts a bug"),
    ("codetype", "Typing Forge", "the bard races the clock"),
]
