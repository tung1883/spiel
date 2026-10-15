"""Content for Archive of Queries: three case files (one per seeded world in seed.py) and 24
drills. Every reference_sql/answer/verify_sql is checked by tests/learn/sql/test_levels.py against
the real seeded db - nothing here is a guess.
"""
from dataclasses import dataclass, field


@dataclass
class CaseStep:
    prompt: str
    reference_sql: str
    answer: str  # compared case-insensitively, stripped


@dataclass
class Case:
    id: str
    title: str
    world: str  # one of seed.WORLDS
    intro: str
    steps: list[CaseStep]


@dataclass
class Drill:
    id: str
    title: str
    teach: str
    prompt: str
    reference_sql: str
    ordered: bool
    hints: list[str]
    world: str = "company"
    writable: bool = False  # True = runs on a throwaway connect_writable() copy
    verify_sql: str = ""  # for writable drills: the SELECT that proves the change landed


CASES: list[Case] = [
    Case(
        id="company",
        title="The Vanishing Release",
        world="company",
        intro=(
            "atlas shipped release 2.0 with a blank changelog. The team filed an issue; someone in "
            "the comments admits to it. Follow the thread from issue to confession to the guilty commit."
        ),
        steps=[
            CaseStep(
                "Find the open issue in the 'atlas' repo (id 1) whose title mentions the changelog. "
                "Submit the issue's id.",
                "SELECT id FROM issues WHERE repo_id=1 AND title LIKE '%changelog%'",
                "1",
            ),
            CaseStep(
                "Who opened issue 1? Submit their username.",
                "SELECT u.username FROM issues i JOIN users u ON u.id=i.opened_by WHERE i.id=1",
                "carol",
            ),
            CaseStep(
                "Read the comments on issue 1 - whose comment admits to the mistake? Submit their username.",
                "SELECT u.username FROM comments c JOIN users u ON u.id=c.author_id "
                "WHERE c.issue_id=1 AND c.body LIKE '%mistake%'",
                "dave",
            ),
            CaseStep(
                "Find the commit in repo 1 authored by dave with a large negative lines_changed "
                "(a deletion). Submit the commit's id.",
                "SELECT id FROM commits WHERE repo_id=1 "
                "AND author_id=(SELECT id FROM users WHERE username='dave') AND lines_changed<0",
                "5",
            ),
            CaseStep(
                "What does that commit's message say? Submit the exact message.",
                "SELECT message FROM commits WHERE id=5",
                "remove old changelog",
            ),
            CaseStep(
                "Final accusation: who broke the release? Submit their username.",
                "SELECT username FROM users WHERE id=5",
                "dave",
            ),
        ],
    ),
    Case(
        id="shop",
        title="The Overcharged Order",
        world="shop",
        intro=(
            "dana opened a support ticket swearing she was double-billed. The shop's order_items "
            "table holds the proof, if you know where to look - trace the ticket to the exact "
            "duplicate line, then to who should be refunded."
        ),
        steps=[
            CaseStep(
                "Find the open ticket whose subject mentions being double charged. Submit its order_id.",
                "SELECT order_id FROM tickets WHERE status='open' AND subject LIKE '%double charged%'",
                "4",
            ),
            CaseStep(
                "Look at that order's line items - which product_id appears twice with the exact same "
                "quantity and price (a literal duplicate row)? Submit the product_id.",
                "SELECT product_id FROM order_items WHERE order_id=4 "
                "GROUP BY product_id, quantity, unit_price HAVING COUNT(*)>1",
                "7",
            ),
            CaseStep(
                "What's that product's name?",
                "SELECT name FROM products WHERE id=7",
                "bluetooth speaker",
            ),
            CaseStep(
                "Which supplier makes it? Submit the supplier's name.",
                "SELECT s.name FROM products p JOIN suppliers s ON s.id=p.supplier_id WHERE p.id=7",
                "brightline",
            ),
            CaseStep(
                "Who placed the order? There are two similarly-named customers - submit the exact "
                "username (case matters) of the one who actually placed order 4.",
                "SELECT name FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.id=4",
                "dana",
            ),
            CaseStep(
                "How many whole dollars was the duplicate line item worth (quantity * unit_price, "
                "no cents)? Submit the number.",
                "SELECT CAST(quantity*unit_price AS INTEGER) FROM order_items WHERE id=6",
                "45",
            ),
            CaseStep(
                "Final accusation: submit the username of the customer who should be refunded.",
                "SELECT name FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.id=4",
                "dana",
            ),
        ],
    ),
    Case(
        id="stream",
        title="The Royalty Mismatch",
        world="stream",
        intro=(
            "A royalty audit on the streaming ledger starts with duplicate artist entries - the "
            "same act, split across two ids, each one undercounting the other's plays."
        ),
        steps=[
            CaseStep(
                "Find the two artist rows that share the same name (case-insensitive) but have "
                "different ids. Submit the smaller id.",
                "SELECT MIN(a1.id) FROM artists a1 JOIN artists a2 "
                "ON LOWER(a1.name)=LOWER(a2.name) AND a1.id<>a2.id",
                "1",
            ),
            CaseStep(
                "What's that artist's name?",
                "SELECT name FROM artists WHERE id=1",
                "nova wave",
            ),
            CaseStep(
                "Submit the OTHER id in that duplicate pair.",
                "SELECT a2.id FROM artists a1 JOIN artists a2 "
                "ON LOWER(a1.name)=LOWER(a2.name) AND a1.id<>a2.id WHERE a1.id=1",
                "2",
            ),
            CaseStep(
                "A full play counts as ms_played >= 30000. Submit the combined number of full plays "
                "across both ids.",
                "SELECT COUNT(*) FROM plays p JOIN tracks t ON t.id=p.track_id "
                "WHERE p.ms_played>=30000 AND t.artist_id IN (1,2)",
                "6",
            ),
            CaseStep(
                "Which track (either id) was played the longest in a single sitting? Submit its title.",
                "SELECT t.title FROM plays p JOIN tracks t ON t.id=p.track_id "
                "WHERE t.artist_id IN (1,2) ORDER BY p.ms_played DESC LIMIT 1",
                "Afterglow (Live)",
            ),
            CaseStep(
                "Final accusation: by how many full plays was 'nova wave' undercounted by the split? "
                "Submit the number.",
                "SELECT COUNT(*) FROM plays p JOIN tracks t ON t.id=p.track_id "
                "WHERE p.ms_played>=30000 AND t.artist_id=2",
                "2",
            ),
        ],
    ),
]

