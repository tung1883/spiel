"""Bug Hunt snippets: original small Python functions, one bug each. `code` is the buggy source,
`bug_line` is the 1-indexed line (within `code`, not any test harness) that must be accused and
fixed, `fix` is the corrected replacement text for that line (may itself contain embedded "\n" to
insert a couple of lines in place of one), `tests` is appended after the (buggy or fixed) code to
form a runnable script: it must print "OK" and exit 0 only when the function behaves correctly.
"""
from dataclasses import dataclass


@dataclass
class BugLevel:
    id: str
    title: str
    tier: str  # "beginner" | "intermediate" | "expert"
    code: str
    bug_line: int
    bug_class: str
    explanation: str
    fix: str
    tests: str


def apply_fix(level: "BugLevel") -> str:
    lines = level.code.split("\n")
    lines[level.bug_line - 1] = level.fix
    return "\n".join(lines)


def build_script(code: str, level: "BugLevel") -> str:
    return code + "\n\n" + level.tests


LEVELS: list[BugLevel] = [
    BugLevel(
        "1", "Sum to N", "beginner",
        code="""def sum_to(n):
    total = 0
    for i in range(1, n):
        total += i
    return total""",
        bug_line=3, bug_class="off-by-one",
        explanation="range(1, n) stops before n, so the last number is never added.",
        fix="    for i in range(1, n + 1):",
        tests='assert sum_to(5) == 15\nprint("OK")',
    ),
    BugLevel(
        "2", "Age Check", "beginner",
        code="""def is_adult(age):
    return age > 18""",
        bug_line=2, bug_class="wrong-operator",
        explanation="18-year-olds are adults too: it should be >=, not >.",
        fix="    return age >= 18",
        tests='assert is_adult(18) is True\nassert is_adult(17) is False\nprint("OK")',
    ),
    BugLevel(
        "3", "Shopping List", "beginner",
        code="""def add_item(item, items=[]):
    items.append(item)
    return items""",
        bug_line=1, bug_class="mutable-default-arg",
        explanation="A mutable default list is created once and shared across every call.",
        fix="def add_item(item, items=None):\n    items = items if items is not None else []",
        tests='assert add_item("a") == ["a"]\nassert add_item("b") == ["b"]\nprint("OK")',
    ),
    BugLevel(
        "4", "Retry Loop", "intermediate",
        code="""MAX_RETRIES = 3

def attempt(task, max_retries=MAX_RETRIES):
    retries = 0
    while retries < MAX_RETRIES:
        if task():
            return True
        retries += 1
    return False""",
        bug_line=5, bug_class="scope-shadowing",
        explanation="The loop checks the module constant MAX_RETRIES, ignoring the max_retries argument.",
        fix="    while retries < max_retries:",
        tests="""def flaky():
    flaky.calls += 1
    return flaky.calls >= 5
flaky.calls = 0
assert attempt(flaky, max_retries=10) is True
print("OK")""",
    ),
    BugLevel(
        "5", "Friendly Greeting", "intermediate",
        code="""def greet(user):
    name = user.get("name")
    return "Hello, " + name.upper()""",
        bug_line=3, bug_class="none-check",
        explanation="user.get('name') can be None, and None has no .upper().",
        fix='    return "Hello, " + (name or "friend").upper()',
        tests='assert greet({"name": "Ada"}) == "Hello, ADA"\nassert greet({}) == "Hello, FRIEND"\nprint("OK")',
    ),
    BugLevel(
        "6", "Average Score", "beginner",
        code="""def average(nums):
    return sum(nums) // len(nums)""",
        bug_line=2, bug_class="integer-division",
        explanation="// truncates to an int, throwing away the fractional part of the average.",
        fix="    return sum(nums) / len(nums)",
        tests='assert average([1, 2, 4]) == 7 / 3\nprint("OK")',
    ),
    BugLevel(
        "7", "Duplicate Tag", "intermediate",
        code="""def is_duplicate_tag(tag, seen_tags):
    for t in seen_tags:
        if t is tag:
            return True
    return False""",
        bug_line=3, bug_class="eq-vs-is",
        explanation="`is` checks identity, not equality - two equal strings can be different objects.",
        fix="        if t == tag:",
        tests="""seen = ["".join(["d", "u", "p"])]
assert is_duplicate_tag("dup", seen) is True
print("OK")""",
    ),
    BugLevel(
        "8", "Highest Score", "beginner",
        code="""def max_value(nums):
    best = nums[0]
    for n in nums[1:]:
        if n > best:
            best = n
    return best""",
        bug_line=2, bug_class="boundary-empty-input",
        explanation="nums[0] crashes with an IndexError when the list is empty.",
        fix="    best = nums[0] if nums else None",
        tests="""assert max_value([3, 1, 4, 1, 5]) == 5
assert max_value([]) is None
print("OK")""",
    ),
    BugLevel(
        "9", "Global Counter", "intermediate",
        code="""counter = 0

def increment():
    counter += 1
    return counter""",
        bug_line=4, bug_class="scope-unbound-local",
        explanation="counter += 1 makes counter a local name without `global`, so it is unbound.",
        fix="    global counter\n    counter += 1",
        tests='assert increment() == 1\nassert increment() == 2\nprint("OK")',
    ),
    BugLevel(
        "10", "Total Cost", "intermediate",
        code="""def total_cost(price_str, quantity):
    return price_str * quantity""",
        bug_line=2, bug_class="type-coercion",
        explanation='price_str is text from a form; "9.99" * 3 repeats the string instead of multiplying.',
        fix="    return float(price_str) * quantity",
        tests='assert total_cost("9.99", 3) == 29.97\nprint("OK")',
    ),
    BugLevel(
        "11", "Voting Eligibility", "beginner",
        code="""def can_vote(age, is_citizen):
    if not is_citizen or age < 18:
        return True
    return False""",
        bug_line=2, bug_class="logic-inversion",
        explanation="The condition is backwards: it should require citizenship AND being 18+.",
        fix="    if is_citizen and age >= 18:",
        tests="""assert can_vote(20, True) is True
assert can_vote(20, False) is False
assert can_vote(15, True) is False
print("OK")""",
    ),
    BugLevel(
        "12", "Bonus Item", "intermediate",
        code="""def with_bonus(items):
    items.append("bonus")
    return items""",
        bug_line=2, bug_class="aliasing-mutation",
        explanation="append() mutates the caller's own list instead of returning a new one.",
        fix='    return items + ["bonus"]',
        tests="""cart = ["milk", "bread"]
result = with_bonus(cart)
assert result == ["milk", "bread", "bonus"]
assert cart == ["milk", "bread"]
print("OK")""",
    ),
    BugLevel(
        "13", "Target Reached", "expert",
        code="""def reached_target(total, target):
    return total == target""",
        bug_line=2, bug_class="float-comparison",
        explanation="Accumulated floats rarely equal a target exactly; compare within a tolerance.",
        fix="    return abs(total - target) < 1e-9",
        tests="""total = 0.1 + 0.1 + 0.1
assert reached_target(total, 0.3) is True
print("OK")""",
    ),
    BugLevel(
        "14", "Name Formatter", "intermediate",
        code='''def format_name(first, last):
    return "{0}, {0}".format(first, last)''',
        bug_line=2, bug_class="string-formatting",
        explanation="Both placeholders use index 0, so last is never used.",
        fix='    return "{1}, {0}".format(first, last)',
        tests='assert format_name("Ada", "Lovelace") == "Lovelace, Ada"\nprint("OK")',
    ),
    BugLevel(
        "15", "Factorial", "expert",
        code="""def factorial(n):
    if n == 0:
        return 0
    return n * factorial(n - 1)""",
        bug_line=3, bug_class="recursion-base-case",
        explanation="factorial(0) should be 1, not 0 - otherwise every result collapses to 0.",
        fix="        return 1",
        tests='assert factorial(5) == 120\nprint("OK")',
    ),
    BugLevel(
        "16", "Price Lookup", "beginner",
        code="""def get_price(catalog, item):
    return catalog[item]""",
        bug_line=2, bug_class="key-error-missing-default",
        explanation="catalog[item] raises KeyError for unknown items; fall back to a default.",
        fix="    return catalog.get(item, 0)",
        tests="""catalog = {"apple": 1.5, "pear": 2.0}
assert get_price(catalog, "apple") == 1.5
assert get_price(catalog, "kiwi") == 0
print("OK")""",
    ),
    BugLevel(
        "17", "Late Binding Closures", "intermediate",
        code="""def make_multipliers():
    fns = []
    for i in range(3):
        fns.append(lambda x: x * i)
    return fns""",
        bug_line=4, bug_class="closure-late-binding",
        explanation="i is looked up when the lambda RUNS, not when it's created - all three share the final i.",
        fix="        fns.append(lambda x, i=i: x * i)",
        tests="""fns = make_multipliers()
assert [f(10) for f in fns] == [0, 10, 20]
print("OK")""",
    ),
    BugLevel(
        "18", "Remove Evens", "intermediate",
        code="""def remove_evens(nums):
    for n in nums:
        if n % 2 == 0:
            nums.remove(n)
    return nums""",
        bug_line=2, bug_class="mutate-during-iteration",
        explanation="Removing from a list while iterating over it skips elements - iterate a copy instead.",
        fix="    for n in nums[:]:",
        tests="""assert remove_evens([2, 4, 6, 1, 3]) == [1, 3]
print("OK")""",
    ),
    BugLevel(
        "19", "Shipping Cost", "beginner",
        code="""FREE = 5

def shipping_cost(weight):
    if not weight:
        return FREE
    return weight * 2""",
        bug_line=4, bug_class="falsy-vs-none",
        explanation="weight=0 is falsy but a legitimate value (a free digital item) - check `is None`, not truthiness.",
        fix="    if weight is None:",
        tests="""assert shipping_cost(0) == 0
assert shipping_cost(None) == 5
assert shipping_cost(3) == 6
print("OK")""",
    ),
    BugLevel(
        "20", "Top Scores", "intermediate",
        code="""def top_scores(scores, n):
    return sorted(scores, reverse=True)[n]""",
        bug_line=2, bug_class="wrong-slice",
        explanation="[n] grabs a single element at index n, not the top n - slice with [:n] instead.",
        fix="    return sorted(scores, reverse=True)[:n]",
        tests="""assert top_scores([5, 3, 9, 1], 2) == [9, 5]
print("OK")""",
    ),
    BugLevel(
        "21", "Settings Merge", "intermediate",
        code="""def with_defaults(opts, extra={}):
    extra.update(opts)
    return extra""",
        bug_line=1, bug_class="mutable-default-arg",
        explanation="A mutable default dict is created once and shared across every call.",
        fix="def with_defaults(opts, extra=None):\n    extra = extra if extra is not None else {}",
        tests="""a = with_defaults({"x": 1})
b = with_defaults({"y": 2})
assert a == {"x": 1} and b == {"y": 2}
print("OK")""",
    ),
    BugLevel(
        "22", "List Sum", "expert",
        code="""def list_sum(lst):
    if len(lst) == 1:
        return lst[0]
    return lst[0] + list_sum(lst[1:])""",
        bug_line=2, bug_class="recursion-base-case",
        explanation="An empty list never hits len(lst)==1 and falls through to lst[0] on the next line - crashes. Handle empty first.",
        fix="    if not lst:\n        return 0\n    if len(lst) == 1:",
        tests="""assert list_sum([5]) == 5
assert list_sum([1, 2, 3]) == 6
assert list_sum([]) == 0
print("OK")""",
    ),
    BugLevel(
        "23", "Price Tag", "beginner",
        code='''def price_tag(name, price):
    return f"{name}: ${price:.0f}"''',
        bug_line=2, bug_class="string-formatting",
        explanation="`.0f` drops the cents entirely - use `.2f` to keep two decimal places.",
        fix='    return f"{name}: ${price:.2f}"',
        tests='assert price_tag("Tea", 2.5) == "Tea: $2.50"\nprint("OK")',
    ),
    BugLevel(
        "24", "Grade Average", "beginner",
        code="""def grade_average(grades):
    return sum(grades) / len(grades)""",
        bug_line=2, bug_class="boundary-empty-input",
        explanation="An empty grade list divides by zero - return 0 when there's nothing to average.",
        fix="    return sum(grades) / len(grades) if grades else 0",
        tests="""assert grade_average([80, 90, 100]) == 90
assert grade_average([]) == 0
print("OK")""",
    ),
    BugLevel(
        "25", "Palindrome Check", "beginner",
        code="""def is_palindrome(word):
    return word == word[::-1]""",
        bug_line=2, bug_class="case-sensitivity",
        explanation="'Racecar' isn't equal to its own reverse by case - normalize with .lower() on both sides.",
        fix="    return word.lower() == word.lower()[::-1]",
        tests="""assert is_palindrome("racecar") is True
assert is_palindrome("Racecar") is True
assert is_palindrome("hello") is False
print("OK")""",
    ),
    BugLevel(
        "26", "Fetch And Double", "expert",
        code="""import asyncio


async def fetch_value():
    await asyncio.sleep(0)
    return 42


async def get_doubled():
    value = fetch_value()
    return value * 2""",
        bug_line=10, bug_class="missing-await",
        explanation="Calling an async function without await returns a coroutine object, not its result.",
        fix="    value = await fetch_value()",
        tests="""result = asyncio.run(get_doubled())
assert result == 84
print("OK")""",
    ),
    BugLevel(
        "27", "Get Config", "intermediate",
        code="""def get_config(options, key, default=None):
    return options.get(key) or default""",
        bug_line=2, bug_class="falsy-vs-none",
        explanation='`or default` kicks in for ANY falsy stored value (False, 0, "") - check for None explicitly.',
        fix="    value = options.get(key)\n    return value if value is not None else default",
        tests="""assert get_config({"debug": False}, "debug", True) is False
assert get_config({}, "debug", True) is True
print("OK")""",
    ),
    BugLevel(
        "28", "Binary Search", "expert",
        code="""def binary_search(nums, target):
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1""",
        bug_line=3, bug_class="off-by-one",
        explanation="`lo < hi` stops one step too early - the last remaining candidate (lo == hi) is never checked.",
        fix="    while lo <= hi:",
        tests="""nums = [1, 3, 5, 7, 9]
assert binary_search(nums, 9) == 4
assert binary_search(nums, 1) == 0
assert binary_search(nums, 4) == -1
print("OK")""",
    ),
    BugLevel(
        "29", "Duplicate Row", "intermediate",
        code="""def duplicate_row(row, times):
    return [row] * times""",
        bug_line=2, bug_class="aliasing-mutation",
        explanation="[row] * times repeats the SAME list object - mutating one copy mutates all of them.",
        fix="    return [list(row) for _ in range(times)]",
        tests="""rows = duplicate_row([1, 2, 3], 3)
rows[0].append(9)
assert rows[1] == [1, 2, 3]
print("OK")""",
    ),
    BugLevel(
        "30", "Weighted Average", "beginner",
        code="""def weighted_average(values, weights):
    return sum(v + w for v, w in zip(values, weights)) / sum(weights)""",
        bug_line=2, bug_class="wrong-operator",
        explanation="Each value should be multiplied by its weight, not added to it.",
        fix="    return sum(v * w for v, w in zip(values, weights)) / sum(weights)",
        tests="""assert weighted_average([2, 4], [1, 1]) == 3
assert abs(weighted_average([2, 4], [1, 3]) - 3.5) < 1e-9
print("OK")""",
    ),
]
