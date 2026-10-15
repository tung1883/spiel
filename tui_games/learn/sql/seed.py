"""Deterministic fictional datasets for Archive of Queries - three worlds, one per case, all hand-
written (not generated, not copied from SQL Murder Mystery) so every run produces the exact same
rows with no random seed needed.

- `connect()` / world "company": a small software company (users/repos/commits/issues/comments).
  Backs the drills and Case 1.
- `connect_shop()` / world "shop": a small online shop (customers/products/orders/tickets).
  Backs Case 2.
- `connect_stream()` / world "stream": a music-streaming royalty ledger (artists/tracks/plays).
  Backs Case 3.

Each world plants its own data-quality traps (a case-duplicate name, a NULL, a literal duplicate
row) in the same spirit as the original company dataset.
"""
import sqlite3

# ============================== world: company ==============================
SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY, username TEXT NOT NULL, email TEXT NOT NULL,
    joined_on TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE repos (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, owner_id INTEGER NOT NULL REFERENCES users(id),
    created_on TEXT NOT NULL, stars INTEGER NOT NULL
);
CREATE TABLE commits (
    id INTEGER PRIMARY KEY, repo_id INTEGER NOT NULL REFERENCES repos(id),
    author_id INTEGER NOT NULL REFERENCES users(id), message TEXT NOT NULL,
    committed_on TEXT NOT NULL, lines_changed INTEGER NOT NULL
);
CREATE TABLE issues (
    id INTEGER PRIMARY KEY, repo_id INTEGER NOT NULL REFERENCES repos(id),
    opened_by INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL,
    status TEXT NOT NULL, opened_on TEXT NOT NULL, closed_on TEXT
);
CREATE TABLE comments (
    id INTEGER PRIMARY KEY, issue_id INTEGER NOT NULL REFERENCES issues(id),
    author_id INTEGER NOT NULL REFERENCES users(id), body TEXT NOT NULL, posted_on TEXT NOT NULL
);
"""

USERS = [
    (1, "alice", "alice@corp.dev", "2021-01-10", 0),
    (2, "Alice", "alice.chen@corp.dev", "2022-03-01", 0),
    (3, "bob", "bob@corp.dev", "2021-02-15", 0),
    (4, "carol", "carol@corp.dev", "2020-11-20", 1),
    (5, "dave", "dave@corp.dev", "2023-05-05", 0),
    (6, "erin", "erin@corp.dev", "2021-07-07", 0),
    (7, "frank", "frank@corp.dev", "2022-09-09", 0),
    (8, "grace", "grace@corp.dev", "2023-01-01", 0),
]

REPOS = [
    (1, "atlas", 4, "2020-12-01", 340),
    (2, "beacon", 1, "2021-03-01", 12),
    (3, "cipher", 6, "2022-01-01", 88),
]

COMMITS = [
    (1, 1, 4, "initial import", "2021-01-02", 500),
    (2, 1, 3, "add login flow", "2021-02-20", 120),
    (3, 1, 5, "fix off-by-one in pager", "2022-04-11", 8),
    (4, 1, 7, "refactor router", "2023-01-05", 60),
    (5, 1, 5, "remove old changelog", "2024-06-14", -120),
    (6, 1, 4, "cut release 2.0", "2024-06-13", 15),
    (7, 2, 1, "initial import", "2021-03-02", 200),
    (8, 2, 1, "fix flaky test", "2021-09-09", 5),
    (9, 2, 3, "add CI config", "2022-02-02", 40),
    (10, 2, 8, "fix typo in README", "2023-03-03", 1),
    (11, 3, 6, "initial import", "2022-01-02", 300),
    (12, 3, 6, "add encryption module", "2022-05-05", 90),
    (13, 3, 7, "fix memory leak", "2022-11-11", 20),
    (14, 3, 2, "fix build on windows", "2023-07-07", 10),
    (15, 1, 3, "add tests for router", "2023-01-06", 35),
    (16, 3, 6, "bump dependencies", "2024-01-01", 3),
]

ISSUES = [
    (1, 1, 4, "Release v2.0 missing changelog", "closed", "2024-06-15", "2024-06-16"),
    (2, 1, 3, "login redirect loop on logout", "open", "2024-02-01", None),
    (3, 2, 1, "flaky test fails on CI", "closed", "2021-09-10", "2021-09-12"),
    (4, 3, 7, "memory leak under load", "closed", "2022-11-12", "2022-11-20"),
    (5, 3, 2, "windows build broken", "open", "2023-07-08", None),
    (6, 1, 7, "router 404s on trailing slash", "open", "2023-01-10", None),
]

COMMENTS = [
    (1, 1, 4, "who force-pushed over the changelog right before release?", "2024-06-15"),
    (2, 1, 5, "sorry, that was me, I force-removed the changelog file by mistake", "2024-06-15"),
    (3, 1, 5, "sorry, that was me, I force-removed the changelog file by mistake", "2024-06-15"),
    (4, 2, 3, "still happens on Firefox", "2024-02-02"),
    (5, 4, 7, "patched, see commit 13", "2022-11-13"),
    (6, 5, 2, "repro'd on a clean checkout", "2023-07-09"),
]


def connect() -> sqlite3.Connection:
    """A fresh in-memory connection with the company dataset loaded. Not yet locked down - db.py."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO users VALUES (?,?,?,?,?)", USERS)
    conn.executemany("INSERT INTO repos VALUES (?,?,?,?,?)", REPOS)
    conn.executemany("INSERT INTO commits VALUES (?,?,?,?,?,?)", COMMITS)
    conn.executemany("INSERT INTO issues VALUES (?,?,?,?,?,?,?)", ISSUES)
    conn.executemany("INSERT INTO comments VALUES (?,?,?,?,?)", COMMENTS)
    conn.commit()
    return conn


