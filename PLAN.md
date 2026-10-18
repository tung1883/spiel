# Learn to Code: 7 story-driven coding games inside spiel

> Handoff document for a fresh session. Read sections 0 (state and conventions) and 12 (research to do first) before
> writing any code. Sections 1-11 are the approved plan. The user approved it as written; do not re-ask the questions
> already answered in "Context".

## 0. Current state and working conventions

**Repo:** `C:\Users\Tung\Documents\work\spiel` (not a git repo, Windows, Python 3.12, Textual 8.2.8, editable install
`pip install -e .`, entry point `spiel`). Related repos nearby: `..\plainphone`, `..\butler` (not needed here).

**Already built (do not redo):**
- Main menu `src/app.py`: rows TypeRacer, Chess, Minesweeper, **Vim Quest (learn vim)**, Settings. `s` / `ctrl+s` open
  Settings.
- TypeRacer (`src/typeracer/`): races, offline mode, languages, instant death, analytics (`analytics.py`: `RaceStats`,
  ghosts in `typeracer-ghosts.json`, history), settings in `typeracer/menu.py` (`SettingsScreen`, accent colour via
  `self.app.theme_variables["primary"]`).
- Chess (`src/chess/`): Lichess, offline engine, Chess.com browserless client; text board + side panels.
- **Vim Quest v1** (`src/games/vimquest.py`, tests in `tests/test_vimquest.py`): `VimBuffer` engine (normal/insert, counts,
  motions h j k l w b e 0 ^ $ gg G f F t T ; ,, operators d/c, x D C r, i a A I o O, p P, u), 16 text-buffer levels
  with reference solutions, menu + level screens. It is the seed for Game 1 (section 2); its engine moves to
  `src/learn/vim/engine.py` and the 16 levels become "Training Rooms".
- Persistence: `src/config.py` (`load()/save()` of `%APPDATA%\spiel\config.json`; keys in use: `typeracer`,
  `lichess_token`, `best_minesweeper_expert`, `vimquest.best`). The new `learn` key must not disturb those.

**Conventions to follow (from the user's CLAUDE.md and what bit us):**
- Replies concise. Never add Co-Authored-By/AI attribution to commits; short commit messages; **never `git push`** unless told.
  (There is no git repo in `spiel` today; do not `git init` without asking.)
- Write code files with the Write/Edit tools, not shell heredocs: backslash escapes (`\n`, `\s`, `\t`) were mangled by the Bash
  tool repeatedly (broken strings in Python source, a tab character in a README path).
- Textual: do not name instance attributes `_size`, `size`, `render`, `_cell`-like names that shadow `Widget` internals
  (`Widget.size` and `_size` both caused bugs). Check a screen's geometry in a headless `App.run_test` and assert regions
  fit (a board once rendered off-screen because a widget defaulted to `width: 1fr`).
- Test pattern: `async with app.run_test(size=(w, h)) as pilot` + `pilot.press(...)`; set `APPDATA` to a temp dir in tests so
  `config.json` is not touched. Print `Static.render().plain` to assert text.
- Docs: keep `README.md` in sync (one section per game). Process notes: say honestly what was and was not verified.
- Safety: nothing in the games may touch the real filesystem, network or processes beyond the explicitly sandboxed
  subprocess in Bug Hunt. Never run `taskkill` on all of an application's processes (this killed the user's own Chrome once).

---

## Context
spiel (Python 3.12 + Textual 8, `C:\Users\Tung\Documents\work\spiel`) has TypeRacer, chess, Minesweeper and a first
"Vim Quest" (16 text-buffer puzzles, `src/games/vimquest.py`). The user wants a full suite of games that teach coding,
each as deep and polished as https://vim-adventures.com/ (a world you explore, abilities you earn, boss rooms, a feel of
progress), not a pile of quiz levels. Decisions already made with the user:

- **One "Learn to Code" hub** (a single main-menu row) with an **overworld map**; every game is a region.
- **Story/world with unlocks**: light story ("the Terminal Kingdom"), shared XP/rank, badges, par/star ratings per level.
- **Vim Quest is rebuilt as a 2D tile adventure** (walk the map with the keys you have earned). The existing 16 text
  puzzles become its "training rooms".
- All content is **original** (nothing copied from vim-adventures, Learn Git Branching, Regex Golf, SQL Murder Mystery).
  Inspirations are only formats/ideas.

Games (region names are placeholders): Vim Adventures-style world, Regex Golf, Git Quest, Shell Quest, SQL Detective,
Bug Hunt, Code Typing.

---

## 1. Architecture

New package `src/learn/` (replaces `games/vimquest.py`, whose `VimBuffer` is moved and extended):

