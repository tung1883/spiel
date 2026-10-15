"""Code Typing ("Typing Forge"): original idiomatic snippets across 5 languages. Reduced from
PLAN.md's ~150-snippet/10-language target to ~50/5 for this pass (Python, JavaScript, Go, Rust, SQL).

Modes (screens.py): Snippet (plain typing), Recall (memorize then type blind), Explain-then-type
(a one-line quiz on the snippet's `note` before typing it), Boss (a longer `tier="expert"` program
under a visible time limit), and a post-run Symbols drill built from whatever characters you missed."""
import ast
import random
from dataclasses import dataclass


@dataclass
class Snippet:
    id: str
    lang: str
    title: str
    code: str  # real newlines, spaces only (no tabs)
    note: str  # one sentence: what the idiom is for
    tier: str = "beginner"  # beginner | intermediate | expert ("expert" = Boss mode material)


SNIPPETS: list[Snippet] = [
    # ---- Python ---------------------------------------------------------
    Snippet("py1", "python", "List comprehension filter", (
        "evens = [n for n in range(20) if n % 2 == 0]\n"
        "squares = [n * n for n in evens]"
    ), "Build a filtered, transformed list in one readable expression instead of a loop."),
    Snippet("py2", "python", "Context manager file read", (
        "with open(\"data.txt\") as f:\n"
        "    lines = [line.strip() for line in f]\n"
        "print(len(lines), \"lines\")"
    ), "`with` closes the file automatically, even if reading raises."),
    Snippet("py3", "python", "Dataclass", (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Point:\n"
        "    x: float\n"
        "    y: float\n"
        "\n"
        "    def dist(self, other: \"Point\") -> float:\n"
        "        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5"
    ), "@dataclass generates __init__/__repr__/__eq__ from the annotated fields.", "intermediate"),
    Snippet("py4", "python", "Enumerate loop", (
        "for i, name in enumerate(names, start=1):\n"
        "    print(f\"{i}. {name}\")"
    ), "enumerate pairs each item with its index without a manual counter."),
    Snippet("py5", "python", "Dict get with default", (
        "counts = {}\n"
        "for word in words:\n"
        "    counts[word] = counts.get(word, 0) + 1"
    ), "dict.get(key, default) avoids a KeyError on the first occurrence."),
    Snippet("py6", "python", "Generator function", (
        "def chunks(seq, size):\n"
        "    for i in range(0, len(seq), size):\n"
        "        yield seq[i:i + size]"
    ), "yield produces values lazily, one chunk at a time, without building a full list.", "intermediate"),
    Snippet("py7", "python", "Decorator with functools.wraps", (
        "from functools import wraps\n"
        "\n"
        "def log_calls(fn):\n"
        "    @wraps(fn)\n"
        "    def wrapper(*args, **kwargs):\n"
        "        print(f\"calling {fn.__name__}\")\n"
        "        return fn(*args, **kwargs)\n"
        "    return wrapper"
    ), "@wraps copies __name__/__doc__ onto the wrapper so introspection still works.", "intermediate"),
    Snippet("py8", "python", "Sorting with a key function", (
        "people.sort(key=lambda p: (p.age, p.name))"
    ), "A tuple key sorts by age first, then name, without writing a custom comparator."),
    Snippet("py9", "python", "Try/except/else/finally", (
        "try:\n"
        "    value = int(raw)\n"
        "except ValueError:\n"
        "    value = 0\n"
        "else:\n"
        "    print(\"parsed ok\")\n"
        "finally:\n"
        "    cleanup()"
    ), "else runs only if no exception was raised; finally always runs.", "intermediate"),
    Snippet("py10", "python", "Pattern matching (match/case)", (
        "match command.split():\n"
        "    case [\"go\", direction]:\n"
        "        move(direction)\n"
        "    case [\"quit\"]:\n"
        "        return\n"
        "    case _:\n"
        "        print(\"unknown command\")"
    ), "match/case destructures the list directly in each case pattern."),
    # ---- JavaScript -------------------------------------------------------
    Snippet("js1", "javascript", "Array map/filter/reduce", (
        "const total = orders\n"
        "    .filter((o) => o.paid)\n"
        "    .map((o) => o.amount)\n"
        "    .reduce((sum, n) => sum + n, 0);"
    ), "Chaining filter/map/reduce reads as a pipeline instead of nested loops."),
    Snippet("js2", "javascript", "Async/await fetch", (
        "async function loadUser(id) {\n"
        "    const res = await fetch(`/api/users/${id}`);\n"
        "    if (!res.ok) throw new Error(\"not found\");\n"
        "    return res.json();\n"
        "}"
    ), "await pauses until the promise settles, reading like synchronous code."),
    Snippet("js3", "javascript", "Destructuring assignment", (
        "const { name, age = 0, ...rest } = person;\n"
        "const [first, second] = scores;"
    ), "Destructuring pulls fields out of an object/array in one statement, with defaults."),
    Snippet("js4", "javascript", "Arrow function default param", (
        "const greet = (name, greeting = \"Hello\") => `${greeting}, ${name}!`;"
    ), "A default parameter covers the common case so most callers can omit it."),
    Snippet("js5", "javascript", "Promise.all", (
        "const [users, posts] = await Promise.all([\n"
        "    fetchUsers(),\n"
        "    fetchPosts(),\n"
        "]);"
    ), "Promise.all runs independent requests concurrently instead of one after another."),
    Snippet("js6", "javascript", "Template literal", (
        "const row = `${id}\\t${name.padEnd(12)}\\t${score.toFixed(1)}`;"
    ), "Template literals interpolate expressions directly into a string."),
    Snippet("js7", "javascript", "Optional chaining and nullish coalescing", (
        "const city = user?.address?.city ?? \"unknown\";"
    ), "?. short-circuits to undefined on a missing link; ?? only falls back on null/undefined."),
    Snippet("js8", "javascript", "Class with private field", (
        "class Counter {\n"
        "    #count = 0;\n"
        "    increment() {\n"
        "        return ++this.#count;\n"
        "    }\n"
        "}"
    ), "A #field is only reachable from inside the class, unlike a plain property.", "intermediate"),
    Snippet("js9", "javascript", "Set for deduplication", (
        "const uniqueIds = [...new Set(orders.map((o) => o.id))];"
    ), "Set drops duplicates; the spread turns it back into a plain array."),
    Snippet("js10", "javascript", "Async generator", (
        "async function* paginate(fetchPage) {\n"
        "    let page = 0;\n"
        "    let items;\n"
        "    while ((items = await fetchPage(page++)).length) {\n"
        "        yield* items;\n"
        "    }\n"
        "}"
    ), "An async generator yields items as pages arrive, without loading them all first.", "intermediate"),
    # ---- Go ---------------------------------------------------------------
    Snippet("go1", "go", "Error handling idiom", (
        "data, err := os.ReadFile(path)\n"
        "if err != nil {\n"
        "    return fmt.Errorf(\"read %s: %w\", path, err)\n"
        "}"
    ), "Checking err right after the call, and wrapping it with %w, is Go's standard idiom."),
    Snippet("go2", "go", "Goroutine and channel", (
        "ch := make(chan int)\n"
        "go func() {\n"
        "    ch <- compute()\n"
        "}()\n"
        "result := <-ch"
    ), "A channel hands a value from a goroutine back to the caller safely."),
    Snippet("go3", "go", "Struct and method", (
        "type Rect struct {\n"
        "    W, H float64\n"
        "}\n"
        "\n"
        "func (r Rect) Area() float64 {\n"
        "    return r.W * r.H\n"
        "}"
    ), "A method with a value receiver attaches behaviour to the struct without mutating it."),
    Snippet("go4", "go", "Defer cleanup", (
        "f, err := os.Open(path)\n"
        "if err != nil {\n"
        "    return err\n"
        "}\n"
        "defer f.Close()"
    ), "defer runs Close() when the function returns, on every exit path."),
    Snippet("go5", "go", "Slice append", (
        "var evens []int\n"
        "for _, n := range nums {\n"
        "    if n%2 == 0 {\n"
        "        evens = append(evens, n)\n"
        "    }\n"
        "}"
    ), "append grows the slice, reallocating under the hood only when capacity runs out."),
    Snippet("go6", "go", "Interface definition", (
        "type Shape interface {\n"
        "    Area() float64\n"
        "}"
    ), "Any type with an Area() method satisfies Shape - no explicit \"implements\" needed."),
    Snippet("go7", "go", "Select on two channels", (
        "select {\n"
        "case v := <-ch1:\n"
        "    fmt.Println(\"got\", v)\n"
        "case <-time.After(time.Second):\n"
        "    fmt.Println(\"timeout\")\n"
        "}"
    ), "select waits on whichever channel is ready first, with time.After as a timeout.", "intermediate"),
    Snippet("go8", "go", "Map with ok check", (
        "if v, ok := cache[key]; ok {\n"
        "    return v\n"
        "}"
    ), "The two-value map lookup tells you whether the key was present, not just its zero value."),
    Snippet("go9", "go", "WaitGroup for fan-out", (
        "var wg sync.WaitGroup\n"
        "for _, url := range urls {\n"
        "    wg.Add(1)\n"
        "    go func(u string) {\n"
        "        defer wg.Done()\n"
        "        fetch(u)\n"
        "    }(url)\n"
        "}\n"
        "wg.Wait()"
    ), "wg.Wait() blocks until every goroutine has called Done(), even though they run concurrently.", "intermediate"),
    Snippet("go10", "go", "Generic function with a type constraint", (
        "func Sum[T int | float64](nums []T) T {\n"
        "    var total T\n"
        "    for _, n := range nums {\n"
        "        total += n\n"
        "    }\n"
        "    return total\n"
        "}"
    ), "The type parameter [T int | float64] lets one function work over either numeric type.", "intermediate"),
    # ---- Rust ---------------------------------------------------------------
    Snippet("rs1", "rust", "Option matching", (
        "match config.get(\"timeout\") {\n"
        "    Some(v) => v.parse().unwrap_or(30),\n"
        "    None => 30,\n"
        "}"
    ), "match forces every case of the Option to be handled, so a missing key can't panic silently."),
    Snippet("rs2", "rust", "Result with ?", (
        "fn read_count(path: &str) -> Result<u32, std::io::Error> {\n"
        "    let text = std::fs::read_to_string(path)?;\n"
        "    Ok(text.trim().parse().unwrap_or(0))\n"
        "}"
    ), "? returns the error early, so the happy path stays on one line."),
    Snippet("rs3", "rust", "Struct and impl", (
        "struct Point { x: f64, y: f64 }\n"
        "\n"
        "impl Point {\n"
        "    fn dist(&self, other: &Point) -> f64 {\n"
        "        ((self.x - other.x).powi(2) + (self.y - other.y).powi(2)).sqrt()\n"
        "    }\n"
        "}"
    ), "impl blocks attach methods to a struct defined separately."),
    Snippet("rs4", "rust", "Iterator chain", (
        "let total: i32 = nums.iter().filter(|&&n| n > 0).sum();"
    ), "Iterator chains stay lazy until sum() (or collect()) actually consumes them."),
    Snippet("rs5", "rust", "Match on enum", (
        "enum Shape { Circle(f64), Square(f64) }\n"
        "\n"
        "fn area(s: &Shape) -> f64 {\n"
        "    match s {\n"
        "        Shape::Circle(r) => std::f64::consts::PI * r * r,\n"
        "        Shape::Square(side) => side * side,\n"
        "    }\n"
        "}"
    ), "match on an enum with data is exhaustive - the compiler flags a missing variant."),
    Snippet("rs6", "rust", "Borrowing a function argument", (
        "fn longest<'a>(a: &'a str, b: &'a str) -> &'a str {\n"
        "    if a.len() >= b.len() { a } else { b }\n"
        "}"
    ), "Taking &str instead of String borrows the caller's data instead of copying it."),
    Snippet("rs7", "rust", "Trait with a default method", (
        "trait Greet {\n"
        "    fn name(&self) -> String;\n"
        "    fn hello(&self) -> String {\n"
        "        format!(\"Hello, {}!\", self.name())\n"
        "    }\n"
        "}"
    ), "A default method body lets implementors override only name() and still get hello() for free.", "intermediate"),
    Snippet("rs8", "rust", "Vec collect with filter_map", (
        "let valid: Vec<i32> = raw.iter().filter_map(|s| s.parse().ok()).collect();"
    ), "filter_map drops the None results from parse(), keeping only the values that succeeded."),
    Snippet("rs9", "rust", "Box<dyn Trait> for dynamic dispatch", (
        "fn make_shape(kind: &str) -> Box<dyn Shape> {\n"
        "    match kind {\n"
        "        \"circle\" => Box::new(Circle::default()),\n"
        "        _ => Box::new(Square::default()),\n"
        "    }\n"
        "}"
    ), "Box<dyn Shape> returns different concrete types behind one trait-object pointer.", "intermediate"),
    Snippet("rs10", "rust", "Arc<Mutex<T>> for shared state", (
        "let counter = Arc::new(Mutex::new(0));\n"
        "let c = Arc::clone(&counter);\n"
        "thread::spawn(move || {\n"
        "    *c.lock().unwrap() += 1;\n"
        "});"
    ), "Arc shares ownership across threads; Mutex guards the one field they all mutate.", "intermediate"),
    # ---- SQL ---------------------------------------------------------------
    Snippet("sql1", "sql", "Join with aggregate", (
        "SELECT c.name, COUNT(o.id) AS orders\n"
        "FROM customers c\n"
        "LEFT JOIN orders o ON o.customer_id = c.id\n"
        "GROUP BY c.name\n"
        "ORDER BY orders DESC;"
    ), "LEFT JOIN keeps customers with zero orders; GROUP BY then counts per customer."),
    Snippet("sql2", "sql", "Group by with having", (
        "SELECT dept, AVG(salary) AS avg_salary\n"
        "FROM employees\n"
        "GROUP BY dept\n"
        "HAVING AVG(salary) > 60000;"
    ), "HAVING filters on the aggregate itself, after grouping - WHERE cannot do that."),
    Snippet("sql3", "sql", "Common table expression", (
        "WITH recent AS (\n"
        "    SELECT * FROM events WHERE created_at > date(\"now\", \"-7 days\")\n"
        ")\n"
        "SELECT user_id, COUNT(*) FROM recent GROUP BY user_id;"
    ), "A CTE names a subquery so the main query reads top-to-bottom."),
    Snippet("sql4", "sql", "Window function running total", (
        "SELECT day, amount,\n"
        "       SUM(amount) OVER (ORDER BY day) AS running_total\n"
        "FROM sales;"
    ), "A window function computes a running total without collapsing rows with GROUP BY."),
    Snippet("sql5", "sql", "Insert from select", (
        "INSERT INTO archive (id, name)\n"
        "SELECT id, name FROM users WHERE active = 0;"
    ), "INSERT ... SELECT copies query results straight into another table."),
    Snippet("sql6", "sql", "Create table with foreign key", (
        "CREATE TABLE comments (\n"
        "    id INTEGER PRIMARY KEY,\n"
        "    post_id INTEGER NOT NULL REFERENCES posts(id),\n"
        "    body TEXT NOT NULL\n"
        ");"
    ), "A foreign key constraint keeps comments from pointing at a post that doesn't exist."),
    Snippet("sql7", "sql", "Correlated subquery with EXISTS", (
        "SELECT name FROM customers c\n"
        "WHERE EXISTS (\n"
        "    SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.amount > 1000\n"
        ");"
    ), "EXISTS stops at the first matching row instead of counting every order.", "intermediate"),
    Snippet("sql8", "sql", "Rank within groups", (
        "SELECT dept, name, salary,\n"
        "       RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rnk\n"
        "FROM employees;"
    ), "PARTITION BY restarts the ranking for each department instead of ranking globally.", "intermediate"),
    Snippet("sql9", "sql", "Case expression bucketing a value", (
        "SELECT name,\n"
        "       CASE\n"
        "           WHEN score >= 90 THEN \"A\"\n"
        "           WHEN score >= 75 THEN \"B\"\n"
        "           ELSE \"C\"\n"
        "       END AS grade\n"
        "FROM results;"
    ), "CASE evaluates its WHEN clauses top to bottom and stops at the first match."),
    Snippet("sql10", "sql", "Update with a join-style subquery", (
        "UPDATE products\n"
        "SET price = price * 1.1\n"
        "WHERE category_id IN (SELECT id FROM categories WHERE name = \"electronics\");"
    ), "The subquery resolves to a set of ids that the UPDATE's WHERE then filters on.", "intermediate"),
]

