# Learn to Code: research decisions (session 2026-10-10)

Scope note: this session built all 7 regions as **reduced first passes** in parallel (one fork per
game, after Phase 0 + the Vim prototype were built inline). Full PLAN.md content volume
(~45+48+40+40+(3 cases+45 drills)+70+150 items) is not what's here - each region ships a correct,
tested engine plus a smaller level set (13-30 items depending on the game) sufficient to play the
region start-to-finish. See README.md's "Learn to Code" section for the per-region level counts and
what each one deferred. 269 tests pass (`python -m pytest tests`). Remaining work is filling in
content volume and the explicitly-deferred features per region (listed in README), not new
engineering - the architecture in PLAN.md section 1 held up across all 7 games.

## 12.1 Environment

- `vim`, `nvim`, `git` are all installed (Git for Windows ships vim; standalone nvim at
  `C:\tools\neovim`). `sqlite3` CLI is absent but Python's bundled `sqlite3` module is 3.42.0,
  which has window functions (needs >=3.25) and CTEs. SQL game can rely on the stdlib module only.
- Textual patterns already proven in this repo and reused as-is (no new prototyping needed):
  `Screen.on_key` + `event.stop()` for full key capture (`vimquest.py` `VimQuestScreen.on_key`),
  `Static.update(Text)` for repaint (used for a 25-line buffer already, cheap enough), `OptionList`
  for menus, `self.app.theme_variables["primary"]` for accent colour. These carry over unchanged
  to `learn/`.
- Deferred (not needed for Phase 0/1): `Ctrl-Enter`/`F5` key reporting (SQL game, phase 5),
  `TextArea` vs custom input (shell/SQL, phases 3/5), large tile-map repaint cost at 60x25 (git/shell
  graph phases). Re-check when those phases start.
- Package data: added `tool.setuptools.package-data` for `src.learn` -> `content/**/*` (done
  below, phase 0).

## 12.3 Cross-cutting decisions (settled now, used by Phase 0 code)

1. **Hub layout:** graph of region nodes (not a free-walk ASCII map) — simpler to render reliably
   in Textual and matches "jump around after Apprentice" requirement. `OptionList`-based region
   list with a per-region progress string; walking map deferred to later polish if wanted.
2. **Par/XP/stars:** `stars(actual, par)` = 3 if `actual <= par`, 2 if `actual <= par*1.5`, else 1.
   XP per level = `10 * stars`. Rank ladder: Novice(0) -> Apprentice(100) -> Journeyman(300) ->
   Adept(700) -> Archmage(1500).
3. **config.json schema:** new top-level key `"learn": {"v": 1, "xp": int, "badges": [str],
   "levels": {"<game>:<level_id>": {"stars": int, "best": int}}}`. `vimquest.best` (old key) is
   read once and merged into `learn.levels["vim:training:<i>"]` on first load if `learn` is absent;
   old key is left in place untouched (no destructive migration).
4. **Content format:** Python data (dataclasses) for now, same as existing `vimquest.LEVELS` —
   simplest for Phase 0/1 scope. `levelio.py` still exists as the seam where a JSON/TXT loader can
   replace the Python literals later without touching screens.
5. **UI kit:** plain text, no emoji/icons (matches chess's text-only choice already in this repo).
   Accent colour via `theme_variables["primary"]`, dim grey for meta text — same palette as vimquest.
6. **Performance:** unchanged from vimquest's proven pattern (repaint one `Static.update` per
   keypress); no measured regression expected at this content size.