```
src/learn/
  hub.py            overworld map screen, entry from the main menu
  progress.py       persistence + XP/ranks/badges/unlocks (config.json key "learn")
  story.py          regions, prerequisites, NPC dialogue text, rank titles
  widgets.py        shared widgets (see below)
  levelio.py        load + validate content files, error messages that name file/level
  vim/    engine.py  levels.py  world.py  screens.py   content/*.txt
  regex/  engine.py  explain.py screens.py              content/*.json
  git/    model.py   commands.py graph.py screens.py    content/*.json
  shell/  fs.py      parser.py  commands/*.py screens.py content/*.json
  sql/    db.py      screens.py                          content/cases/*.json, drills/*.json, seed.py
  bughunt/ tracer.py sandbox.py screens.py               content/*.json
  codetype/ screens.py                                   content/*.json
tests/learn/  one test module per game + test_progress.py + test_hub.py
```

Shared pieces (build once, Phase 0):

| Piece | What it does | Reuse |
|---|---|---|
| `progress.py` | `LearnProgress` (xp, badges, per-game `levels{id:{stars,best}}`, `inventory`, `unlocked`), `record(game, level, score, par)` -> stars (3 = at/under par, 2 = <=1.5x, 1 = done), XP, rank ladder (Novice, Apprentice, ... Archmage), daily-challenge streak | `src/config.py` `load()/save()` (same pattern as `typeracer/menu.py` `load_settings`) |
| `hub.py` | Overworld: ASCII map of regions with roads, `@` marker moved with hjkl/arrows, locked regions greyed, per-region progress bar, side panel (rank, XP bar, streak, next unlock), Enter opens the region's level map | accent colour via `self.app.theme_variables["primary"]` (as in `SettingsScreen`) |
| `widgets.py` | `Dialogue` (NPC speech box, typewriter, Enter to continue, skippable), `KeyboardView` (lit-up key map), `LevelMap` (generic level-select grid with stars), `ResultScreen` (stars, par vs yours, XP, "next / retry / map"), `HintBar` (hints cost a star), `CheatSheet` overlay (`?`) | Textual `Screen`/`Static`/`OptionList` patterns from `typeracer/menu.py` |
| `levelio.py` | JSON/TXT loaders with schema validation; content lives in package data (add to `pyproject.toml` `package-data`) | - |
| Hub entry | Replace the main-menu "Vim Quest" row with **"Learn to Code"**; add a `learn` option to the Settings screen (hints on/off, animations on/off) | `src/app.py` `Menu`, `typeracer/menu.py` `SettingsScreen` |

Cross-cutting rules:
- Every level has a **reference solution** and a **par**; a test per game replays every solution through the real engine
  (pattern already proven by `tests/test_vimquest.py`). A level without a passing solution fails CI.
- Every game gets a **sandbox/free mode**, a **cheat sheet** (`?`), a **hint ladder** (nudge -> concept -> solution), and
  an **`undo/reset`** key. Esc always leaves; progress saves after every level.
- Pilot (`App.run_test`) playthrough test per game: play level 1 through to the result screen with real key presses.
- Textual gotchas already hit in this repo: do not name attributes `_size`/`size`/`render`; build strings with real
  newlines in files (heredoc escaping bit us several times: use Write/Edit for code, not shell heredocs).

Story spine ("The Terminal Kingdom"): a once-glorious kingdom of code is overrun by *the Glitch*. You are a new Keeper
travelling the map; each region has a mentor NPC (the Vim monk, the Regex witch, the Git cartographer, the Shell
blacksmith, the SQL archivist, the Bug exterminator, the Typing bard) who gives lore, tutorials and the boss challenge.
Beating a region's boss gives a badge + XP and unlocks the next region. Regions 1-2 are open; the rest unlock by rank
so the player has a guided order but can still jump around after reaching Apprentice.

---

## 2. Game 1: Vim Adventures-style world ("Vim Highlands")

**Core idea (like vim-adventures):** the map *is* a text buffer. You are the cursor. You start knowing almost nothing
(one key) and **earn keys by collecting them in the world**; the keyboard view lights up what you own.

**Engine (extend `VimBuffer`, moved to `learn/vim/engine.py`, keep all existing tests passing):**
- Phase A (world 1-3): keep h j k l w b e 0 ^ $ gg G counts f t F T ; , x D r i a A I o O dd dw cw cc p P u.
- Phase B (world 4-5): add W B E, `{ }`, `H M L`, `%`, `Ctrl-d/u`, y (yy yw y$), `.` dot-repeat, J, ~, `>>`/`<<`,
  visual mode `v`/`V` + operators, text objects (`iw aw i( a( i" a" it`), search `/ ? n N * #`, marks `m ' `` `, registers
  `"a`, macros `q @`, ex subset `:s/a/b/[g]`, `:%s`, `:g/pat/d`, `:w`, `:q`.
- Each command is a name in an `allowed` set; unowned keys give a friendly "you have not found `w` yet" message.
- Per-command unit tests against real-vim expectations (table-driven: start buffer, keys, expected buffer+cursor).
  For correctness, spot-check the table against real `vim -es` (or `nvim --headless`) offline; if neither is installed on
  this machine skip the cross-check and rely on the tables.