DRILLS: list[Drill] = [
    Drill(
        "select-where", "Admins only", "SELECT ... WHERE",
        "List the username of every admin.",
        "SELECT username FROM users WHERE is_admin=1", False,
        ["is_admin is 0/1, not a word"],
    ),
    Drill(
        "order-limit", "Top repos", "ORDER BY ... LIMIT",
        "List the 3 repos with the most stars, most first.",
        "SELECT name FROM repos ORDER BY stars DESC LIMIT 3", True,
        ["DESC for most-first", "LIMIT 3"],
    ),
    Drill(
        "distinct", "Double-posted", "DISTINCT",
        "Someone double-posted a comment on issue 1. List the distinct comment bodies on issue 1.",
        "SELECT DISTINCT body FROM comments WHERE issue_id=1", False,
        ["without DISTINCT you'll see the same text twice"],
    ),
    Drill(
        "group-count", "Busiest committers", "GROUP BY, COUNT",
        "For each author, show their username and how many commits they've made, busiest first "
        "(tie-break alphabetically).",
        "SELECT u.username, COUNT(*) c FROM commits cm JOIN users u ON u.id=cm.author_id "
        "GROUP BY u.id ORDER BY c DESC, u.username", True,
        ["JOIN commits to users on author_id", "ORDER BY the count DESC"],
    ),
    Drill(
        "having", "Active repos", "GROUP BY ... HAVING",
        "List the names of repos with more than 3 commits.",
        "SELECT r.name FROM commits cm JOIN repos r ON r.id=cm.repo_id "
        "GROUP BY r.id HAVING COUNT(*) > 3", False,
        ["HAVING filters after GROUP BY, WHERE can't see COUNT(*)"],
    ),
    Drill(
        "inner-join", "Who owns what", "INNER JOIN",
        "List each repo's name with its owner's username.",
        "SELECT r.name, u.username FROM repos r JOIN users u ON u.id=r.owner_id ORDER BY r.id", True,
        ["repos.owner_id references users.id"],
    ),
    Drill(
        "left-join", "Quiet issues", "LEFT JOIN",
        "List every issue's title with its number of comments, including issues with zero comments.",
        "SELECT i.title, COUNT(c.id) FROM issues i LEFT JOIN comments c ON c.issue_id=i.id "
        "GROUP BY i.id ORDER BY i.id", True,
        ["an INNER JOIN would drop issues with no comments - use LEFT JOIN", "COUNT(c.id) not COUNT(*)"],
    ),
    Drill(
        "subquery-not-in", "Never filed", "subquery",
        "List the usernames of users who have never opened an issue.",
        "SELECT username FROM users WHERE id NOT IN (SELECT opened_by FROM issues) ORDER BY username", True,
        ["NOT IN (SELECT opened_by FROM issues)"],
    ),
    Drill(
        "exists", "Still open somewhere", "EXISTS",
        "List the names of repos that have at least one open issue.",
        "SELECT r.name FROM repos r WHERE EXISTS "
        "(SELECT 1 FROM issues i WHERE i.repo_id=r.id AND i.status='open') ORDER BY r.name", True,
        ["EXISTS (SELECT 1 FROM issues i WHERE i.repo_id=r.id AND i.status='open')"],
    ),
    Drill(
        "like", "Patch notes", "LIKE",
        "List the messages of commits that mention 'fix', in id order.",
        "SELECT message FROM commits WHERE message LIKE '%fix%' ORDER BY id", True,
        ["LIKE '%fix%'"],
    ),
    Drill(
        "case", "Open or closed", "CASE",
        "List each issue's title with a state column that says 'Open' or 'Closed' (map the status "
        "column with CASE), in id order.",
        "SELECT title, CASE WHEN status='open' THEN 'Open' ELSE 'Closed' END AS state "
        "FROM issues ORDER BY id", True,
        ["CASE WHEN status='open' THEN 'Open' ELSE 'Closed' END"],
    ),
    Drill(
        "case-sensitive", "Not the same Alice", "case sensitivity",
        "There are two users named alice/Alice. Find the row for the one spelled exactly lowercase "
        "'alice' (all columns).",
        "SELECT * FROM users WHERE username='alice'", False,
        ["sqlite text equality is case-sensitive by default"],
    ),
    Drill(
        "window", "Biggest change per repo", "window function",
        "For every commit, show repo_id, commit id, and its rank within its repo by lines_changed "
        "descending (ROW_NUMBER), ordered by repo_id then rank.",
        "SELECT repo_id, id, ROW_NUMBER() OVER (PARTITION BY repo_id ORDER BY lines_changed DESC) rn "
        "FROM commits ORDER BY repo_id, rn", True,
        ["ROW_NUMBER() OVER (PARTITION BY repo_id ORDER BY lines_changed DESC)"],
    ),
    Drill(
        "left-join-count", "Issues per repo", "LEFT JOIN, COUNT",
        "List each repo's name with how many issues it has, including repos with zero, in id order.",
        "SELECT r.name, COUNT(i.id) FROM repos r LEFT JOIN issues i ON i.repo_id=r.id "
        "GROUP BY r.id ORDER BY r.id", True,
        ["LEFT JOIN so a repo with no issues still shows up"],
    ),
    # ---- window functions, round 2 -------------------------------------------------------
    Drill(
        "window-running-total", "Running total", "window function: SUM() OVER",
        "For repo 1's commits ordered by committed_on, show the commit id and a running total of "
        "lines_changed, ordered by committed_on.",
        "SELECT id, SUM(lines_changed) OVER (ORDER BY committed_on) rt FROM commits "
        "WHERE repo_id=1 ORDER BY committed_on", True,
        ["SUM(lines_changed) OVER (ORDER BY committed_on)", "no PARTITION BY needed - one repo"],
    ),
    Drill(
        "window-lag", "Previous commit's size", "window function: LAG()",
        "For every commit, show repo_id, id, and the previous commit's lines_changed within the "
        "same repo (LAG, NULL for the first), ordered by repo_id then committed_on.",
        "SELECT repo_id, id, LAG(lines_changed) OVER (PARTITION BY repo_id ORDER BY committed_on) prev "
        "FROM commits ORDER BY repo_id, committed_on", True,
        ["LAG(lines_changed) OVER (PARTITION BY repo_id ORDER BY committed_on)"],
    ),
    Drill(
        "window-rank", "Rank by size", "window function: RANK()",
        "Rank each repo's commits by lines_changed descending with RANK (ties share a rank); show "
        "repo_id, id, rank, ordered by repo_id then rank.",
        "SELECT repo_id, id, RANK() OVER (PARTITION BY repo_id ORDER BY lines_changed DESC) rk "
        "FROM commits ORDER BY repo_id, rk", True,
        ["RANK() OVER (PARTITION BY repo_id ORDER BY lines_changed DESC)"],
    ),
    # ---- a self-join and a UNION, for variety --------------------------------------------
    Drill(
        "self-join", "Who's worked together", "self JOIN",
        "List every pair of distinct users who have both committed to the same repo - repo name, "
        "then the two usernames with user1 < user2 alphabetically (so each pair appears once), "
        "ordered by repo name then user1.",
        "SELECT r.name, u1.username, u2.username FROM commits c1 "
        "JOIN commits c2 ON c1.repo_id=c2.repo_id AND c1.author_id<c2.author_id "
        "JOIN repos r ON r.id=c1.repo_id JOIN users u1 ON u1.id=c1.author_id JOIN users u2 ON u2.id=c2.author_id "
        "GROUP BY r.id, u1.id, u2.id ORDER BY r.name, u1.username", True,
        ["self-join commits to commits on repo_id, with author_id1 < author_id2 to avoid mirror pairs"],
    ),
    Drill(
        "union", "One big list", "UNION",
        "List every username AND every repo name together as a single alphabetical column named "
        "'name' (no duplicates).",
        "SELECT username AS name FROM users UNION SELECT name FROM repos ORDER BY name", True,
        ["UNION (not UNION ALL) drops duplicates and needs matching column counts"],
    ),
    # ---- DML/DDL chapter: a throwaway writable copy, verified by a follow-up SELECT -----
    Drill(
        "insert", "Onboard a user", "INSERT",
        "Add a new user: id 9, username 'heidi', email 'heidi@corp.dev', joined_on '2024-07-01', "
        "not an admin.",
        "INSERT INTO users VALUES (9,'heidi','heidi@corp.dev','2024-07-01',0)", False,
        ["INSERT INTO users VALUES (id, username, email, joined_on, is_admin)"],
        writable=True, verify_sql="SELECT username, email FROM users WHERE id=9",
    ),
    Drill(
        "update", "A well-earned promotion", "UPDATE",
        "Promote bob (id 3) to admin.",
        "UPDATE users SET is_admin=1 WHERE id=3", False,
        ["UPDATE users SET is_admin=1 WHERE id=3"],
        writable=True, verify_sql="SELECT is_admin FROM users WHERE id=3",
    ),
    Drill(
        "delete", "Clean up the duplicate", "DELETE",
        "Issue 1 has a literal duplicate comment (ids 2 and 3 are identical). Delete comment id 3.",
        "DELETE FROM comments WHERE id=3", False,
        ["DELETE FROM comments WHERE id=3", "after this, issue 1 should have 2 comments left"],
        writable=True, verify_sql="SELECT COUNT(*) FROM comments WHERE issue_id=1",
    ),
    Drill(
        "create-table", "A place for tags", "CREATE TABLE",
        "Create a new table `tags` with columns `id INTEGER PRIMARY KEY` and `name TEXT`.",
        "CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT)", False,
        ["CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT)"],
        writable=True,
        verify_sql="SELECT name FROM sqlite_master WHERE type='table' AND name='tags'",
    ),
    Drill(
        "rollback", "Changed your mind", "transaction / ROLLBACK",
        "Start a transaction, delete every commit in repo 1, then roll back - prove nothing was "
        "actually lost. Write it as one script: BEGIN; DELETE ...; ROLLBACK;",
        "BEGIN; DELETE FROM commits WHERE repo_id=1; ROLLBACK;", False,
        ["BEGIN; DELETE FROM commits WHERE repo_id=1; ROLLBACK;",
         "ROLLBACK undoes everything since BEGIN - the count should be unchanged (7)"],
        writable=True, verify_sql="SELECT COUNT(*) FROM commits WHERE repo_id=1",
    ),
]
