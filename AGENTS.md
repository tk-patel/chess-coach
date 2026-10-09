# AGENTS.md — Rules for any coding agent working on chess-coach

You are a coding agent working on **chess-coach**, a personal tool that downloads a player's
chess.com games, analyzes them with Stockfish, and turns the results into (1) a study report and
(2) a puzzle trainer built from the player's own mistakes.

The human owner is the final authority. An orchestrator (Claude) wrote the plan and reviews work
at gates. You are an implementer. Follow these rules exactly.

## 0. Before you write any code
1. Read `PLAN.md` fully. It is the spec. Do not skim the "Definitions" section; the math matters.
2. Read `PROGRESS.md`. Find the **first task whose status is `todo` and whose dependencies are all `done`**.
   That is your task. Do not pick a different one unless the human tells you to.
3. Set that task to `in_progress` in `PROGRESS.md`, with your agent/model name and the date.
4. Restate the task's acceptance criteria to yourself. If any criterion is ambiguous, write the
   question under "Open questions" in `PROGRESS.md` and choose the most conservative reading.

## 1. While working
- **One task at a time.** Do not start the next task in the same session unless the current one is
  `done` and verified.
- **Stay inside the task's scope.** If you notice something else that needs doing, add it to the
  "Backlog / discovered work" section of `PROGRESS.md`. Do not do it.
- **Follow the spec's names.** Module names, CLI commands, DB columns and config keys are defined in
  `PLAN.md`. Do not rename them. If the spec is wrong, log a Decision (see §3) before deviating.
- **Never change the DB schema silently.** Schema changes need a migration in `src/chesscoach/db.py`
  (bump `SCHEMA_VERSION`), an update to `PLAN.md` §6, and a Decision entry.
- **No fabricated results.** Never write "tests pass" or a benchmark number you did not observe.
  Paste the real command output (trimmed) into the handoff note.
- **No network assumptions.** The sandbox you run in may block `api.chess.com`, GitHub, or CDNs.
  If a download is blocked, do not try workarounds; record a blocker and use the offline path
  described in the plan (fixtures / PGN import / ask the human to drop the file in).
- **Fixtures must be real.** Any FEN or PGN you put in `tests/fixtures/` must be validated with
  python-chess (`chess.Board(fen).is_valid()` / the game parses with zero errors). Never invent an
  engine evaluation in a test; tests that need engine output mark themselves
  `@pytest.mark.engine` and run against the real binary.
- **Keep diffs small and readable.** Type hints on public functions. Docstrings on modules.
  No dead code, no commented-out blocks.
- **Deterministic output.** Sort anything that ends up in a report or JSON file.

## 2. Definition of done (every task)
A task is `done` only when ALL of these hold:
1. Every acceptance criterion listed for the task in `PLAN.md` is met.
2. `ruff check .` passes with no errors.
3. `pytest -q` passes (engine-marked tests may be skipped only if Stockfish is unavailable, and
   that must be stated in the handoff).
4. Any new CLI command works end-to-end on `tests/fixtures/sample_games.pgn`.
5. `PROGRESS.md` is updated: status `done`, a handoff note (template below), and the commit hash.
6. One git commit per task, message format: `T<id>: <short summary>`.

If you cannot finish, set the status to `blocked` or leave it `in_progress`, and write a handoff
note saying exactly what is left and why. A half-done task marked `done` is the worst outcome.

## 3. Decisions log
Any time you choose between reasonable options the plan did not settle (a library version, a
threshold, a file layout), add one line to the Decisions log in `PROGRESS.md`:
`D<n> | date | task | decision | reason`.

## 4. Review gates
Tasks marked **GATE** in `PLAN.md` end with a stop. After finishing a GATE task, set its status to
`review` (not `done`) and stop. The orchestrator or human reviews and flips it to `done`.

## 5. Handoff note template (paste into PROGRESS.md under the task)
```
### T<id> handoff — <agent/model> — <YYYY-MM-DD>
Status: done | blocked | in_progress | review
Commit: <hash>
What changed: <files + one line each>
How I verified: <commands run + trimmed real output>
Deviations from PLAN: <none | list, each with a Decision id>
Known issues / follow-ups: <none | list>
Next task: T<id>
```

## 6. Environment quick reference
- Python 3.11+, virtualenv in `.venv/`.
- Stockfish binary path comes from `config.toml` → `engine.path` (default `stockfish` on PATH).
- Run everything through the CLI: `python -m chesscoach <command>`.
- Data lives in `data/` (gitignored). Outputs go to `out/` (gitignored).
- Never commit `config.toml`, `data/`, or `out/`.