**World model (`world.py`, map files `content/*.txt`):**
- A level is a text grid (the buffer) with a header: title, par, required-key, solution, NPC text.
- Tiles: `#` wall (blocks h/j/k/l steps only; jumps like `w f gg %` can cross, which is the puzzle), `@` start, `>` exit,
  letters shown as **key items** (`[w]`) that grant the command when the cursor lands on them, `%`-linked gate pairs
  `( )`, rubble `x`/`xxx` (destroy with `x`, `dw`, `dd`), locked doors `D` (open by typing the password written on a
  nearby sign with `i`/`cw`), "typo goblins" (a misspelled word that blocks the way; fix with `r`/`cw`/`ciw`), signs
  (read-only text you copy with `y`/`p`), bridges made of words separated by gaps (need `w`/`e` to hop), long corridors
  (need counts, `f`, `G`), mazes (need `%`, `{ }`, marks), vaults (visual mode + text objects), dark rooms (search `/`).
- Level goal types: reach `>`, edit buffer to match goal text, collect all items, or survive a "rising tide" (a move
  budget/turn timer) for speed-run levels.
- Persistent **inventory** (earned commands) lives in `progress.py`; levels declare `needs` (keys that must be owned) and
  `grants` (keys awarded on pickup). Re-playing earlier levels with all keys is allowed (par based on optimal keys).

**Content (target ~45 levels in 6 worlds + dojo):**
1. *Meadow* (hjkl): 6 levels, first level you can only press `l`; `j`, `k`, `h` found as items.
2. *Word Woods* (w b e W B E, counts): 7 levels, gap bridges, speed lane.
3. *Line Cliffs* (0 ^ $ gg G H M L f t ; , %): 8 levels, bracket gates, long vertical shafts.
4. *Edit Forge* (x dd dw cw cc yy p P u . J ~ r i a I A o O): 9 levels, rubble, goblins, password doors, a "move the
   function" puzzle; boss: rebuild a broken config file to match a spec.
5. *Mirror Lake* (visual mode, text objects, search, marks): 8 levels; boss: refactor a code snippet in N keys.
6. *Macro Mountain* (macros, registers, `:s`, `:g`, dot-repeat combos): 6 levels; boss: transform a 40-line file.
7. **Dojo** (post-game): generated challenges (random buffer + random edit target) scored against an optimal key count
   found by a bounded BFS/IDA* over the command set; plus a **daily challenge** (seeded by date) with streak.
- NPC "monk" gives a short tutorial per world (Dialogue widget) plus a `?` cheat sheet that only lists owned commands.
- Existing 16 `LEVELS` migrate as "Training Rooms" in the dojo (keep `Level`, `solve`, tests).

---

## 3. Game 2: Regex Golf ("Pattern Marsh")

**Mechanics:** each level shows two lists, **must match** and **must not match**. Type a regex; results update live per
string (green check / red cross, matched span highlighted, **why-it-failed** note such as "`cat` matches but should not").
Score = pattern length vs par (golf); stars by length; "clean" runs (no hint) give bonus XP.

**Modes:**
- *Golf* (core): accept/reject lists.
- *Extract*: a paragraph where exactly the highlighted target substrings must be matched (teaches groups/anchors).
- *Substitute*: write `pattern` and `replacement` so the before-text turns into the after-text (backrefs, `\1`, `$&`).
- *Validators* (bosses): realistic fields (email, IPv4, hex colour, ISO date, semver, URL, phone, password rules).
- *Daily*: seeded puzzle with a local best.

**Engine (`regex/engine.py`):** Python `re` is the dialect (state this in the UI). Evaluate each candidate in a worker with
a hard timeout (a `multiprocessing` pool or `concurrent.futures.ProcessPoolExecutor`, kill on >0.4s) and a pattern-length
cap, to survive catastrophic backtracking (`(a+)+$`) without freezing the UI; show "too slow (backtracking)" as a result,
which doubles as a lesson. Compile errors are shown inline with the offending position.
- **Explainer (`explain.py`)**: tokenises the pattern (use `re._parser` carefully or a small own tokenizer) and prints a
  plain-English line per token under the input (`\d{3}` -> "exactly 3 digits"); also a "show me what this part matches"
  step-through highlight. This is the learning hook beyond golf.
- **Reference solution per level** plus a "shortest known" par; test asserts reference passes every yes/no and is not
  shorter than par.

**Content (target ~48 levels, 8 chapters):** literals, `.`, character classes/ranges/negation, anchors/word boundaries,
`* + ? {n,m}`, groups and alternation, backreferences, lookahead/lookbehind, greedy vs lazy, flags, then validators and a
"regex crossword" mini-mode (grid where rows/columns each have a regex). Level data is JSON:
`{id, title, teach, mode, yes[], no[], par, reference, hints[], explain?}`.

---

## 4. Game 3: Git Quest ("Branch Forest")

**Engine (`git/model.py`, `commands.py`):** a faithful **in-memory simulation** (no real git needed, deterministic, cheap to
reset): commits with ids (short hex derived from content so they differ after rebase), parents, trees as
`{path: [lines]}`, branches, tags, HEAD (attached or detached), index and working tree, one simulated remote `origin`.
Commands: `init commit(-m,-a,--amend) add status log(--oneline,--graph) diff branch(-d,-m) switch/checkout(-b)
merge(--no-ff,--abort) rebase(onto, -i with pick/squash/drop/reword via a small picker UI) cherry-pick revert reset(--soft
--mixed --hard) restore stash(push/pop) tag fetch pull push(--force) remote reflog bisect(basic) clean`. Conflicts are
real: 3-way line merge, `<<<<<<<` markers in a tiny inline editor (choose ours/theirs/both or edit), then `add` +
`merge --continue`/`rebase --continue`.
- Unit tests compare commit graphs after each command against hand-written expectations (and spot-check semantics against
  real `git` if it is installed on this machine: build the same repo with `git`, compare `git log --graph --oneline`).

