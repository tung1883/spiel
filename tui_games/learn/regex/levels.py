"""Pattern Marsh levels. Three modes now: "golf" (accept/reject lists, score = pattern length),
"extract" (the pattern's matches over a paragraph must equal an exact target list, in order -
teaches groups/anchors/greedy-vs-lazy in a way accept/reject can't, since two patterns can accept
the same strings while capturing different spans), and "substitute" (pattern + replacement must
turn `before` into `after` exactly - backreferences, \\1, greedy vs lazy with a visible effect).
32 levels, original content, following PLAN.md section 3's chapter order; a regex-crossword mode is
still deferred (noted in README).
"""
from dataclasses import dataclass, field


@dataclass
class RegexLevel:
    id: str
    title: str
    teach: str
    yes: list[str]
    no: list[str]
    reference: str
    par: int
    hints: list[str] = field(default_factory=list)
    mode: str = "golf"
    # extract mode:
    text: str = ""
    targets: list[str] = field(default_factory=list)
    # substitute mode (also uses `reference` as the pattern):
    before: str = ""
    after: str = ""
    repl: str = ""


LEVELS: list[RegexLevel] = [
    RegexLevel(
        "literal", "Literals", "Letters match themselves.",
        ["cat", "concatenate", "category"], ["dog", "car"],
        "cat", 3, ["Just type the three letters."],
    ),
    RegexLevel(
        "dot", "The dot", ". matches any single character.",
        ["cat", "cot", "cut"], ["ct", "caat"],
        "c.t", 3, ["c then . then t."],
    ),
    RegexLevel(
        "class", "Character classes", "[abc] matches one of the listed characters.",
        ["cat", "bat", "hat"], ["rat", "mat"],
        "[cbh]at", 7, ["[cbh]at - list the three starting letters."],
    ),
    RegexLevel(
        "negrange", "Ranges and negation", "[0-9] is a range; [^x] matches anything except x.",
        ["dog5", "dog9"], ["dog", "dogs"],
        "dog[0-9]", 8, ["dog followed by a digit range."],
    ),
    RegexLevel(
        "anchors", "Anchors ^ $", "^ pins the start, $ pins the end of the string.",
        ["error: bad"], ["an error: bad", "error: bad "],
        "^error: bad$", 12, ["Anchor both ends so nothing extra is allowed."],
    ),
    RegexLevel(
        "boundary", "Word boundary \\b", "\\b matches between a word character and a non-word one.",
        ["cat sat", "a cat."], ["concatenate", "scatter"],
        r"\bcat\b", 7, [r"\bcat\b - a boundary on each side."],
    ),
    RegexLevel(
        "star", "Quantifier *", "x* means zero or more of x.",
        ["ac", "abc", "abbbc"], ["axc", "abx"],
        "ab*c", 4, ["a, then b*, then c."],
    ),
    RegexLevel(
        "braces", "Quantifier {n,m}", "{n,m} means between n and m repeats.",
        ["1234", "12345"], ["123", "123456"],
        r"^\d{4,5}$", 10, ["Anchor it, then \\d{4,5}."],
    ),
    RegexLevel(
        "groupalt", "Groups and alternation", "(a|b) matches a or b.",
        ["cat", "dog"], ["bat", "cog"],
        "^(cat|dog)$", 12, ["^(cat|dog)$"],
    ),
    RegexLevel(
        "optional", "Quantifier ?", "x? means zero or one of x.",
        ["color", "colour"], ["colouur", "colr"],
        "^colou?r$", 10, ["colou?r, anchored."],
    ),
    RegexLevel(
        "nestedgroup", "Repeating a group", "(ab)+ repeats the whole group, not just b.",
        ["ab", "abab", "ababab"], ["aba", "abc"],
        "^(ab)+$", 8, ["^(ab)+$"],
    ),
    RegexLevel(
        "backref_simple", "Backreferences", "\\1 matches the same text the first group matched.",
        ["the the cat", "bye bye"], ["the cat", "the cats"],
        r"\b(\w+) \1\b", 12, [r"(\w+) then \1 to repeat it."],
    ),
    RegexLevel(
        "backref_tag", "Matching tag pairs", "A backreference can close what a group opened.",
        ["<b>hi</b>", "<i>x</i>y"], ["<b>hi</i>", "<b>hi"],
        r"<(\w+)>.*</\1>", 14, [r"<(\w+)> ... </\1>"],
    ),
    RegexLevel(
        "boss_email", "Boss: a plain email", "A loose but real email shape.",
        ["a@b.com", "a.b@c-d.org"], ["a@b", "@b.com", "a@.com"],
        r"^[\w.]+@[\w-]+\.\w+$", 20, ["name part, @, domain part, dot, suffix - anchored."],
    ),
    RegexLevel(
        "boss_ipv4", "Boss: IPv4 shape", "Four dot-separated 1-3 digit groups (ranges not enforced).",
        ["1.2.3.4", "255.255.255.255"], ["1.2.3", "1.2.3.4.5"],
        r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", 36, ["Four copies of \\d{1,3} separated by \\."],
    ),
    RegexLevel(
        "boss_hex", "Boss: hex color", "# followed by exactly 6 hex digits.",
        ["#1a2b3c", "#FFFFFF"], ["#12345", "#gggggg"],
        "^#[0-9A-Fa-f]{6}$", 19, ["#[0-9A-Fa-f]{6}, anchored."],
    ),
    RegexLevel(
        "boss_semver", "Boss: semver", "Three dot-separated numbers - major.minor.patch, nothing more.",
        ["1.2.3", "0.0.1"], ["1.2", "1.2.3.4", "v1.2.3"],
        r"^\d+\.\d+\.\d+$", 15, ["Three \\d+ separated by \\., anchored both ends."],
    ),
    RegexLevel(
        "boss_url", "Boss: a plain URL", "http or https, a host, an optional path.",
        ["http://a.com", "https://a.b.com/path/x"], ["ftp://a.com", "a.com"],
        r"^https?://[\w.-]+(/\S*)?$", 25, ["https? :// host (/path)?, anchored."],
    ),
    # ---- Extract mode: the matches themselves must equal an exact target list, in order ----
    RegexLevel(
        "ext_digits", "Extract: pull out the numbers", "In extract mode, every match the pattern finds must be"
        " exactly the highlighted targets - no more, no fewer.",
        [], [], r"\d+", 4, [r"\d+ - one or more digits."], mode="extract",
        text="order 12 has 3 items, order 45 has 7",
        targets=["12", "3", "45", "7"],
    ),
    RegexLevel(
        "ext_words_cap", "Extract: capitalised words", "Anchor on a capital letter, then let lowercase follow.",
        [], [], r"\b[A-Z][a-z]*\b", 15, [r"\b[A-Z][a-z]*\b"], mode="extract",
        text="Alice met Bob near the Lake",
        targets=["Alice", "Bob", "Lake"],
    ),
    RegexLevel(
        "ext_quoted", "Extract: quoted strings", "A quote, anything that isn't a quote, then a quote.",
        [], [], r'"[^"]*"', 9, [r'"[^"]*"'], mode="extract",
        text='say "hi" then "bye" now',
        targets=['"hi"', '"bye"'],
    ),
    RegexLevel(
        "ext_tags_lazy", "Extract: every tag, not the whole thing", "A greedy .+ would swallow from the first <"
        " to the last > in one match. Lazy .+? stops at the first >, giving you every tag separately.",
        [], [], r"<.+?>", 5, [r"<.+?>"], mode="extract",
        text="<a><b>text</b></a>",
        targets=["<a>", "<b>", "</b>", "</a>"],
    ),
    # ---- Substitute mode: pattern + replacement must turn `before` into `after` exactly ----
    RegexLevel(
        "sub_simple", "Substitute: a plain swap", "Match the word, replace it with another.",
        [], [], "cat", 7, ["pattern: cat   replacement: dog"], mode="substitute",
        before="the cat sat", after="the dog sat", repl="dog",
    ),
    RegexLevel(
        "sub_group_swap", "Substitute: swap with groups", r"\1 and \2 refer back to what each group matched - "
        "use them in the replacement to reorder text.",
        [], [], r"(\w+), (\w+)", 18, [r"pattern: (\w+), (\w+)   replacement: \2 \1"], mode="substitute",
        before="Doe, John", after="John Doe", repl=r"\2 \1",
    ),
    RegexLevel(
        "sub_wrap_amp", "Substitute: wrap every match", r"\g<0> (or &-style $&) stands for the whole match - "
        "wrap each number in brackets without retyping it.",
        [], [], r"\d+", 11, [r"replacement: [\g<0>]"], mode="substitute",
        before="I have 3 cats and 2 dogs", after="I have [3] cats and [2] dogs", repl="[\\g<0>]",
    ),
    RegexLevel(
        "sub_dedupe_space", "Substitute: squeeze whitespace", "One or more spaces, replaced by exactly one.",
        [], [], " +", 4, ["pattern:  +   replacement: (one space)"], mode="substitute",
        before="a   b    c", after="a b c", repl=" ",
    ),
    # ---- Greedy vs lazy: the lesson golf mode can't teach, made visible via substitute ----
    RegexLevel(
        "greedy_quotes", "Greedy vs lazy I: the greedy trap", ".* is greedy - it reaches for the LAST matching"
        " quote, swallowing everything between the first and last quote in one match.",
        [], [], '".*"', 6, ['pattern: ".*"   replacement: Q - watch it eat both quoted words'], mode="substitute",
        before='"a" and "b"', after="Q", repl="Q",
    ),
    RegexLevel(
        "lazy_quotes", "Greedy vs lazy II: the lazy fix", ".*? is lazy - it stops at the FIRST matching quote,"
        " so each quoted word becomes its own match.",
        [], [], '".*?"', 7, ['pattern: ".*?"   replacement: Q - now each quote pair matches separately'],
        mode="substitute", before='"a" and "b"', after="Q and Q", repl="Q",
    ),
    RegexLevel(
        "greedy_tag", "Greedy vs lazy III: tags, greedy", "<.*> greedily spans from the very first < to the"
        " very last > - the whole line becomes one match.",
        [], [], "<.*>", 6, ["pattern: <.*>   replacement: X"], mode="substitute",
        before="<a><b>text</b></a>", after="X", repl="X",
    ),
    RegexLevel(
        "lazy_tag", "Greedy vs lazy IV: tags, lazy", "<.*?> stops at each first >, so every tag is matched and"
        " replaced on its own - text in between survives untouched.",
        [], [], "<.*?>", 7, ["pattern: <.*?>   replacement: X"], mode="substitute",
        before="<a><b>text</b></a>", after="XXtextXX", repl="X",
    ),
]
