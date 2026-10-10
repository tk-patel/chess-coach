# chess-coach — Progress

Read `AGENTS.md` → `PLAN.md` → this file. Update this file at the start and end of every task.

Statuses: `todo` · `in_progress` · `blocked` · `review` (GATE tasks only, waiting for a human or the orchestrator) · `done`

## Current focus
- **All tasks implemented.** GATEs awaiting owner review: T1.3, T3.4, T4.2, T6.1, T8.1, T9.2 (final).

## Task board

| ID | Task | Deps | Gate | Status | Agent / model | Commit |
|---|---|---|---|---|---|---|
| T0.1 | Scaffold | – | | done | Cody (deepseek-v4-pro) 2026-10-09 | 649a0a6 |
| T0.2 | Config + DB | T0.1 | | done | Cody (deepseek-v4-pro) 2026-10-09 | 5700247 |
| T0.3 | Fixtures | T0.1 | | done | Cody (deepseek-v4-pro) 2026-10-09 | 976e731 |
| T1.1 | Parse PGN + metadata | T0.2, T0.3 | | done | Cody (deepseek-v4-pro) 2026-10-09 | 0325998 |
| T1.2 | PGN import command | T1.1 | | done | Cody (deepseek-v4-pro) 2026-10-09 | 5de8eb3 |
| T1.3 | chess.com fetch | T1.1 | GATE | review | Cody (deepseek-v4.1-flash) 2026-10-09 | e6f046e |
| T2.1 | Openings DB | T0.2 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | cd06fdf |
| T2.2 | Annotate games with openings | T2.1, T1.2 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | fcad03a |
| T3.1 | Engine wrapper | T0.2 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | 3a8f0b5 |
| T3.2 | Single-game analysis (2 passes) | T3.1, T1.1, T2.2 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | 17b712b |
| T3.3 | Batch analysis, workers, resume | T3.2 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | 7b2d0e2 |
| T3.4 | Benchmark | T3.3 | GATE | review | Cody (deepseek-v4.1-flash) 2026-10-09 | 667e9c2 |
| T4.1 | classify.py (pure math) | T0.1 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | bee4581 |
| T4.2 | Wire classification into analysis | T4.1, T3.3 | GATE | review | Cody (deepseek-v4.1-flash) 2026-10-09 | b59ce8a |
| T5.1 | Motif detectors + fixtures | T4.1 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | 55f0536 |
| T5.2 | Wire motifs into analysis | T5.1, T4.2 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | 963b801 |
| T6.1 | Puzzle selection + export | T5.2 | GATE | review | Cody (deepseek-v4.1-flash) 2026-10-09 | 659083d |
| T7.1 | stats.py | T4.2, T5.2 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | cb55d3d |
| T7.2 | charts.py | T7.1 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | b71a68c |
| T7.3 | Report templates + command | T7.2 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | 9eee03d |
| T8.1 | Trainer page | T6.1, T7.3 | GATE | review | Cody (deepseek-v4.1-flash) 2026-10-09 | 661ef8e |
| T9.1 | update + status commands | T8.1 | | done | Cody (deepseek-v4.1-flash) 2026-10-09 | cf52d86 |
| T9.2 | Home-server setup docs | T9.1 | GATE (final) | review | Cody (deepseek-v4.1-flash) 2026-10-09 | 1ec56c0 |

Tasks that can run in parallel once their deps are done: T2.1, T3.1 and T4.1 depend only on
the foundation and are good tasks for trying different models side by side.

## Open questions (owner answers here)
- **Q1** chess.com username → goes in `config.toml` (never commit it). Answer: **set** (config.toml, gitignored)
- **Q2** Which time classes count? Default: bullet, blitz, rapid, daily. Answer:
- **Q3** Where will analysis run? Default: the Ubuntu home server; note its CPU core count for `workers`. Answer:

## Decisions log
`D<n> | date | task | decision | reason`
- D0 | 2026-10-09 | plan | Lichess-style win%/accuracy, not chess.com CAPS | Published formula, reproducible
- D1 | 2026-10-09 | plan | Static HTML + localStorage trainer, no server in v1 | Zero ops; export/import covers device moves
- D2 | 2026-10-09 | plan | Two-pass engine analysis (d14 all plies, d18 multipv3 on candidates) | ~5–10× cheaper than deep analysis on every ply
- D3 | 2026-10-09 | T0.3 | Fixtures use well-known public games (Opera, Legall's, Fool's, Hamppe–Meitner, Scholar's, Blackburne Shilling); %clk comments, Elo, dates, ECO URLs and termination headers are synthesized for test coverage | Historical games have no clocks/ratings and no chess.com-style headers; no human-supplied exports were available
- D4 | 2026-10-09 | T2.1 | ECOUrl-slug fallback expands hyphens naively (`Caro-Kann-Defense-Advance-Variation` → `Caro Kann Defense Advance Variation`), losing the internal hyphen of "Caro-Kann" | The slug is lossy (colons and intra-word hyphens are indistinguishable); PLAN §7.2's example output is not recoverable from the slug. Fallback only used when the TSVs are absent; the T2.1 AC (EPD path) is unaffected
- D5 | 2026-10-09 | T3.2 | Implement classify.py (T4.1) before analyze.py (T3.2), i.e. slightly out of board order | T3.2 stores win_before/win_after/win_drop (§8.2/8.3) which are the canonical classify.py math; doing T4.1 first avoids duplicating the win% formula. T4.1's only dep (T0.1) is already done

## Blockers
(none yet)

## Benchmarks (filled by T3.4)
| Date | Machine / CPU | Workers | pass1/pass2 depth | Games | Avg s/game | Notes |
|---|---|---|---|---|---|---|
| 2026-10-09 | Intel i7-7700K (8 threads), Linux | 1 (per-worker; config workers=4) | 14/18 (multipv 3) | 6 fixture games | 3.65 (median 3.83, max 7.60, total 21.9s) | Stockfish 17.1, 128 MB hash; user synthesised as each game's White so pass 2 fires. Target ≤15 s/game met with ~4× headroom |

## Agent scorecard (owner/orchestrator fills at review)
Use this table to compare models (GLM, Claude, others) on the same kind of work.

| Task | Agent / model | First-try pass at gate? | Spec deviations | Bugs found in review | Honest handoff? | Notes |
|---|---|---|---|---|---|---|

## Backlog / discovered work
(agents append here instead of doing out-of-scope work)

## Handoff notes
(newest at top; use the template in AGENTS.md §5)

### T9.2 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: review (GATE, final)
Commit: 1ec56c0
What changed:
- README.md: full "Home-server setup (Ubuntu, from scratch)" — apt packages (python3.11/venv, stockfish, git), clone + venv + `pip install -e .`, `init` + config notes (username, workers = cores-1), `openings download` (+ manual fallback), first `fetch`/`import`, `analyze`/`puzzles`/`report`; a nightly **cron** line using the venv's absolute python; **serving `out/` on the LAN** via `python -m http.server`, nginx and Caddy snippets; a **backup** section (`sqlite3 .backup` of `data/chesscoach.db` + restore); a command-reference table and notes (lichess-style accuracy, heuristic motifs, never commit config/data/out, never enter the chess.com password).
How I verified (from-scratch recipe executed end to end in an empty dir /tmp/fresh):
- `init` -> `openings download` (5 files) -> `import sample_games.pgn` -> `analyze --limit 1` (Stockfish 17.1, 4.5s) -> `puzzles` -> `report` (5 pages) -> `status` (games 1/done 1, puzzles 0, last fetch never, engine Stockfish 17.1). All exit 0.
- LAN serve: `http.server 8099 -d out` -> `curl /` = 200, `curl /trainer.html` = 200, `<title>Overview — chess-coach</title>`.
Deviations from PLAN: none
Known issues / follow-ups: GATE (final) — the owner should follow the README once on the actual home server. `<your-repo-url>` in the README is a placeholder to fill with the real remote.
Next task: none — backlog only.

### T9.1 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: cf52d86
What changed:
- src/chesscoach/cli.py: real `status` (games by analysis_status, puzzles, last fetch time, engine id) and `update` (fetch → analyze → puzzles → report, each step best-effort so cron never dies on a blocked network). Removed the now-unused `_stub` helper; added the datetime import.
- tests/test_cli.py: `status` and offline `update` tests (fetch transport stubbed to 404 → "fetch skipped", report pages written).
How I verified:
- `ruff check .` → "All checks passed!"; `pytest -q` → "211 passed in 22.76s".
- Scratch e2e: `status` → games 1 / done 1 / puzzles 1 / last fetch never / engine Stockfish 17.1. `update` (username temporarily CHANGE_ME) → "fetch skipped … / analyze: 0 games / update done: 0 analyzed, 1 puzzles, 5 pages".
Deviations from PLAN: none
Known issues / follow-ups: none
Next task: T9.2 (Home-server setup docs, final GATE)

### T8.1 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: review (GATE)
Commit: 661ef8e
What changed:
- src/chesscoach/templates/trainer.html: self-contained page (inline CSS + JS, no external assets). Puzzle JSON inlined in `<script type="application/json" id="puzzles">`. 8x8 SVG board with Unicode glyphs, oriented to the user's colour, edge coordinates; click-piece-then-square with a Q/R/B/N promotion chooser; guesses checked by UCI string compare against `accepted` (no JS legality engine). Shows solution_san / line_san / motifs / opening / date / game link after solving. Leitner boxes 1–5 (intervals 0/1/3/7/21 d), state in localStorage `chesscoach.srs.v1` (guarded try/catch); correct-first-try → box+1, wrong/revealed → box 1. Queue = due (box asc, oldest due first) then new (largest win_drop). Filters: motif / phase / low_clock / time window; `#motif=<tag>` hash; Export/Import progress buttons.
- src/chesscoach/report.py: `render_report` now also renders `trainer.html` from the live DB (`select_puzzles`), so it stays in sync. Report now writes 5 pages.
- tests/test_report.py updated to 5 pages; tests/test_trainer.py: JSON inlined + parses to the documented shape, no external assets, empty-queue case.
How I verified:
- `ruff check .` → "All checks passed!"; `pytest -q` → "209 passed in 17.95s".
- Scratch e2e `python -m chesscoach report` → "wrote 5 pages"; trainer inlines 1 puzzle (`id 5a0e5a803896`).
- `node --check` on the extracted trainer JS → "JS SYNTAX OK".
- Headless DOM-shim run of the trainer init path (node) → "board squares: 64, board glyphs: 32, status: 'White to move — find the best move.', queue: 1 new". No runtime errors.
- NO browser in this environment, so the interactive click test was NOT performed — GATE manual script below.

GATE manual test script (owner, in a browser):
1. `python -m chesscoach report`, open `out/trainer.html` via file://.
2. Solve a puzzle correctly on the first try → status shows "Correct! Box N"; reload → the puzzle does not reappear as new and its box persisted.
3. Fail one (wrong first move) → "Not quite …" then Reveal → status "back to box 1".
4. Reveal another → box resets. Reload → state persists.
5. Export progress (downloads `chesscoach-srs.json`); clear site data; Import that file → boxes/due restored.
6. Open `trainer.html#motif=hung_piece` → the motif filter pre-selects.
7. Narrow the window to 375 px → board fills the width, controls wrap under it.
Deviations from PLAN: none
Known issues / follow-ups: interactive behaviours are validated by JS syntax + headless init only (no browser here); the owner's step 2–7 closes the GATE.
Next task: T9.1 (update + status commands)

### T7.3 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: 9eee03d
What changed:
- src/chesscoach/report.py: `render_report` (Jinja2, 4 pages), `report_meta` (engine/depths/generation time for the footer), `build_charts`.
- src/chesscoach/templates/: base.html (light/dark via prefers-color-scheme, system font stack, responsive, no external assets) + overview.html, mistakes.html, openings.html (Wilson CI, small-sample greying, expandable variations), games.html (plain-JS column sort).
- src/chesscoach/cli.py: `report` command wired end-to-end.
- pyproject.toml: `templates/*.html` as package data.
How I verified:
- `ruff check .` → "All checks passed!"; `pytest -q` → "206 passed in 17.16s" (4 report tests).
- Scratch e2e `python -m chesscoach report` → "wrote 4 pages"; every `src=`/`href=` http reference is absent or a chess.com game link (grep found none in this scratch game).
Deviations from PLAN: none
Known issues / follow-ups: the visual check at 375/1280 px was NOT done — no browser is available in this environment (the plan permits skipping when no browser is present). Trainer nav link 404s until T8.1.
Next task: T8.1 (Trainer page, GATE)

### T7.2 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: b71a68c
What changed:
- src/chesscoach/charts.py: generic `bar_chart`, `grouped_bar`, `line_chart`, `multi_line_chart` + report wrappers `rating_charts`, `accuracy_chart`, `phase_chart`, `clock_chart`, `motif_chart`, `time_chart`. Transparent background, neutral-grey text so charts read on light and dark themes; consistent palette.
- tests/test_charts.py: every chart returns inline SVG; empty data returns a graceful "no data" SVG; no external image/URL references.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q tests/test_charts.py` → "5 passed in 1.00s"
Deviations from PLAN: none
Known issues / follow-ups: none
Next task: T7.3 (Report templates + command)

### T7.1 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: cb55d3d
What changed:
- src/chesscoach/stats.py: `wilson_ci`; `basic_counts` (W/D/L overall/by color/by time class + score%), `rating_over_time`, `accuracy_over_time` (rolling 20-game mean), `blunder_rate_by_phase`, `blunder_rate_by_clock`, `motif_counts`, `time_vs_blunders`, `top_costly_moves` (20), `conversion_stats` (§8.8 failed conversions/100), `openings_table` (family + variation level, Wilson CI, median theory-exit), `games_table`, `top_issues` (≤5 ranked bullets), and `build_stats`.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q tests/test_stats.py` → "9 passed in 0.07s"; full suite "197 passed in 15.33s".
- Hand-computed checks: Wilson CI (5/10 → 0.237–0.763; 0/10 → 0.000–0.278); phase blunder rates 25.0 / 100.0 / n-a; conversion 1/2 → 50.0; opening family avg accuracy 75.0.
Deviations from PLAN: none
Known issues / follow-ups: none
Next task: T7.2 (charts.py)

### T6.1 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: review (GATE)
Commit: 659083d
What changed:
- src/chesscoach/puzzles.py: `select_puzzles` (all §11 rules 1–6), `strip_internal` (documented export shape), `store_puzzles` (replaces the `puzzles` table), `export_puzzles`, `rebuild`; helpers `_puzzle_id` (sha1(EPD+solution)[:12]), `_line_san` (≤6 plies), `_date`, `_played_san`.
- src/chesscoach/cli.py: `puzzles` command wired end-to-end.
- tests/test_puzzles.py: each selection rule (min_drop, min_best_winpct, multipv required, played-accepted exclusion, multi_answer), dedupe (kept newest + seen_count), export shape/order, DB store.
- tests/test_cli.py: `puzzles` CLI smoke test.
How I verified:
- `ruff check .` → "All checks passed!"; `pytest -q` → "188 passed in 15.08s".
- Scratch e2e `python -m chesscoach puzzles` on the analyzed user game → `built 1 puzzles`; out/puzzles.json has 1 record with the documented keys, `played_san "g4??"`, `accepted ["b1c3","e2e3","e2e4"]` (all within 3 win%), `solution_san "Nc3"`, `line_san "Nc3 Nc6 e4 Nf6 Bc4 Nd4"`, `motifs ["allowed_mate"]`, `multi_answer true`. The played move is not in `accepted`.
Deviations from PLAN: exported JSON omits an internal `solution_uci` key to match the documented §11 shape exactly (kept in the DB table).
Known issues / follow-ups: GATE — orchestrator sanity-check on real games.
Next task: T7.1 (stats.py)

### T5.2 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: 963b801
What changed:
- src/chesscoach/analyze.py: `AnalyzedMove.motifs_json` field; pass 2 now captures the post-move PV as `reply_pv` and calls `detect_motifs` for user moves classified inaccuracy/mistake/blunder (§10). Only those qualify.
- tests/test_analyze.py: every inaccuracy-or-worse user move has a non-empty motifs list; opponent plies have none.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q tests/test_analyze.py` → "5 passed in 13.83s"
- Scratch e2e (`analyze --reanalyze`) on a user game: `1. f3 → ["positional"]` (inaccuracy), `2. g4 → ["allowed_mate"]` (blunder, mate in 1 next), `2...e5 → NULL`. Tags make chess sense.
Deviations from PLAN: none
Known issues / follow-ups: heuristics (labelled in UI later).
Next task: T6.1 (Puzzle selection + export, GATE)

### T5.1 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: 55f0536
What changed:
- src/chesscoach/motifs.py: `detect_motifs(board_before, played_uci, best_pv, reply_pv, mate_before, mate_after, low_clock)` implementing all §10 tags (allowed/missed mate, back_rank, hung_piece, allowed/missed fork, allowed_pin, missed_capture, promotion, low_clock, positional fallback). Pure; helpers `_play_delta`, `_is_fork`, `_pinned_big_pieces`, `_back_rank_mate`.
- tests/fixtures/positions.json: 33 hand-crafted cases — every tag has ≥2 positive + ≥1 negative; generated by replaying UCI move lists through python-chess so every FEN/move is legal.
- tests/test_motifs.py: fixture coverage assertion, per-case validity (FEN + move legality), per-case expectation, determinism, positional fallback.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q tests/test_motifs.py` → "70 passed in 0.09s"; full suite "175 passed in 13.54s".
Deviations from PLAN: none
Known issues / follow-ups: heuristics, as the plan requires them to be labelled. Fixture lines are hand-built to exercise each rule, not engine-verified (the §10 tests must not need Stockfish).
Next task: T5.2 (Wire motifs into analysis)

### T4.2 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: review (GATE)
Commit: b59ce8a
What changed:
- src/chesscoach/analyze.py: `game_totals` + `_side_accuracy`; `run_batch` now stores `user_accuracy`, `opp_accuracy`, `max_user_winpct`, `min_user_winpct` on the games row (per-side move accuracy excludes plies ≤ theory_exit_ply, §8.4).
- tests/test_batch.py: exact `game_totals` numbers, theory-ply exclusion, persisted-to-games-row.
- tests/test_analyze.py: engine test — every user move classified, accuracies in [0,100], max ≥ min.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q` → "105 passed in 12.90s"
- Scratch e2e (`analyze --reanalyze`) on a user game: games row `user_accuracy=12.36, opp_accuracy=99.80, max=53.40, min=43.50`; 0 user moves with NULL classification. Numbers make chess sense (the user blundered and was mated; the opponent played perfect moves).
Deviations from PLAN: none
Known issues / follow-ups: GATE — orchestrator should spot-check 3 games vs lichess analysis for sanity. Note: `moves.classification` was already populated in T3.2/T3.3 (classify.py existed early, D5); this task added the game-level aggregates.
Next task: T5.1 (Motif detectors + fixtures)

### T3.4 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: review (GATE)
Commit: 667e9c2
What changed:
- No source changes. Benchmarked `analyze_game` at the default depths on the six fixture games.
How I verified:
- Real run (`/tmp/bench.py`, Stockfish 17.1, threads=1, hash 128 MB, pass1=14/pass2=18/multipv=3), user synthesised as each game's White so pass 2 actually fires:
  `games=6  avg=3.65s  median=3.83s  max=7.60s  total=21.9s`
  per game: Opera 33 ply 4.02s · Legall 13 ply 0.96s · Fool's 4 ply 5.16s · Hamppe 36 ply 7.60s · Scholar 7 ply 0.54s · Blackburne 13 ply 3.64s
- Machine: Intel i7-7700K (8 threads), Linux-7.0.0 x86_64. Numbers recorded in the PROGRESS Benchmarks table.
Deviations from PLAN: none
Known issues / follow-ups: these are short fixture games; real 60–80 ply games will be slower (still well inside budget). GATE: owner may want a real-data run recorded.
Next task: T4.2 (Wire classification into analysis, GATE)

### T3.3 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: 7b2d0e2
What changed:
- src/chesscoach/analyze.py: `run_batch` (§9 worker pool, `imap_unordered`, parent-only DB writes, commit per game), `_worker`, `_select_specs` (pending/pass1, `--since`/`--limit`), `_mark_short_games_skipped` (`min_plies`), `_reset_status` (`--reanalyze`), `_write_moves`. Games are marked `pass1` before running so a crash stays resumable; `book` triggers the T2.2 openings backfill.
- src/chesscoach/cli.py: `analyze [--limit] [--since] [--reanalyze]` wired end-to-end with per-game progress.
- tests/test_batch.py: resume-after-crash (injected crashing executor → only the unfinished game re-analyzed), per-game error recording, short-game skip, limit/oldest-first.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q` → "101 passed in 10.32s" (5 new batch tests)
- CLI e2e: `python -m chesscoach analyze --limit 1` on an imported game → 33 moves stored, status done, engine "Stockfish 17.1". Scratch run (min_plies=4) on a user game → user move g4 classified `blunder` (win_drop 43.5) with multipv, opponent ply left NULL — classification path confirmed end-to-end.
Deviations from PLAN: none
Known issues / follow-ups: the repo-root DB game is a PaulMorphy fixture, so its user moves are all NULL (the configured user is not in it) — correct behaviour, not a bug. `backfill_openings` now runs inside `analyze`.
Next task: T3.4 (Benchmark, GATE)

### T3.2 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: 17b712b
What changed:
- src/chesscoach/analyze.py: `AnalyzedMove`/`GameAnalysis` + `analyze_game(parsed, engine, config, theory_exit_ply)`. Pass 1 evaluates P0..PN once (terminal positions scored from the result, §8.3); pass 2 deepens every user move with win_drop ≥ 10 and overwrites that ply's values + `multipv_json`. No DB writes.
- tests/test_analyze.py (engine): every ply has before/after evals; the blunder row has `multipv_json` with `pass2_multipv` entries; opponent plies have none; user moves classified; final `mate_after`/`win_after` come from the result.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q tests/test_analyze.py` → "3 passed in 9.12s" (real Stockfish; Fool's Mate fixture: both 1.f3 and 2.g4 get deepened, 2...e5 does not)
Deviations from PLAN: none
Known issues / follow-ups: none
Next task: T3.3 (Batch analysis, workers, resume)

### T4.1 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: bee4581
What changed:
- src/chesscoach/classify.py: pure §8.2–§8.8 — `win_percentage`, `win_drop`, `move_accuracy`, `game_accuracy`, `classify_move` (both §8.5 caps), `non_pawn_material`, `phase`, `low_clock`, `failed_conversion`, `saved_game`.
- tests/test_classify.py: win anchors (0/±1000 + mate), drop floor, accuracy anchors (drop 0≈100, drop 30≈24.78), every class boundary, both exceptions, phase boundaries, low_clock thresholds, conversion/saved flags.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q tests/test_classify.py` → "15 passed in 0.07s"
Deviations from PLAN: done ahead of T3.2 (see D5)
Known issues / follow-ups: none
Next task: T3.2 (Single-game analysis)

### T3.1 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: 3a8f0b5
What changed:
- src/chesscoach/engine.py: `EngineLine` dataclass and `Engine` (context manager; `from_config`; `id_name`; `evaluate(board, depth, multipv, pov)`). Scores normalized to the requested POV and cp clamped to ±1000 per §8.1; PV capped at 10 plies.
- tests/test_engine.py: start-position eval within ±100cp, mate-in-1 → mate=1, POV sign, multipv ranking, id name. All marked `engine`.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q` → "78 passed in 1.22s" (6 engine tests ran against Stockfish 17.1 at /usr/games/stockfish, none skipped)
Deviations from PLAN: none
Known issues / follow-ups: none
Next task: T4.1 (classify.py) then T3.2 (see D5)

### T2.2 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: fcad03a
What changed:
- src/chesscoach/openings.py: `OpeningAnnotation` + `annotate_pgn` (§8.9 theory-exit replay, header fallback) + `backfill_openings(conn, book)`.
- src/chesscoach/importer.py: `import_pgn_file` takes an optional `book` and stores opening_name/family/theory_exit_ply.
- src/chesscoach/fetch.py: `fetch_all`/`_insert_month` take an optional `book`; same columns stored.
- src/chesscoach/cli.py: `_load_book(root)` helper; `import` and `fetch` now annotate from data/openings.
- tests/test_openings.py: theory-exit-on-deviation (exit ply 6), whole-game-in-book (NULL exit), ply-1 header fallback, no-book/no-header, empty PGN, backfill, import-with-book.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q` → "72 passed in 0.43s" (7 new tests)
- `python -m chesscoach import tests/fixtures/sample_games.pgn` (real book) → Opera Game row: opening_name "Philidor Defense: Albin-Blackburne Gambit", family "Philidor Defense", eco C41, theory_exit_ply 8.
Deviations from PLAN: none
Known issues / follow-ups: `backfill_openings` is implemented+tested but not yet *called* by the `analyze` command (still a stub until T3.3); will be invoked there.
Next task: T3.1 (Engine wrapper)

### T2.1 handoff — Cody (deepseek-v4.1-flash) — 2026-10-09
Status: done
Commit: cd06fdf
What changed:
- src/chesscoach/openings.py: `epd_of`, `opening_family`, `load_openings` (replays lichess TSVs; longest line reaching an EPD wins), `OpeningBook` (`from_dir`/`name_for_epd`), `eco_name_from_headers` fallback (§7.2), and `download_openings` (via the injectable `Transport`; `OpeningsError` prints manual-download instructions if blocked).
- src/chesscoach/cli.py: `openings download` wired end-to-end.
- tests/fixtures/openings_sample.tsv: real lichess lines (Caro-Kann, Najdorf, etc.) for the EPD tests.
- tests/test_openings.py: Caro-Kann-Advance resolution (the T2.1 AC), longest-line-wins, deeper-variation, out-of-book, from_dir/empty dir, family, header fallback, download + error.
How I verified:
- `ruff check .` → "All checks passed!"
- `pytest -q` → "65 passed in 0.40s" (10 new openings tests)
- `python -m chesscoach openings download` (real network) → downloaded 5 files (a/b/c/d/e.tsv, 395 KB) into data/openings; `OpeningBook.from_dir` → 7982 EPDs; `1.e4 c6 2.d4 d5 3.e5` → `('B12', 'Caro-Kann Defense: Advance Variation')`.
Deviations from PLAN: header-fallback hyphen handling (see D4)
Known issues / follow-ups: none
Next task: T2.2 (Annotate games with openings)

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