**Graph view (`graph.py`):** layered DAG layout (generation columns, branch lanes), commits as `o`/`@`, labels
(`main`, `feature`, `HEAD`, tags, `origin/main`) attached to tips, animated redraw when a command changes the graph
(brief highlight of new/moved commits), dim "ghost" of the previous position for rebase/reset so players see what moved.
Scales by collapsing long linear chains ("... 5 commits ...").

**Level types:**
- *Goal graph*: a target graph is shown beside yours (like Learn Git Branching); you win when branch tips/ancestry match
  (structural comparison by commit roles, not ids). Par = commands used.
- *Rescue missions* (story): detached HEAD, bad force-push, lost commits (use `reflog`), committed to wrong branch,
  secret in history (amend/rebase), messy history to squash before a "PR".
- *Conflict missions*: resolve and continue.
- *Collab missions*: fetch/pull/push against a scripted teammate who commits to `origin` between your commands.
- *Sandbox*: free repo, `git` command history, "explain what just happened" panel after every command.
- Every command prints a **plain-English consequence line** and the graph diff; `undo` rewinds the last command
  (snapshot stack) so exploring is safe.

**Content (target ~40 levels, 6 chapters):** commits and branches -> merging -> rebasing -> undoing things (reset/revert/
reflog) -> remotes -> advanced (interactive rebase, bisect, stash, worktrees as lore only). Boss: an "incident": a tangled
repo to restore to a clean linear history with specific commit messages.

---

## 5. Game 4: Shell Quest ("Terminal Caverns")

**Engine (`shell/`):** a fake POSIX-ish machine, entirely in memory.
- `fs.py`: tree of dirs/files/symlinks with mode bits, owner, mtime, size, file contents; path resolution (`.`, `..`,
  `~`, absolute/relative), globs (`* ? [..] {a,b}`), `$PWD/$HOME/$VAR`.
- `parser.py`: tokenizer and grammar for quotes, escapes, `$VAR`/`$(cmd)`, pipes `|`, redirects `> >> < 2>`, `&& || ;`,
  `for`/`if` in a minimal form, comments; clear errors ("bash: foo: command not found").
- `commands/`: `ls(-l -a -h -R -t) cd pwd cat head tail wc sort(-n -r -u -k) uniq(-c) cut tr grep(-i -n -r -v -c -E -l)
  find(-name -type -size -mtime -exec) sed(s///, -n p) awk('{print $N}' + simple conditions) xargs tee mkdir(-p) rm(-r)
  cp mv touch chmod(octal + symbolic) ln(-s) echo printf basename dirname diff date env export alias history man help
  ps kill(simulated processes) du df tar(list/extract simulated)`. Each has a short built-in `man` page so the learner can
  look things up in-game.
- UI: real-feeling terminal pane: prompt with cwd, command history (up/down), **tab completion** (commands, paths),
  scrollback, coloured `ls` (dirs/exec/symlinks), `Ctrl-C` interrupts, plus a side **mission panel** (objective,
  hints, command budget) and a **file-tree view** that updates live (toggle).
- Safety: nothing touches the real OS; no `subprocess`. Property tests: parser round-trips, `sort|uniq -c` etc. checked
  against Python reference implementations on random input.

**Missions (target ~40 in 7 chapters, story "restore the dying server"):** navigation, listing/inspecting files,
creating/moving/deleting, searching (`grep`, `find`), text processing (`cut sort uniq wc sed awk`), pipes and redirects,
permissions and links, variables/loops/scripts, final mission: triage a "compromised" box (find the rogue process,
the planted cron file, the leaked key, fix perms, write a report with a pipeline).
- Mission types: *find the answer* (`submit <text>` or `answer`), *make the filesystem look like this* (state check),
  *produce this exact output*, *constraint missions* ("do it with one pipeline", "without `find`").
- Level JSON: `{id, title, story, fs (compact DSL), objective, check{kind...}, par_commands, hints[], banned[], solution[]}`.
- Free "sandbox" machine with a few seeded projects to play in.

---

## 6. Game 5: SQL Detective ("Archive of Queries")

**Engine (`sql/db.py`):** stdlib `sqlite3` in memory, seeded deterministically from `seed.py` (fixed random seed) so story
facts are stable. Safety: `PRAGMA query_only=ON` in investigation/drill chapters, `SELECT/WITH/EXPLAIN` only; a chapter
that teaches DML/DDL runs on a throwaway copy with INSERT/UPDATE/DELETE/CREATE allowed; `set_progress_handler` timeout
(~1s) and a row cap (1,000) so `JOIN` blow-ups cannot hang the UI.

