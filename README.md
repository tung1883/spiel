# spiel

TypeRacer and chess in the terminal (Python + Textual).

    pip install -e .
    spiel                # or: python -m src

## TypeRacer
Real typeracer.com races as a guest (public races, practice, quote of the day).
Unofficial: talks to `POST /api/action` using the site's binary action encoding
and TLv1 keylog format (`typeracer/wire.py`, `typeracer/keylog.py`). It may break
whenever the site changes. The server validates keylog timing, so only real typing is accepted.
Keys: type the text, Backspace, Esc leave, Enter new race after finishing.

The **TypeRacer** row starts a race at once with your saved settings (defaults: online, race, English). Change them under
**Settings** (hotkey `s` in the menu, `ctrl+s` anywhere; also holds the chess opponent/level; vim-style list: `j/k` move, `h/l`/Enter change, saved automatically in `config.json`):
- **Connection**: online (typeracer.com) or offline (10 built-in + cached quotes, no countdown - the timer starts at your first key).
- **Mode** (online): race live opponents, solo practice, or quote of the day.
- **Instant death**: first wrong key ends the race (online on English = the site's own `accuracy` universe, else enforced
  client-side with the `fail` action; also works offline).
- **Text / language** (online): English quotes, Dictionary, Numbers, Repeating words, Coder edition, or ~40 languages
  (es fr de it pt ru pl nl sv da no fi cs sk hu ro bg el tr uk hr sr sl lt lv et ca vi id ms tl hi af ga cy mk be + 2 dictionaries;
  CJK/Thai/RTL omitted - they need IME/shaping). Small universes may leave you waiting for opponents; use practice.
Offline practice has no countdown: the timer starts at your first key. After every race (and when you die) you get
analytics: net/raw WPM, accuracy, consistency, errors, backspaces, a speed-over-time sparkline, fastest/slowest words,
most-missed keys, and your best / recent average per mode (history in `%APPDATA%\spiel\typeracer-history.json`).

## Chess
- **Lichess**: full play via the official Board API. Needs a token with `board:play`
  (+ `challenge:write` for Stockfish games): set `LICHESS_TOKEN` or paste it in the menu.
  Text only, no board: type a move (SAN like `Nf3` or UCI like `e2e4`) and Enter, or a command: `resign`, `draw`, `abort`, `back` (Esc also leaves).
  Promotion is always to queen (type the move with `m` for others, e.g. `e7e8n`).
