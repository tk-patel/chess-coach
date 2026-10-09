# chess-coach — Progress

Read `AGENTS.md` → `PLAN.md` → this file. Update this file at the start and end of every task.

Statuses: `todo` · `in_progress` · `blocked` · `review` (GATE tasks only, waiting for a human or the orchestrator) · `done`

## Current focus
- **Next task:** T2.1 Openings DB
- **Owner decisions needed before M1:** see Open questions Q1–Q3.
- T1.3 is a **GATE**: awaiting a human real-fetch run (sandbox may block api.chess.com).

## Task board

| ID | Task | Deps | Gate | Status | Agent / model | Commit |
|---|---|---|---|---|---|---|
| T0.1 | Scaffold | – | | done | Cody (deepseek-v4-pro) 2026-10-09 | 649a0a6 |
| T0.2 | Config + DB | T0.1 | | done | Cody (deepseek-v4-pro) 2026-10-09 | 5700247 |
| T0.3 | Fixtures | T0.1 | | done | Cody (deepseek-v4-pro) 2026-10-09 | 976e731 |
| T1.1 | Parse PGN + metadata | T0.2, T0.3 | | done | Cody (deepseek-v4-pro) 2026-10-09 | 0325998 |
| T1.2 | PGN import command | T1.1 | | done | Cody (deepseek-v4-pro) 2026-10-09 | 5de8eb3 |
| T1.3 | chess.com fetch | T1.1 | GATE | review | Cody (deepseek-v4.1-flash) 2026-10-09 | e6f046e |
| T2.1 | Openings DB | T0.2 | | todo | | |
| T2.2 | Annotate games with openings | T2.1, T1.2 | | todo | | |
| T3.1 | Engine wrapper | T0.2 | | todo | | |
| T3.2 | Single-game analysis (2 passes) | T3.1, T1.1, T2.2 | | todo | | |
| T3.3 | Batch analysis, workers, resume | T3.2 | | todo | | |
| T3.4 | Benchmark | T3.3 | GATE | todo | | |
| T4.1 | classify.py (pure math) | T0.1 | | todo | | |
| T4.2 | Wire classification into analysis | T4.1, T3.3 | GATE | todo | | |
| T5.1 | Motif detectors + fixtures | T4.1 | | todo | | |
| T5.2 | Wire motifs into analysis | T5.1, T4.2 | | todo | | |
| T6.1 | Puzzle selection + export | T5.2 | GATE | todo | | |
| T7.1 | stats.py | T4.2, T5.2 | | todo | | |
| T7.2 | charts.py | T7.1 | | todo | | |
| T7.3 | Report templates + command | T7.2 | | todo | | |
| T8.1 | Trainer page | T6.1, T7.3 | GATE | todo | | |
| T9.1 | update + status commands | T8.1 | | todo | | |
| T9.2 | Home-server setup docs | T9.1 | GATE (final) | todo | | |

Tasks that can run in parallel once their deps are done: T2.1, T3.1 and T4.1 depend only on
the foundation and are good tasks for trying different models side by side.

## Open questions (owner answers here)
- **Q1** chess.com username → goes in `config.toml` (never commit it). Answer:
- **Q2** Which time classes count? Default: bullet, blitz, rapid, daily. Answer:
- **Q3** Where will analysis run? Default: the Ubuntu home server; note its CPU core count for `workers`. Answer:

## Decisions log
`D<n> | date | task | decision | reason`
- D0 | 2026-10-09 | plan | Lichess-style win%/accuracy, not chess.com CAPS | Published formula, reproducible
- D1 | 2026-10-09 | plan | Static HTML + localStorage trainer, no server in v1 | Zero ops; export/import covers device moves
- D2 | 2026-10-09 | plan | Two-pass engine analysis (d14 all plies, d18 multipv3 on candidates) | ~5–10× cheaper than deep analysis on every ply
- D3 | 2026-10-09 | T0.3 | Fixtures use well-known public games (Opera, Legall's, Fool's, Hamppe–Meitner, Scholar's, Blackburne Shilling); %clk comments, Elo, dates, ECO URLs and termination headers are synthesized for test coverage | Historical games have no clocks/ratings and no chess.com-style headers; no human-supplied exports were available

## Blockers
(none yet)

## Benchmarks (filled by T3.4)
| Date | Machine / CPU | Workers | pass1/pass2 depth | Games | Avg s/game | Notes |
|---|---|---|---|---|---|---|

## Agent scorecard (owner/orchestrator fills at review)
Use this table to compare models (GLM, Claude, others) on the same kind of work.

| Task | Agent / model | First-try pass at gate? | Spec deviations | Bugs found in review | Honest handoff? | Notes |
|---|---|---|---|---|---|---|

## Backlog / discovered work
(agents append here instead of doing out-of-scope work)

## Handoff notes
(newest at top; use the template in AGENTS.md §5)

### T1.3 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: review (GATE — needs a human real-fetch run)
Commit: e6f046e
What changed:
- src/chesscoach/fetch.py: `Transport`/`RequestsTransport` (all HTTP behind an injectable interface), `fetch_archive_list`, `_get_with_retry` (429 backoff 1/2/4/8/16, max 5), `fetch_all` (incremental: past months skipped once stored, newest month always re-fetched, ETag/Last-Modified → 304 short-circuit, raw JSON saved to `data/raw/{YYYY}-{MM}.json` before parse), `_insert_month` applying the §7.1 filters (rules, time_classes, rated_only, user present).
- src/chesscoach/cli.py: `fetch` wired to load config, require the username, migrate, and run the real `RequestsTransport`.
- tests/test_fetch.py: fake `Transport`; second-run-requests-only-newest-month, 429-then-200, rule/time-class filtering, archive-list error.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q` → "54 passed in 0.35s" (4 new fetch tests included)
Deviations from PLAN: none
Known issues / follow-ups: GATE not closed — must run `python -m chesscoach fetch` on a machine with api.chess.com reachable and record the real inserted count.
Next task: T2.1 (Openings DB)

### T1.2 handoff — Cody (deepseek-v4-pro) — 2026-10-09
Status: done
Commit: 5de8eb3
What changed:
- src/chesscoach/importer.py: `compute_uuid` (sha1 of sorted headers + UCI movetext) and `import_pgn_file` (idempotent; skips games without the user and already-imported games).
- src/chesscoach/cli.py: `import` command wired to load config, require the username, migrate, and import.
- tests/test_importer.py + test_cli.py: idempotency, metadata, user filtering, uuid stability, and CLI end-to-end.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q` → "50 passed in 0.34s"
- `python -m chesscoach import sample_games.pgn` run twice: run 1 "imported 1 games, 5 without user", run 2 "imported 0 games, skipped 1 existing"; DB holds 1 game / 33 moves both times.
Deviations from PLAN: none
Known issues / follow-ups: none
Next task: T1.3 (chess.com fetch) — GATE

### T1.1 handoff — Cody (deepseek-v4-pro) — 2026-10-09
Status: done
Commit: 0325998
What changed:
- src/chesscoach/parse.py: pure PGN parsing. `parse_time_control`, `result_code_to_result` (§7.1), `user_result_from_pgn`, `detect_user_color` (case-insensitive), `time_class_from_control`, `parse_end_time`, and `parse_game` -> `ParsedGame` + `ParsedMove` (ply/color/is_user/san/uci/fen_before/clock_after/time_spent per §8.6).
- tests/test_parse.py: unit tests for time controls, every §7.1 result code, increment-aware time_spent, color detection, and full-game parsing against the fixtures.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q` → "44 passed in 0.23s"
Deviations from PLAN: none
Known issues / follow-ups: none
Next task: T1.2 (PGN import command)

### T0.3 handoff — Cody (deepseek-v4-pro) — 2026-10-09
Status: done
Commit: 976e731
What changed:
- tests/fixtures/sample_games.pgn: 6 real games (Opera, Legall's, Fool's, Hamppe–Meitner draw, Scholar's, Blackburne Shilling timeout) with %clk comments; covers win/loss/draw/timeout/daily.
- tests/fixtures/sample_archive.json: chess.com-shaped monthly response (3 games).
- tests/test_fixtures.py: parses every game with zero errors, checks results/termination/time-control coverage, clock readability, and archive shape.
How I verified:
- Fixtures generated by replaying hand-written UCI move lists through python-chess (every move validated legal; illegal-move typos in Opera/Scholar/Blackburne lines were caught and fixed during generation).
- `ruff check .` → "All checks passed!"
- `pytest -q` → "17 passed in 0.17s"
Deviations from PLAN: none (see D3 for synthesized clocks/metadata rationale)
Known issues / follow-ups: none
Next task: T1.1 (Parse PGN + metadata)

### T0.2 handoff — Cody (deepseek-v4-pro) — 2026-10-09
Status: done
Commit: 5700247
What changed:
- src/chesscoach/config.py: nested dataclasses for all §5 sections; `load_config` parses/validates; `require_username`/`require_engine` fail loudly on placeholders / missing binaries.
- src/chesscoach/db.py: `connect` (FK on, Row factory), `migrate` (versioned, idempotent), `SCHEMA_VERSION=1`, full §6 schema + 2 indexes.
- src/chesscoach/cli.py: `init` wired to create data/, data/raw/, data/openings/, out/, the DB, and copy config.example.toml → config.toml.
- tests/test_config.py, test_db.py, test_cli.py: config validation, schema, and init end-to-end.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q` → "12 passed in 0.11s"
- `python -m chesscoach init` in a scratch dir → created config.toml, data/chesscoach.db (schema v1), tables `archives, games, meta, moves, puzzles`.
Deviations from PLAN: none
Known issues / follow-ups: none
Next task: T0.3 (Fixtures)

### T0.1 handoff — Cody (deepseek-v4-pro) — 2026-10-09
Status: done
Commit: 649a0a6
What changed:
- pyproject.toml: project metadata, deps (python-chess, requests, typer, jinja2, matplotlib), dev extras (pytest, ruff), ruff + pytest config with the `engine` marker.
- .gitignore: .venv/ data/ out/ config.toml __pycache__/ and tooling caches.
- README.md: short install + run instructions.
- config.example.toml: full §5 config.
- src/chesscoach/__init__.py, __main__.py, cli.py: typer app with all §13 commands as stubs.
- tests/test_cli.py: smoke tests for the help surface and stub exit codes.
How I verified:
- `pip install -e .[dev]` in a fresh `.venv` (python 3.11.16) → exit 0.
- `ruff check .` → "All checks passed!"
- `pytest -q` → "2 passed in 0.09s"
- `python -m chesscoach --help` → lists init, status, fetch, import, analyze, puzzles, report, update, openings.
Deviations from PLAN: none
Known issues / follow-ups: none
Next task: T0.2 (Config + DB)