**Modes:**
- *Case files* (story): 3 multi-step investigations (e.g. "The Missing Commit", "The Phantom Invoice", "The Leaky
  Dashboard"), ~10 steps each. Each step gives a clue prompt, you query the database, you **submit an answer** (a name,
  number, date) to unlock the next step; the case notebook auto-collects discovered clues. Final accusation screen.
- *Drills* (~45): "return exactly this table" with the expected result set shown (diff of missing/extra rows and
  column mismatches); order only checked when the prompt requires `ORDER BY`.
- *Explain mode*: after a query, a "what the database did" panel: simplified plan (`EXPLAIN QUERY PLAN`), row counts per
  stage for joins/filters (computed by re-running prefixes), and an index lesson chapter showing scan vs search.
- *Schema explorer*: tables/columns/FKs panel, sample rows, ER sketch (box-drawing).
- Query editor: multi-line input, history, `Ctrl-Enter`/`F5` to run, basic keyword colouring, autocomplete for table and
  column names, results table with paging and column-width fitting; error messages rewritten in friendlier language with
  the original SQLite error underneath.

**Curriculum:** SELECT/WHERE/ORDER/LIMIT/DISTINCT -> aggregates, GROUP BY/HAVING -> JOINs (inner/left/self) -> subqueries
and EXISTS -> LIKE/dates/CASE -> CTEs -> window functions (`ROW_NUMBER`, `LAG`, running totals) -> DML/DDL, transactions
(rollback demo), indexes. Content files: `cases/*.json` (story, steps, reference query + expected answer) and
`drills/*.json` (`{prompt, reference_sql, ordered, hints}`). Tests: every reference query executes, produces the expected
answer/result set, and every case's final answer is derivable.

---

## 7. Game 6: Bug Hunt ("Bug Swamp")

**Idea:** you are an exterminator. Each level is a code file with a bug; the interesting part is the **tools** you use.
- *Hunt* (find the line): cursor on code (j/k, Enter to accuse) with a time/accuse budget.
- *Diagnose*: after a correct accusation pick the bug class (off-by-one, wrong operator, wrong variable, scope/shadowing,
  mutation/aliasing, type coercion, None/null, integer division, race condition, resource leak, logic inversion,
  boundary/empty-input, stale cache...). The explanation screen teaches that class with the minimal example.
- *Debugger tool* (`tracer.py`): for Python levels, record a real execution with `sys.settrace` in a sandbox subprocess and
  let the player **step forward/back**, set breakpoints, and watch locals change in a side panel; this is the hunting aid
  and the lesson in how to debug. Using it costs time, not stars.
- *Fix it*: edit the guilty line (inline) and hidden unit tests run in the sandbox; green = fixed. Partial credit for the
  right idea.
- *Review mode* (code review): a diff with 3 hunks, flag which are bugs vs fine (false positives cost points).
- *Daily bug*, *endless mode* (escalating difficulty, 3 lives).

**Sandbox (`sandbox.py`):** run snippets in a subprocess with `python -I`, a wall-clock timeout, no network, a temp
working dir, memory/ output limits; only bundled snippets plus the one edited line run, never arbitrary pasted code.
**Content (target ~70 snippets):** Python primary (executable), plus JS/TS, C, Go, Java, Rust read-only (hunt + diagnose)
with tiers beginner -> expert; each entry `{id, lang, tier, code, bug_line, class, explanation, fix, tests?}`. Test: for every
Python entry the buggy code fails the hidden tests, the fixed code passes, and `bug_line` matches the diff.

---

## 8. Game 7: Code Typing ("Typing Forge")

**Idea:** TypeRacer for programmers, plus learning hooks. Reuses the TypeRacer stack instead of duplicating it.
- Reuse: `typeracer/analytics.py` (`RaceStats`, `save_ghost/load_ghost/ghost_chars`, history), the ghost/replay UX and
  settings pattern from `typeracer/screen.py` and `typeracer/menu.py`.
- New `CodeRaceScreen`: character-accurate typing with **newlines and auto-indent** (Enter jumps over leading indent like
  monkeytype code mode), per-language snippet banks, correct handling of tabs/unicode, bracket-matching hints off by default.
- Modes: *Snippet* (idiomatic real-world code per language: Python, JS/TS, Go, Rust, C, Java, SQL, shell, HTML/CSS, git),
  *Symbols drill* (brackets, operators, pipes, quotes; adaptive: drills the keys you miss), *Recall* (snippet shown, then
  hidden after N seconds; retype from memory), *Explain-then-type* (a one-line "what does this do?" multiple choice before or
  after typing), *Boss*: type a whole small program with the timer.
- Analytics: per-language WPM, symbol-accuracy heatmap, slowest tokens/n-grams, trend over time, ghosts per snippet, streaks.
- Content: ~150 snippets across 10 languages in JSON `{id, lang, title, code, note}`, grouped by tier; each has a
  one-sentence `note` shown on the result screen (what the idiom is for). Tests: all snippets are valid for their language
  where a cheap check exists (`ast.parse` for Python, `json.loads` for JSON), no tabs/trailing spaces, length limits.