# ============================== world: shop ==============================
SHOP_SCHEMA = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
    joined_on TEXT NOT NULL, region TEXT NOT NULL
);
CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE suppliers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL);
CREATE TABLE products (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories(id),
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id), unit_price REAL NOT NULL,
    discontinued INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
    ordered_on TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL
);
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_id INTEGER NOT NULL REFERENCES orders(id), subject TEXT NOT NULL,
    status TEXT NOT NULL, opened_on TEXT NOT NULL
);
"""

SHOP_CUSTOMERS = [
    (1, "dana", "dana@shop.test", "2022-01-10", "west"),
    (2, "Dana", "dana.k@shop.test", "2023-02-02", "east"),
    (3, "miguel", "miguel@shop.test", "2021-05-05", "east"),
    (4, "priya", "priya@shop.test", "2022-07-07", "south"),
    (5, "owen", "owen@shop.test", "2023-03-03", "west"),
    (6, "sofia", "sofia@shop.test", "2020-09-09", "south"),
]

SHOP_CATEGORIES = [(1, "electronics"), (2, "home"), (3, "outdoor")]

SHOP_SUPPLIERS = [(1, "brightline", "USA"), (2, "nordware", "Norway"), (3, "terrapeak", "Canada")]

SHOP_PRODUCTS = [
    (1, "wireless mouse", 1, 1, 19.99, 0),
    (2, "usb-c hub", 1, 1, 34.99, 0),
    (3, "desk lamp", 2, 2, 24.50, 0),
    (4, "camp stove", 3, 3, 59.00, 0),
    (5, "rain jacket", 3, 3, 89.00, 1),
    (6, "coffee grinder", 2, 2, 42.00, 0),
    (7, "bluetooth speaker", 1, 1, 45.00, 0),
    (8, "hiking poles", 3, 3, 29.99, 0),
    (9, "throw blanket", 2, 2, 22.00, 0),
    (10, "action camera", 1, 1, 120.00, 0),
]

SHOP_ORDERS = [
    (1, 1, "2023-04-01", "paid"),
    (2, 3, "2023-04-02", "paid"),
    (3, 4, "2023-04-03", "paid"),
    (4, 1, "2023-05-10", "paid"),
    (5, 5, "2023-05-15", "refunded"),
    (6, 6, "2023-06-01", "paid"),
    (7, 2, "2023-06-02", "paid"),
    (8, 3, "2023-06-10", "pending"),
]

SHOP_ORDER_ITEMS = [
    (1, 1, 1, 2, 19.99),
    (2, 1, 3, 1, 24.50),
    (3, 2, 4, 1, 59.00),
    (4, 3, 6, 1, 42.00),
    (5, 4, 7, 1, 45.00),
    (6, 4, 7, 1, 45.00),  # exact duplicate of row 5 - the double charge
    (7, 4, 8, 2, 29.99),
    (8, 5, 5, 1, 89.00),
    (9, 6, 9, 3, 22.00),
    (10, 6, 2, 1, 34.99),
    (11, 7, 10, 1, 120.00),
    (12, 8, 1, 1, 19.99),
    (13, 8, 3, 1, 24.50),
    (14, 2, 2, 1, 34.99),
]

SHOP_TICKETS = [
    (1, 1, 4, "I think I was double charged for the bluetooth speaker", "open", "2023-05-20"),
    (2, 5, 5, "requesting refund for rain jacket - wrong size", "closed", "2023-05-16"),
    (3, 6, 6, "where is my coffee grinder", "closed", "2023-06-05"),
]


def connect_shop() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SHOP_SCHEMA)
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", SHOP_CUSTOMERS)
    conn.executemany("INSERT INTO categories VALUES (?,?)", SHOP_CATEGORIES)
    conn.executemany("INSERT INTO suppliers VALUES (?,?,?)", SHOP_SUPPLIERS)
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?)", SHOP_PRODUCTS)
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?)", SHOP_ORDERS)
    conn.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", SHOP_ORDER_ITEMS)
    conn.executemany("INSERT INTO tickets VALUES (?,?,?,?,?,?)", SHOP_TICKETS)
    conn.commit()
    return conn


# ============================== world: stream ==============================
STREAM_SCHEMA = """
CREATE TABLE artists (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL);
CREATE TABLE tracks (
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, artist_id INTEGER NOT NULL REFERENCES artists(id),
    duration_sec INTEGER NOT NULL, isrc TEXT NOT NULL
);
CREATE TABLE listeners (
    id INTEGER PRIMARY KEY, username TEXT NOT NULL, country TEXT NOT NULL, signup_on TEXT NOT NULL
);
CREATE TABLE plays (
    id INTEGER PRIMARY KEY, listener_id INTEGER NOT NULL REFERENCES listeners(id),
    track_id INTEGER NOT NULL REFERENCES tracks(id), played_on TEXT NOT NULL,
    ms_played INTEGER NOT NULL
);
"""

STREAM_ARTISTS = [
    (1, "nova wave", "SE"),
    (2, "Nova Wave", "SE"),  # duplicate artist row - same act, re-entered under a new id
    (3, "crimson tide", "US"),
    (4, "echo valley", "UK"),
    (5, "paper moons", "CA"),
]

STREAM_TRACKS = [
    (1, "Afterglow", 1, 210, "ISRC001"),
    (2, "Night Drive", 2, 198, "ISRC002"),
    (3, "Riverbed", 3, 240, "ISRC003"),
    (4, "Static Bloom", 4, 180, "ISRC004"),
    (5, "Glass Fields", 5, 205, "ISRC005"),
    (6, "Low Tide", 3, 220, "ISRC006"),
    (7, "Afterglow (Live)", 1, 230, "ISRC007"),
]

STREAM_LISTENERS = [
    (1, "kai", "SE", "2021-01-01"),
    (2, "lena", "US", "2021-02-02"),
    (3, "omar", "UK", "2022-03-03"),
    (4, "yuki", "JP", "2022-04-04"),
    (5, "noor", "CA", "2023-05-05"),
]

# ms_played >= 30000 (30s) counts as a royalty-eligible "full play".
STREAM_PLAYS = [
    (1, 1, 1, "2023-06-01", 210000),
    (2, 2, 1, "2023-06-02", 45000),
    (3, 3, 2, "2023-06-03", 198000),
    (4, 4, 2, "2023-06-04", 15000),  # partial - not eligible
    (5, 1, 3, "2023-06-05", 240000),
    (6, 2, 3, "2023-06-06", 240000),
    (7, 3, 4, "2023-06-07", 180000),
    (8, 5, 5, "2023-06-08", 205000),
    (9, 1, 6, "2023-06-09", 220000),
    (10, 4, 6, "2023-06-10", 20000),  # partial - not eligible
    (11, 2, 7, "2023-06-11", 230000),
    (12, 5, 1, "2023-06-12", 210000),
    (13, 3, 1, "2023-06-13", 5000),  # partial - not eligible
    (14, 1, 2, "2023-06-14", 198000),
    (15, 4, 3, "2023-06-15", 240000),
    (16, 5, 4, "2023-06-16", 180000),
]


def connect_stream() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(STREAM_SCHEMA)
    conn.executemany("INSERT INTO artists VALUES (?,?,?)", STREAM_ARTISTS)
    conn.executemany("INSERT INTO tracks VALUES (?,?,?,?,?)", STREAM_TRACKS)
    conn.executemany("INSERT INTO listeners VALUES (?,?,?,?)", STREAM_LISTENERS)
    conn.executemany("INSERT INTO plays VALUES (?,?,?,?,?)", STREAM_PLAYS)
    conn.commit()
    return conn


WORLDS = {"company": connect, "shop": connect_shop, "stream": connect_stream}