- **Chess.com**: live games (10 min, 5 min, 3+2, 15+10) run with **no browser at all**: plain HTTP for matchmaking plus
  chess.com's RSocket/WebSocket game protocol (reverse-engineered, see `docs/chesscom-protocol.md`). Password login
  is behind a Cloudflare Turnstile bot check, so the first time you paste one cookie (`CHESSCOM_REMEMBERME`, from your
  own browser's dev tools) into the TUI; it mints fresh session cookies over HTTP and renews them itself. Saved in
  `%APPDATA%\spiel\chesscom-session.json` (`l` in the Chess.com menu logs out).
  Games are **unrated** unless `TUI_GAMES_CHESSCOM_RATED=1`. Same text commands as Lichess; resign, abort and draw offers work,
  promotion codec checked offline only. Chess.com bots run client-side in the website (no network protocol), so
  there is no "play a bot" here - use the offline computer. Unofficial: can break when chess.com changes, and may be against its terms.
  Also has a read-only viewer for any user's daily games (public API).

## Offline
- **TypeRacer offline** (Settings: connection = offline): random texts from a local cache, per text/language (`%APPDATA%\spiel\quotes.json`),
  filled by every text you see online; English also has 10 built-in quotes. A language with nothing cached shows an error
  with a hint. Seed more: `python -c "import asyncio; from src.typeracer.local import fetch_quotes; print(asyncio.run(fetch_quotes(100, universe='lang_de')))"`.
- **Chess** is one row; Settings picks offline / Lichess / Chess.com and the offline level.
- **Chess offline vs computer** (easy/medium/hard): you play White. Uses Stockfish if `STOCKFISH_PATH`
  is set or `stockfish` is on PATH (strongly recommended); otherwise a weak built-in search engine.

## Minesweeper
Ported from `butler-web` (expert only: 16x30, 99 mines; first-click-safe, chording).
- Minesweeper: arrows/hjkl move, Space reveal (or chord on a number), `f` flag, `n` new; mouse left/right click works. Best times are saved.

## Sudoku
Also ported from `butler-web` (`..\butler\butler-web\src\games\sudoku\`): the same 2000-puzzle bank
(4 variants x 5 difficulties x 100 real curated puzzles, not runtime-generated), the same
resume/undo/hint/pencil-mark/best-time rules, re-done for a keyboard-only terminal board
(`src/sudoku/`).
- **Variants**: Classic (regular 3x3 boxes), Jigsaw (irregular region shapes - same border-detection
  code path as Classic, just different regions), Cross (adds both main diagonals as extra regions),
  Inequality/Futoshiki-style (`>`/`<` arrows between cells; rows/columns only, no box constraint -
  the source app's own puzzle data doesn't actually satisfy one, so the box-conflict check is
  skipped for this variant rather than flagging a correctly solved board, see `bank.py`).
- Board: menu `left`/`right` picks the variant, `[`/`]` the difficulty, the puzzle list is a normal
  `OptionList` (up/down/enter). In a puzzle: arrows/hjkl move the selection, `1`-`9` enters a digit,
  `n` toggles pencil-mark notes, `e`/Backspace/Delete erases, `u` undoes, `?` reveals the selected
  cell (a free hint), `q` leaves (progress saves after every edit, so leaving mid-puzzle resumes
  exactly where you left off). Conflicting digits (row/column/region/diagonal/inequality) highlight
  red live. Best time per variant+difficulty is tracked.
- Tests: `python -m pytest tests/test_sudoku.py tests/test_sudoku_hub.py` - every solved grid in the
  bank is checked against its actual constraint set (rows/cols/boxes or rows/cols/inequalities),
  every given clue matches the solution, engine edit/undo/hint/conflict rules, progress persistence,
  and a `Pilot`-driven full solve of a real puzzle through the real screen.

## 2048
Original implementation of the classic sliding-tile merge puzzle (`src/games/game2048.py`) -
the slide/merge/spawn rules are a generic, widely-reimplemented mechanic; no code or assets taken
from anywhere. Arrows/hjkl slide all four tiles at once (standard rules: equal adjacent tiles merge
once per move, no cascading re-merge), `n` starts a new game, `q` leaves. Best score saved.
Tests: `python -m pytest tests/test_game2048.py` - the compress/merge algorithm against hand-worked
cases (including the no-cascade rule), move/no-move detection, game-over detection, reaching 2048.

## Git Trivia
A 10-question multiple-choice quiz inside Branch Forest (`src/learn/git/trivia.py`,
`TriviaScreen` in `screens.py`) - a lighter, faster companion to the hands-on levels: commands,
undo semantics, rebase vs merge, reflog, bisect, blame. All questions are original, written for
this repo. Press `1`-`4` to answer, space/enter for the next question, `escape` to leave. Best
score saved. Tests: `python -m pytest tests/learn/git/test_trivia.py
tests/learn/git/test_trivia_pilot.py`.

## Ghost

Every finished race saves your best run per text (`typeracer-ghosts.json`). When that text shows up again, a magenta ghost bar replays it. After a race press `r` to replay the same text against the ghost (solo), `Enter` for a new race.

## Chess look

A compact text board (capital = white, lowercase = black, one row per rank) on a dark slate palette, next to four
boxes laid out like [chess-tui](https://github.com/thomas-mauran/chess-tui) (MIT): opponent (name, clock, captured
pieces), move history, you, and the status line. The last move is green; the input at the bottom takes your move.

## Learn to Code

"Learn to Code" on the main menu opens an overworld hub (`src/learn/`): a rank/XP banner plus a list of
six regions, one per `src/learn/<game>/` package. Progress (XP, stars, per-level bests) is saved under
`config.json`'s `"learn"` key via `src/learn/progress.py`. See `docs/learn-research.md` for the schema and
design decisions, and `PLAN.md` for the full plan - every region is still a **reduced pass** of its PLAN.md
section (full target level/snippet counts are larger still), but each now has real mechanics and real
consequences, not a one-shot trivial action per level. Each region's deferred list is below.

- **Pattern Marsh** (`learn/regex/`) - 30 levels across three modes: **golf** (must-match/must-not-match lists,
  score = pattern length vs par), **extract** (match exactly the labeled target substrings - teaches
  groups/anchors), **substitute** (pattern + replacement turn before-text into after-text, backreferences,
  greedy vs lazy). A plain-English explainer under the input, timeout guard against catastrophic backtracking.
  Deferred: regex-crossword mode, daily challenge.
- **Branch Forest** (`learn/git/`) - an in-memory git simulation with **real file content** per commit and a
  **real line-based 3-way merge**: overlapping edits produce genuine `<<<<<<<`/`=======`/`>>>>>>>` conflict
  markers you resolve by hand (ours/theirs/both, or editing the markers directly), not an abstract tag check.
  18 levels, 4 requiring a real conflict resolution (merge, rebase, and cherry-pick can each genuinely
  conflict), ending in an incident boss that chains a conflict resolve with a history scrub. Deferred: bisect,
  stash, remote/collab missions, full interactive-rebase todo-list UI.
- **Terminal Caverns** (`learn/shell/`) - a fake POSIX-ish machine entirely in memory (fs, parser, coreutils-
  style commands plus `$(cmd)` substitution, `awk '{print $N}'`, `sed 's/a/b/'`), nothing touches the real OS.
  21 missions, including a 4-part "Final Incident" arc: find a rogue process, trace the cron file calling out
  to it, rank the attacker's IP with a grep|awk|sort|uniq pipeline, then write the report by substituting in
  both prior answers. Deferred: for/if loops, tab completion, command history.
- **Archive of Queries** (`learn/sql/`) - stdlib `sqlite3` in memory, read-only enforced (`query_only` +
  authorizer + timeout + row cap) outside the DML/DDL drills (which run on a throwaway copy). 3 cases (19
  steps total, each a real clue chain where one query's result feeds the next step) + 24 drills, SELECT
  through window functions and a transaction/rollback demo. `f3` shows Explain mode: `EXPLAIN QUERY PLAN`
  translated to plain English. Deferred: schema explorer/ER sketch.
- **Bug Swamp** (`learn/bughunt/`) - hunt the buggy line, fix it (verified by a hidden test in a sandboxed
  subprocess: `python -I -S`, temp cwd, hard timeout), then **Diagnose**: pick the bug's class from a list. `t`
  opens a real sandboxed step-through **tracer** (`sys.settrace` inside the same subprocess, step
  forward/back through recorded locals - capped at 500 steps / 120-char reprs so a hostile snippet can't blow
  it up). 30 original Python snippets, beginner through expert, no bug class repeated more than twice.
  Deferred: Review mode, multi-language display-only entries.
- **Typing Forge** (`learn/codetype/`) - TypeRacer for code, reusing `typeracer/analytics.py`'s `RaceStats`.
  Four modes: **Snippet** (character-accurate, auto-indent-skip on Enter), **Recall** (memorize then type from
  a masked buffer), **Explain-then-type** (one-line "what does this do?" quiz first), **Boss** (a full
  15-30 line program under a visible timer) - plus a **Symbols drill** built from your own missed characters
  after any run. 55 original snippets (50 + 5 boss programs) across Python/JS/Go/Rust/SQL. Deferred: full
  150-snippet/10-language target, cross-session symbol heatmap.

Every region: `q` back to its menu, `?`/hint key for a nudge, a reference solution per level checked by tests,
progress saved via `progress.record(game, level_id, actual, par)`.

Tests: `python -m pytest tests` (400 passing) - every level/mission/drill/snippet has a reference solution
verified against the real engine, plus a `Pilot`-driven playthrough per region from the main menu to a result
screen.