---

## 9. Rollout (each phase is independently shippable and leaves the app working)

| Phase | Scope | Notes |
|---|---|---|
| 0 | Shared framework: `progress.py`, `story.py`, `hub.py`, `widgets.py`, `levelio.py`, menu row "Learn to Code", settings, README | Hub starts with the existing 16 Vim levels so nothing regresses |
| 1 | Vim Highlands: engine extensions (A then B), world model + map renderer, KeyboardView, worlds 1-3 (~21 levels) | Largest piece; worlds 4-6 + dojo follow in 1b |
| 2 | Regex Marsh: engine + explainer + ~48 levels | Smallest; good early win |
| 3 | Shell Caverns: fs/parser/commands, terminal UI, missions | Needs the most engine tests |
| 4 | Git Forest: model, commands, graph renderer, levels | Hardest to get visually right |
| 5 | SQL Archive: sqlite harness, case files, drills | Content-heavy (dataset design) |
| 6 | Bug Swamp: sandbox + tracer + snippets | Security review of the sandbox |
| 7 | Typing Forge: CodeRaceScreen + snippet bank + analytics | Reuses TypeRacer code |
| 8 | Polish: cross-game badges, daily challenge hub tile, achievements screen, balance pass on par/XP, docs | |

Rough content volume: ~45 + 48 + 40 + 40 + (3 cases, 45 drills) + 70 + 150 snippets; **content is the main cost**, so each
phase ships first with its mechanics + about half the levels and fills in the rest after.

## 10. Critical files (existing)
- `src/app.py`: main menu row "Learn to Code" (replace the "Vim Quest" row).
- `src/config.py`: `load()/save()` reused by `progress.py`.
- `src/games/vimquest.py` + `tests/test_vimquest.py`: engine and level tests migrate into `learn/vim/`.
- `src/typeracer/analytics.py`: `RaceStats`, ghost helpers reused by Typing Forge.
- `src/typeracer/menu.py`: `SettingsScreen` pattern/accent colour, add learn settings.
- `pyproject.toml`: package-data for `content/**` files.

## 11. Verification
- `python -m pytest tests` must pass; per game: (a) every level's reference solution solves it in the real engine,
  (b) engine unit tables (vim motions/edits, regex evaluation + timeout, git command graphs, shell commands vs Python
  references, SQL reference queries/answers, bug-hunt fixes, snippet validity), (c) a Pilot-driven playthrough of the first
  level of each game from the main menu to the result screen, (d) `tests/learn/test_progress.py` (stars/XP/unlock rules,
  corrupted `config.json` tolerated).
- Manual pass per phase in a real terminal (Windows Terminal): hub navigation, first 3 levels of each game, resize
  behaviour at 80x24 and 140x50, `Esc` back from every screen, no input lag while typing (TypeRacer latency lessons).
- Safety checks: regex catastrophic-backtracking pattern returns "too slow" without freezing; sandbox kills an infinite
  loop snippet; SQL `query_only` rejects writes in non-DML chapters; shell sim never touches the real filesystem.
- Final: fresh `config.json` (new player) and an old one (existing keys such as `typeracer`, `lichess_token`) both work;
  README documents the hub, each game, controls and how to add levels.

---

## 12. Research to do before writing code

Do these first, in a scratch dir (e.g. the session scratchpad), and write the findings (short, decisions only) into
`docs/learn-research.md` so later sessions do not repeat them. Where a question needs the user, ask early.

### 12.1 Environment checks (5 minutes, decide fallbacks)
- Is a real `vim`/`nvim`, `git`, and `sqlite3` CLI installed (`where vim nvim git sqlite3`)? They are only used to cross-check
  test tables; if absent, the tables stand alone. Python's `sqlite3` module version and whether window functions work
  (`sqlite3.sqlite_version >= 3.25`).
- Terminal capabilities that matter: 24-bit colour, wide/emoji glyph widths in Windows Terminal, box-drawing chars,
  `Ctrl-Enter`/`F5` key reporting under Textual (which keys does Textual actually deliver on Windows? `ctrl+enter` often
  does not arrive; verify and pick fallbacks), `Tab` handling inside `Input`, the `~`/`^`/`%`/`:` keys on non-US layouts.
- Textual 8.2.8 specifics to confirm with a tiny prototype: capturing *all* keys in a Screen (`on_key` + `event.stop()`) while
  keeping a few global bindings; `TextArea` vs custom widgets for multi-line input (SQL editor, shell, inline code edit);
  `RichLog` for scrollback; `set_interval` cost with large `Static.update`; `Static.update(Text)` repaint speed for a 60x25
  tile map (the hub and Vim map both rely on it); `push_screen_wait`/modal screens for dialogues; `OptionList` selection API.
- Package data: confirm `pyproject.toml` `[tool.setuptools.package-data]` includes `learn/**/content/*` for the editable install
  and for a built wheel.

