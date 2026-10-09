# chess-coach — Progress

Read `AGENTS.md` → `PLAN.md` → this file. Update this file at the start and end of every task.

Statuses: `todo` · `in_progress` · `blocked` · `review` (GATE tasks only, waiting for a human or the orchestrator) · `done`

## Current focus
- **Next task:** T0.1 Scaffold
- **Owner decisions needed before M1:** see Open questions Q1–Q3.

## Task board

| ID | Task | Deps | Gate | Status | Agent / model | Commit |
|---|---|---|---|---|---|---|
| T0.1 | Scaffold | – | | done | Cody (deepseek-v4-pro) 2026-10-09 | |
| T0.2 | Config + DB | T0.1 | | todo | | |
| T0.3 | Fixtures | T0.1 | | todo | | |
| T1.1 | Parse PGN + metadata | T0.2, T0.3 | | todo | | |
| T1.2 | PGN import command | T1.1 | | todo | | |
| T1.3 | chess.com fetch | T1.1 | GATE | todo | | |
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

### T0.1 handoff — Cody (deepseek-v4-pro) — 2026-10-09
Status: done
Commit: (below)
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