# ---- Boss mode material: longer, harder, tier="expert" original programs ------------------
BOSS_SNIPPETS: list[Snippet] = [
    Snippet("boss_py", "python", "LRU cache from scratch", (
        "from collections import OrderedDict\n"
        "\n"
        "\n"
        "class LRUCache:\n"
        "    def __init__(self, capacity: int):\n"
        "        self.capacity = capacity\n"
        "        self.store: OrderedDict[str, int] = OrderedDict()\n"
        "\n"
        "    def get(self, key: str) -> int:\n"
        "        if key not in self.store:\n"
        "            return -1\n"
        "        self.store.move_to_end(key)\n"
        "        return self.store[key]\n"
        "\n"
        "    def put(self, key: str, value: int) -> None:\n"
        "        if key in self.store:\n"
        "            self.store.move_to_end(key)\n"
        "        self.store[key] = value\n"
        "        if len(self.store) > self.capacity:\n"
        "            self.store.popitem(last=False)"
    ), "move_to_end + popitem(last=False) turn an OrderedDict into an O(1) LRU cache.", "expert"),
    Snippet("boss_js", "javascript", "Debounce helper", (
        "function debounce(fn, delayMs) {\n"
        "    let timer = null;\n"
        "    return function debounced(...args) {\n"
        "        clearTimeout(timer);\n"
        "        timer = setTimeout(() => {\n"
        "            timer = null;\n"
        "            fn.apply(this, args);\n"
        "        }, delayMs);\n"
        "    };\n"
        "}\n"
        "\n"
        "const onResize = debounce(() => {\n"
        "    console.log(\"layout recalculated\");\n"
        "}, 200);"
    ), "Each call resets the timer, so fn only runs once the caller has been quiet for delayMs.", "expert"),
    Snippet("boss_go", "go", "Worker pool over a job channel", (
        "func worker(id int, jobs <-chan int, results chan<- int, wg *sync.WaitGroup) {\n"
        "    defer wg.Done()\n"
        "    for j := range jobs {\n"
        "        results <- j * j\n"
        "    }\n"
        "}\n"
        "\n"
        "func RunPool(nums []int, workers int) []int {\n"
        "    jobs := make(chan int, len(nums))\n"
        "    results := make(chan int, len(nums))\n"
        "    var wg sync.WaitGroup\n"
        "    for w := 0; w < workers; w++ {\n"
        "        wg.Add(1)\n"
        "        go worker(w, jobs, results, &wg)\n"
        "    }\n"
        "    for _, n := range nums {\n"
        "        jobs <- n\n"
        "    }\n"
        "    close(jobs)\n"
        "    wg.Wait()\n"
        "    close(results)\n"
        "    out := make([]int, 0, len(nums))\n"
        "    for r := range results {\n"
        "        out = append(out, r)\n"
        "    }\n"
        "    return out\n"
        "}"
    ), "Closing jobs lets each worker's range loop end naturally once all work is drained.", "expert"),
    Snippet("boss_rs", "rust", "Binary search implemented by hand", (
        "fn binary_search(sorted: &[i32], target: i32) -> Option<usize> {\n"
        "    let mut lo = 0usize;\n"
        "    let mut hi = sorted.len();\n"
        "    while lo < hi {\n"
        "        let mid = lo + (hi - lo) / 2;\n"
        "        match sorted[mid].cmp(&target) {\n"
        "            std::cmp::Ordering::Equal => return Some(mid),\n"
        "            std::cmp::Ordering::Less => lo = mid + 1,\n"
        "            std::cmp::Ordering::Greater => hi = mid,\n"
        "        }\n"
        "    }\n"
        "    None\n"
        "}"
    ), "lo + (hi - lo) / 2 finds the midpoint without the overflow risk of (lo + hi) / 2.", "expert"),
    Snippet("boss_sql", "sql", "Monthly cohort retention", (
        "WITH signups AS (\n"
        "    SELECT id, date(created_at, \"start of month\") AS cohort\n"
        "    FROM users\n"
        "),\n"
        "active AS (\n"
        "    SELECT user_id, date(created_at, \"start of month\") AS active_month\n"
        "    FROM events\n"
        "    GROUP BY user_id, active_month\n"
        ")\n"
        "SELECT s.cohort, a.active_month, COUNT(DISTINCT a.user_id) AS active_users\n"
        "FROM signups s\n"
        "JOIN active a ON a.user_id = s.id\n"
        "GROUP BY s.cohort, a.active_month\n"
        "ORDER BY s.cohort, a.active_month;"
    ), "Two CTEs separate 'when a user signed up' from 'when they were active', then join them.", "expert"),
]


ALL_SNIPPETS: list[Snippet] = SNIPPETS + BOSS_SNIPPETS


def validate_all() -> None:
    """Cheap sanity checks: no tabs/trailing whitespace, sane length, Python parses."""
    for s in ALL_SNIPPETS:
        assert "\t" not in s.code, s.id
        assert not any(line != line.rstrip() for line in s.code.split("\n")), s.id
        lines = s.code.count("\n") + 1
        max_lines = 30 if s.tier == "expert" else 15
        assert 1 <= lines <= max_lines, (s.id, lines)
        if s.lang == "python":
            ast.parse(s.code)


def distractor_notes(correct: Snippet, count: int = 2) -> list[str]:
    """Pick `count` other snippets' notes as plausible-but-wrong answers for an Explain-then-type
    quiz - auto-sampled rather than hand-authored per snippet, to keep ~50 entries affordable."""
    pool = [s.note for s in ALL_SNIPPETS if s.id != correct.id and s.note != correct.note]
    return random.sample(pool, k=min(count, len(pool)))


validate_all()