### 12.2 Per-game research (read, then summarise decisions)
**Vim (Game 1)**
- Vim motion/operator semantics that are easy to get wrong: `w/e/b` on punctuation and empty lines, `cw` special case, `dw`
  at end of line, `d` with linewise vs charwise motions, `p` after a charwise delete across lines, counts with operators
  (`2d3w`), `.` repeat rules (what is repeatable, count handling), text-object boundaries (`iw`, `i(` nested, `i"` escapes),
  visual mode cursor semantics (inclusive), search offsets, macro recording of counts, `:s` flags, registers (unnamed, named,
  `"0`, small-delete). Source: `:help motion.txt`, `:help change.txt`, `:help visual.txt`, `:help text-objects`. If `vim`/`nvim`
  is installed, generate the expected results for the unit-test tables from it (`nvim --headless -u NONE -c ...`).
- How vim-adventures structures its learning order and level puzzles (public descriptions only; take **ideas**, not content):
  key-unlock progression, map-as-buffer feel, boss rooms. Do not copy its level layouts, text or art; the plan's levels are
  original.
- Decide the map file format and the tile legend (section 2), the walls-block-steps-but-not-jumps rule, and how pickups grant
  commands; prototype one level (6 rows) end-to-end before authoring more.
- Optimal-solution search for the Dojo: prototype a bounded BFS/IDA* over the command alphabet on small buffers and measure
  time; decide the maximum buffer size / search depth that stays under ~1 s.

**Regex (Game 2)**
- Python `re` syntax limits vs what is taught (no possessive quantifiers before 3.11; atomic groups from 3.11; `\Z`, `(?i)`;
  no variable-width lookbehind). Check `re.compile` behaviour for the exact Python in use (3.12) and write down which
  features each chapter may use.
- Catastrophic backtracking: prototype the timeout worker (`ProcessPoolExecutor` + kill, or `multiprocessing.Process` +
  `join(timeout)`) and measure startup latency on Windows (spawn is slow; may need a long-lived worker process with a pipe
  and respawn-on-timeout). Pick the design that keeps live-as-you-type feedback under ~50 ms.
- Explainer: read `re._parser` (`sre_parse`) output (an internal API; check stability in 3.12) vs writing a tiny tokenizer;
  decide which. Prior art to study for UX only: regex101-style explanations, RegexOne lessons, Regex Golf, Regex Crossword.
- Collect candidate level material and verify each with a script: yes/no lists, a reference pattern, the best known short
  pattern (par) found by hand or a small search.

**Git (Game 3)**
- Exact semantics to model and verify against real `git` (if installed) or the Pro Git book: `merge` (ff vs three-way,
  conflict state, `--no-ff`, `--abort`), `rebase` (replay order, id changes, `--onto`, conflicts + `--continue`,
  `-i` todo list), `cherry-pick`, `reset` modes (what moves HEAD/index/worktree), `revert` (new commit), `reflog` entries per
  operation, detached HEAD, `stash`, `fetch/pull/push` (fast-forward rules, non-ff rejection, `--force`, `--force-with-lease`),
  remote-tracking branches, `bisect`. Write the table of expected graphs *before* coding the model.
- Commit id scheme: deterministic hash of (parents, tree, message, author counter) so tests are stable but ids change on rebase.
- 3-way line merge: study `diff3`/`merge` behaviour and the simplest correct algorithm (line-based LCS diff, hunk
  conflict detection); decide how conflicts are presented and resolved in the TUI (tiny inline editor vs choose
  ours/theirs/both).
- Graph rendering: study layered-DAG layout (Sugiyama basics, or a simpler "lanes per branch" layout like `git log --graph`),
  how to render in monospace with box chars, how to animate/highlight changes, and how to collapse long chains. Prototype with
  5-6 repos of increasing complexity (linear, diamond, octopus-free, with tags/remotes) and keep what reads well at 100 cols.
- Prior art for UX only: Learn Git Branching, Oh My Git!, `git log --graph` output.

**Shell (Game 4)**
- POSIX shell grammar subset to support (quoting rules, expansions order: brace, tilde, parameter, command substitution,
  word splitting, glob; redirect precedence; pipelines and `$?`; `&&`/`||`/`;`; `for`/`while`/`if` minimal forms) and the
  exact behaviour/outputs of each command used in missions (GNU coreutils flags: `ls -l` column format, `sort -k -n -r -u`,
  `uniq -c` padding, `wc` column widths, `grep -n/-c/-r` output prefixes, `find` traversal order and `-exec`, `sed s///`
  flags and `-n p`, `awk` field splitting and `$NF`, `cut -d -f`, `tr` ranges, `chmod` symbolic forms). Source: GNU manuals /
  POSIX spec; write expected-output fixtures by hand or from a real `bash`/WSL if available on this machine.
- Output ordering and determinism: define a fixed locale (C), fixed "now" for mtimes, stable directory order.
- Terminal UI feasibility: tab-completion UX, history, scrollback of 1000+ lines, coloured `ls`; Textual `Input` vs
  `TextArea`/`RichLog` combos (decide in 12.1).
- Mission design inputs: collect realistic sysadmin/forensics scenarios and decide the compact FS DSL (e.g. indented tree
  text with `name (mode owner mtime): content`).

**SQL (Game 5)**
- SQLite features available in Python 3.12's bundled version (window functions, CTEs, `RETURNING`, `strftime`, JSON1).
  `PRAGMA query_only`, `set_progress_handler`, `sqlite3.Connection.set_authorizer` (use it to enforce SELECT-only and block
  `ATTACH`/`PRAGMA`/extensions), row-cap strategy, and `EXPLAIN QUERY PLAN` output format (turn it into readable text).
- Dataset design: pick three coherent fictional datasets (a software company, a shop, a streaming/analytics app), 6-10 tables
  each with realistic names, FKs, dates, deliberate data-quality traps (NULLs, duplicates, case differences). Write the
  generator with a fixed seed and **plant the story clues** so each case has a unique, verifiable answer chain.
- Result-set comparison rules for drills (order-insensitive by default, float tolerance, column-name tolerance, extra
  columns) and friendly error rewriting for common SQLite errors (`no such column`, ambiguous column, syntax near ...).
- Prior art for pedagogy only: SQL Murder Mystery, SQLBolt, Select Star SQL, Advent-of-SQL style puzzles. Do not copy their
  datasets or text.

**Bug Hunt (Game 6)**
- Sandbox design for running Python snippets safely on Windows: `subprocess` with `-I -S`, `creationflags` for a new process
  group, timeout + kill tree, resource limits (the `resource` module is Unix-only; on Windows use a Job Object via `ctypes`,
  or just wall-clock + output caps), stripped environment, temp cwd, and **no network** (block with a
  `sitecustomize`/audit-hook `sys.addaudithook` denying `socket.*`, `os.system`, `subprocess`, file writes outside the temp
  dir). Prototype and try to escape it with a few hostile snippets before trusting it.
- Tracer: `sys.settrace`/`sys.monitoring` (3.12) to capture (line, locals) per step; decide serialization (repr with caps),
  max steps (e.g. 2000) and how to display step-back (record the full trace and index into it).
- Bug taxonomy and a curated bug list: write ~70 realistic bugs (not contrived trivia), each with a failing-test + fix check.
  Study classic bug catalogues (off-by-one, aliasing, integer overflow in C, `==` vs `is`, shadowed names, mutable default
  args, float comparison, timezone/DST, unicode normalisation, async race, missing `await`, unclosed resource) for ideas.
- Multi-language entries are display-only: confirm syntax highlighting approach in Rich (`rich.syntax.Syntax` supports many
  lexers via Pygments; Pygments is already a dependency of Rich) and that it renders well inside a `Static`.

**Code Typing (Game 7)**
- How the existing TypeRacer screen processes keys (`typeracer/screen.py` `on_key`, `RaceStats`) and what must change for
  code: newlines, indentation skipping, tab/space handling, non-printable keys (Enter, Tab), IME-free symbols. Read
  `typeracer/analytics.py` ghost helpers (`save_ghost/load_ghost/ghost_chars`) and decide how to key ghosts for code snippets.
- Monkeytype's code mode / `typing.io` behaviours for UX reference (auto-indent, how mistakes show).
- Snippet sourcing: write original, idiomatic snippets (do not paste from licensed repositories); keep each 3-15 lines; record
  a one-line note for each; check validity with `ast.parse`/`json.loads`/`shlex` where cheap.

### 12.3 Cross-cutting design decisions to settle first (write them down)
1. Hub map layout and navigation model (graph of region nodes vs a free `@` walking an ASCII map); how locked regions look.
2. Rank/XP/star formulas and unlock thresholds (a short table); how "par" is defined per game (keystrokes, characters, commands,
   queries, seconds) and the 3-star rule.
3. `config.json` schema for `learn` (versioned: `{"v":1, ...}`) and migration of `vimquest.best` into it.
4. Content authoring format per game (JSON vs TXT vs Python), a shared loader/validator, and one linter command
   (`python -m src.learn.lint`) that validates and solves every level, used by tests and by content authors.
5. Shared UI kit look (borders, colours, key hints footer) so seven games feel like one product; follow the blue accent
   (`theme_variables["primary"]`), the dark palette used in chess, plain text (no emoji/icons: the user asked for text-only
   on the chess screens and may want the same elsewhere; confirm before using icons).
6. Performance budget: every keypress must repaint in well under ~30 ms (the user complained about TypeRacer latency before);
   measure with the pilot harness.

### 12.4 Questions to ask the user before or during implementation
- Is a story tone wanted (lore text length), or terse mentors? Any naming preferences for regions (the plan's names are
  placeholders)?
- Languages for Bug Hunt and Code Typing beyond Python/JS/Go/Rust/C/Java/SQL/shell?
- Should progress sync anywhere (the user also has butler/plainphone, which store game bests via `routers/games.py`)? Default:
  local only.
- Icons/emoji: allowed or text only?

### 12.5 Suggested order of the first working session
1. Do 12.1 and 12.3, write `docs/learn-research.md`.
2. Phase 0 (framework + hub) with the existing Vim levels listed under the first region; tests green; commit-ready state.
3. Start Phase 1 (Vim world): prototype one tile level end-to-end, review with the user, then author the rest.
