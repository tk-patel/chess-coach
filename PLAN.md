# chess-coach — Project Plan

Owner: Tejas · Orchestrator: Claude · Plan version: 1.0 · Last updated: 2026-10-09

Agents: read `AGENTS.md` first, then this whole file, then `PROGRESS.md`.

---

## 1. Goal

Help one chess.com player improve. The tool should not be a pile of statistics; it should answer
three questions:

1. **What keeps losing me games?** The blunder profile: by phase, by clock, and by tactical motif.
2. **Which openings are hurting me, and where exactly do I go wrong in them?**
3. **Can I drill my own recurring mistakes until I stop making them?** The personal puzzle trainer
   with spaced repetition.

Priority order if time runs short: **puzzle trainer > blunder profile > opening report > everything else.**

### Non-goals (do not build)
- No attempt to match chess.com's "CAPS" accuracy numbers exactly.
- No live/real-time analysis, no browser extension, no chess.com scraping of logged-in pages.
- No multi-user support, no auth, no cloud deployment.
- No LLM-written explanations in v1 (see Backlog; engines are right, LLMs explaining chess often are not).

---

## 2. Architecture overview

```
chess.com public API ──fetch──▶ data/raw/*.json ──parse──▶ SQLite (data/chesscoach.db)
        (or user PGN file ──import──┘)                          │
                                                                ▼
                          openings (lichess TSV) ──▶ annotate opening + theory-exit ply
                                                                │
                              Stockfish (UCI) ──▶ analyze: pass 1 (all plies) + pass 2 (candidates)
                                                                │
                                         classify (win%, accuracy, mistake class, phase, clock)
                                                                │
                                         motifs (heuristic tactic tags)
                                                    ┌───────────┴───────────┐
                                                    ▼                       ▼
                                      puzzles (out/puzzles.json)   stats (out/*.html report)
                                                    │
                                                    ▼
                                      trainer (out/trainer.html, Leitner boxes)
```

Everything runs locally as a Python CLI. Target host: the owner's Ubuntu home server (also works on
any Linux/macOS dev machine). Outputs are static HTML files that open via `file://` or any static
file server on the LAN.

---

## 3. Tech stack (fixed — do not substitute without a Decision)

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Chess logic | `python-chess` (>=1.10) | PGN parsing, board, UCI engine control, `node.clock()` |
| Engine | Stockfish (any version ≥ 15) | `apt install stockfish` on Ubuntu, or official release binary |
| Storage | SQLite via stdlib `sqlite3` | No ORM |
| HTTP | `requests` | Only for chess.com API + one-time openings download |
| CLI | `typer` | |
| Templates | `jinja2` | |
| Charts | `matplotlib` → inline SVG in HTML | Offline, no JS chart lib |
| Trainer board | Vanilla JS + inline SVG, no external libs | Legal-move checking is NOT needed in JS (see §10) |
| Tests | `pytest` | marker `engine` for tests that need Stockfish |
| Lint | `ruff` | |

---

## 4. Repository layout

```
chess-coach/
  AGENTS.md
  PLAN.md
  PROGRESS.md
  README.md                  # short: install + the 3 commands a human runs
  pyproject.toml
  config.example.toml
  .gitignore                 # .venv/ data/ out/ config.toml __pycache__/
  src/chesscoach/
    __init__.py
    __main__.py              # python -m chesscoach → cli.app()
    cli.py                   # typer app; thin wrappers only
    config.py                # load + validate config.toml into a dataclass
    db.py                    # connect, schema, migrations, small query helpers
    fetch.py                 # chess.com API client
    importer.py              # PGN file → games rows
    parse.py                 # PGN text → Game + Move records (pure functions)
    openings.py              # lichess openings DB load, name + theory-exit lookup
    engine.py                # Stockfish wrapper (context manager)
    analyze.py               # pass 1 / pass 2 orchestration, workers, resume
    classify.py              # win%, accuracy, classes, phase, clock buckets (pure)
    motifs.py                # heuristic tactic detectors (pure, take board + lines)
    puzzles.py               # select + build puzzle records, export JSON
    stats.py                 # aggregate queries → plain dicts for templates
    charts.py                # matplotlib → SVG strings
    report.py                # render templates into out/
    templates/
      base.html  overview.html  openings.html  mistakes.html  games.html  trainer.html
  tests/
    fixtures/
      sample_games.pgn       # ≥ 6 real games incl. a win, a loss, a draw, a timeout, a daily game
      sample_archive.json    # one real-shaped chess.com monthly archive response (≥ 3 games)
      positions.json         # validated FENs for motif tests
    test_parse.py test_classify.py test_openings.py test_motifs.py
    test_puzzles.py test_stats.py test_engine.py (engine-marked)
  data/                      # gitignored
  out/                       # gitignored
```

---

## 5. Configuration (`config.example.toml`)

```toml
[player]
username = "CHANGE_ME"          # chess.com username; compare case-insensitively everywhere

[fetch]
user_agent = "chess-coach/0.1 (personal use; contact: CHANGE_ME@example.com)"
time_classes = ["bullet", "blitz", "rapid", "daily"]   # which games to keep
rules = "chess"                  # skip chess960, bughouse, etc.
rated_only = false

[engine]
path = "stockfish"
threads_per_worker = 1
hash_mb = 128
workers = 4                      # parallel engine processes; default = CPU cores - 1 (min 1)
pass1_depth = 14
pass2_depth = 18
pass2_multipv = 3

[analysis]
min_plies = 10                   # games shorter than this are stored but not analyzed
opening_max_ply = 24             # "opening" phase upper bound when out of book earlier
endgame_material = 26            # total non-pawn material on board (both sides) at or below → endgame

[puzzles]
min_drop = 20.0                  # user win% drop to qualify (i.e. mistake or blunder)
min_best_winpct = 35.0           # there must have been something worth finding
uniqueness_gap = 10.0            # best minus 2nd-best win% needed for a single-answer puzzle
accept_within = 3.0              # any multipv move within this of best is accepted

[report]
min_games_opening = 15           # don't judge openings below this sample size
```

`config.py` must fail loudly with a clear message if `username` is still `CHANGE_ME` (for commands
that need it) or if the engine path cannot be executed (for analysis commands).

---

## 6. Data model (SQLite) — `SCHEMA_VERSION = 1`

All win% values are **from the user's point of view** (0–100). All `cp` values are centipawns from
the **user's** point of view, clamped to ±1000; mates stored separately.

```sql
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);          -- schema_version, engine_id, etc.

CREATE TABLE archives (                                         -- fetch bookkeeping
  url TEXT PRIMARY KEY, fetched_at INTEGER, etag TEXT, last_modified TEXT, game_count INTEGER
);

CREATE TABLE games (
  uuid TEXT PRIMARY KEY,           -- chess.com uuid; for PGN imports: sha1 of normalized movetext+headers
  url TEXT,
  source TEXT NOT NULL,            -- 'api' | 'pgn'
  end_time INTEGER,                -- unix seconds
  time_class TEXT,                 -- bullet|blitz|rapid|daily
  time_control TEXT,               -- raw, e.g. "180+2", "600", "1/259200"
  base_seconds INTEGER, increment_seconds INTEGER,   -- NULL for daily
  rated INTEGER,
  user_color TEXT NOT NULL,        -- 'white' | 'black'
  user_rating INTEGER, opp_rating INTEGER, opp_username TEXT,
  result TEXT NOT NULL,            -- 'win' | 'draw' | 'loss' (user POV)
  termination TEXT,                -- raw chess.com result code of the loser/drawer, e.g. 'timeout'
  eco TEXT, opening_name TEXT, opening_family TEXT,
  theory_exit_ply INTEGER,         -- first ply whose resulting position is NOT in the openings DB
  ply_count INTEGER,
  pgn TEXT NOT NULL,
  analysis_status TEXT NOT NULL DEFAULT 'pending',  -- pending|pass1|done|skipped|error
  analysis_error TEXT,
  engine_id TEXT, pass1_depth INTEGER, pass2_depth INTEGER,
  user_accuracy REAL, opp_accuracy REAL,
  max_user_winpct REAL, min_user_winpct REAL
);

CREATE TABLE moves (
  game_uuid TEXT NOT NULL REFERENCES games(uuid),
  ply INTEGER NOT NULL,            -- 1-based; ply 1 = white's first move
  color TEXT NOT NULL,             -- mover
  is_user INTEGER NOT NULL,
  san TEXT NOT NULL, uci TEXT NOT NULL,
  fen_before TEXT NOT NULL,
  clock_after REAL,                -- seconds left for mover after the move (from %clk), NULL if absent
  time_spent REAL,                 -- seconds, see §8.6
  cp_before INTEGER, mate_before INTEGER,   -- eval of fen_before, user POV
  cp_after INTEGER,  mate_after INTEGER,    -- eval after the move, user POV
  win_before REAL, win_after REAL,
  win_drop REAL,                   -- mover-POV drop, ≥ 0 (see §8.3); only meaningful when is_user=1
  move_accuracy REAL,
  best_uci TEXT, best_san TEXT,    -- engine best in fen_before
  pv_uci TEXT,                     -- space-separated, best line from fen_before (≤ 10 plies)
  multipv_json TEXT,               -- pass 2 only: [{"uci":..,"san":..,"cp":..,"mate":..,"win":..}, ...]
  classification TEXT,             -- best|good|inaccuracy|mistake|blunder (user moves only)
  phase TEXT,                      -- opening|middlegame|endgame
  low_clock INTEGER,               -- 1 if user was in time trouble when moving
  motifs_json TEXT,                -- ["hung_piece", "allowed_fork", ...]
  PRIMARY KEY (game_uuid, ply)
);

CREATE TABLE puzzles (
  id TEXT PRIMARY KEY,             -- sha1(fen_4field + solution_uci)[:12]
  game_uuid TEXT NOT NULL, ply INTEGER NOT NULL,
  fen TEXT NOT NULL,               -- position before the user's mistake, user to move
  played_san TEXT NOT NULL,
  solution_uci TEXT NOT NULL, solution_san TEXT NOT NULL,
  accepted_uci_json TEXT NOT NULL, -- all acceptable first moves
  line_san TEXT,                   -- best line (≤ 6 plies) shown after solving
  win_drop REAL, motifs_json TEXT, phase TEXT, low_clock INTEGER,
  opening_name TEXT, game_url TEXT, end_time INTEGER
);

CREATE INDEX idx_moves_user ON moves(game_uuid, is_user);
CREATE INDEX idx_games_status ON games(analysis_status);
```

---

## 7. External data sources

### 7.1 chess.com Published-Data API (no auth)
- Archive list: `GET https://api.chess.com/pub/player/{username_lowercase}/games/archives`
  → `{"archives": ["https://api.chess.com/pub/player/x/games/2024/01", ...]}`
- Monthly games: `GET <archive url>` → `{"games": [ {url, pgn, time_control, end_time, rated,
  uuid, time_class, rules, white:{username, rating, result}, black:{...}, eco, ...}, ...]}`
- Rules for being a good client:
  - Always send the configured `User-Agent` header.
  - **Requests strictly serial**, never parallel. On HTTP 429, back off (1s, 2s, 4s, 8s, max 5 tries).
  - Past months never change: if an archive URL is already in `archives`, skip it **unless** it is
    the current month (or the most recent one listed), which is re-fetched. Send `If-None-Match` /
    `If-Modified-Since` when stored; on 304 do nothing.
  - Store each raw month response in `data/raw/{YYYY}-{MM}.json` before parsing (allows re-parse
    without re-download).
- Result codes (`white.result` / `black.result`) → user result:
  - `win` → win
  - `agreed`, `repetition`, `stalemate`, `insufficient`, `50move`, `timevsinsufficient` → draw
  - anything else (`checkmated`, `resigned`, `timeout`, `abandoned`, `lose`, ...) → loss
  - Store the non-`win` side's code in `termination`.
- Keep only games with `rules == config.fetch.rules` and `time_class in config.fetch.time_classes`.
- **Offline fallback:** the sandbox may block this host. Then the human runs `fetch` on their own
  machine, or exports PGN from chess.com and uses `import`. Tests never hit the network.

### 7.2 Openings database
- Source: lichess `chess-openings` repo (CC0): files `a.tsv` … `e.tsv`, columns `eco`, `name`, `pgn`.
  URL pattern: `https://raw.githubusercontent.com/lichess-org/chess-openings/master/{a..e}.tsv`.
- Command `chesscoach openings download` saves them to `data/openings/`. If blocked, print exact
  instructions for the human to download the 5 files into that folder.
- Build an in-memory dict: **EPD (first 4 FEN fields) → (eco, name)** by replaying each line's PGN
  and recording every position along the way, mapping each EPD to the **longest** line reaching it.
- If the TSVs are missing, fall back to PGN headers `ECO` and the slug of `ECOUrl`
  (`.../openings/Caro-Kann-Defense-Advance-Variation` → `Caro-Kann Defense Advance Variation`), and
  set `theory_exit_ply` NULL.

---

## 8. Definitions (the math — implement exactly)

### 8.1 Score normalization
- Use python-chess `info["score"].pov(user_color)`.
- If mate: store `mate` (positive = user mates, negative = user gets mated), set `cp` = NULL.
- Else `cp = clamp(score.score(), -1000, 1000)`.

### 8.2 Win percentage (lichess formula)
```
win(cp)   = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)
win(mate) = 100 if mate > 0 else 0
```
`win(0) == 50.0`, `win(1000) ≈ 97.5`, `win(-1000) ≈ 2.5`. Unit-test these three values.

### 8.3 Win drop for a user move
`win_drop = max(0, win_before - win_after)`, both user POV, where `win_after` is the eval of the
position after the move (= `win_before` of the next ply).
For the game's final move, `win_after` comes from the result: checkmate delivered → 100;
stalemate/draw → 50; otherwise evaluate the final position.

### 8.4 Move accuracy and game accuracy
```
move_accuracy = clamp(103.1668 * exp(-0.04354 * win_drop) - 3.1669, 0, 100)
game_accuracy = arithmetic mean of move_accuracy over that side's moves, excluding plies ≤ theory_exit_ply
```
Document in the report footer that this is lichess-style, not chess.com CAPS.

### 8.5 Move classification (user moves only)
| win_drop | class |
|---|---|
| move == engine best (pass 1 or 2) | `best` |
| < 10 | `good` |
| 10 – < 20 | `inaccuracy` |
| 20 – < 30 | `mistake` |
| ≥ 30 | `blunder` |

Exception: if `win_before ≥ 97` and `win_after ≥ 90` (still totally winning), cap at `good`;
if `win_before ≤ 3`, cap at `good` (already lost). These prevent noise in decided positions.

### 8.6 Clock
- `clock_after` = python-chess `node.clock()` for that move (seconds) or NULL.
- `clock_before` for the mover = their previous `clock_after`, or `base_seconds` on their first move.
- `time_spent = clock_before - clock_after + increment_seconds` (floor at 0).
- `low_clock = 1` when `clock_before < max(30, 0.10 * base_seconds)`. Daily games: always NULL.

### 8.7 Phase (per ply, from `fen_before`)
- `non_pawn_material` = sum over all pieces except pawns and kings: N=3, B=3, R=5, Q=9 (both sides).
- `endgame` if `non_pawn_material ≤ config.analysis.endgame_material` (default 26).
- else `opening` if `ply ≤ opening_max_ply` OR (`theory_exit_ply` is not NULL and `ply < theory_exit_ply`).
- else `middlegame`.

### 8.8 Conversion and resourcefulness
- **Failed conversion:** user's `win_before` ≥ 85 on at least 2 user moves after ply 20, and result ≠ win.
- **Saved game:** user's `win_before` ≤ 15 on at least 2 user moves after ply 20, and result ≠ loss.

### 8.9 Theory exit ply
Replay the game from the start; the first ply whose resulting EPD is not in the openings dict is
`theory_exit_ply`. Opening name = name of the last in-book position. If even ply 1 is out of book,
`theory_exit_ply = 1`.

---

## 9. Engine analysis strategy

Two passes to keep it fast enough for 1,000+ games on a home server.

**Pass 1 (every ply, every analyzable game):** `Limit(depth=pass1_depth)`, multipv 1. For each
position `fen_before` of ply k, store cp/mate, best move, PV (≤ 10 plies). The eval of position k+1
is the "after" eval of ply k, so each position is analyzed exactly once (N+1 positions for N plies).

**Pass 2 (candidates only):** for every **user** move with pass-1 `win_drop ≥ 10`, re-analyze
`fen_before` at `pass2_depth` with `multipv = pass2_multipv`, and re-analyze the position after
the played move at `pass2_depth` multipv 1. Overwrite the pass-1 values for that ply with the
deeper ones, store `multipv_json`, then recompute that ply's drop and class. (A deeper look often
shows a "blunder" was fine, or vice versa.)

**Workers:** a `multiprocessing` pool of `workers` processes, each owning one engine
(`Threads=threads_per_worker`, `Hash=hash_mb`). The unit of work is one game. The parent process
alone writes to SQLite (workers return results). Commit after every game.

**Resume:** select games where `analysis_status IN ('pending','pass1')`. A crash loses at most the
in-flight games. `--reanalyze` resets everything to `pending`. Store `engine_id` (from the
engine's `id name`) and depths in `games`; if the configured depth or engine changes, `analyze`
warns and only reanalyzes with `--reanalyze`.

**Errors:** an exception on one game sets `analysis_status='error'` + message and continues.

**Performance budget:** the target is ≤ 15 s per game per worker at the default depths on a modern
x86 CPU. T3.4 measures the real number; record it in PROGRESS.md. Do not tune depths below
pass1=12 / pass2=16 without a Decision.

---

## 10. Motif detection (heuristics — label as such in the UI)

Pure functions in `motifs.py`. Input: `board_before` (user to move), the played move, the
engine best line, and the opponent's best reply after the played move (first move of the PV
from the post-move position). Output: list of tags. Only run for user moves classified
`inaccuracy` or worse.

Material values: P=1, N=3, B=3, R=5, Q=9, K=0. "Material swing along a line" = user material
minus opponent material after playing the first n plies of the line, compared with before.

| Tag | Rule |
|---|---|
| `allowed_mate` | after the played move, the eval is mate against the user (`mate_after < 0`, and abs ≤ 5) |
| `missed_mate` | `mate_before > 0` and the played move does not keep a mate score for the user |
| `back_rank` | `allowed_mate` and the mating line's final move gives check with a rook or queen on the user's back rank while the user's king is on that rank |
| `hung_piece` | opponent's best reply is a capture, AND the material swing along the post-move PV over 4 plies is ≤ -2 for the user |
| `allowed_fork` | opponent's best reply puts a piece on a square from which it attacks ≥ 2 user pieces each worth more than the attacker, or the king + any piece worth ≥ 3; AND the 4-ply material swing ≤ -2 |
| `missed_fork` | same fork test applied to the user's engine-best move from `board_before`, AND the 4-ply swing along the best PV ≥ +2 |
| `allowed_pin` | after opponent's best reply, a user piece worth ≥ 3 is absolutely pinned (`board.is_pinned`) that was not pinned before; AND swing ≤ -2 |
| `missed_capture` | engine best move is a capture AND the 4-ply swing along best PV ≥ +2 AND the played move was not a capture of equal or greater value |
| `promotion` | a promotion appears in the first 4 plies of either the best PV (missed) or the post-move PV (allowed) |
| `low_clock` | `low_clock = 1` (copied as a tag so the UI can filter uniformly) |
| `positional` | no other tag except possibly `low_clock` — the drop is not explained by a simple tactic |

Tests: `tests/fixtures/positions.json` holds at least 2 hand-checked positive and 1 negative
example per tag, each with FEN, played move, and the line(s) the function needs (lines are given
as UCI lists in the fixture, so these tests do NOT need Stockfish). Every FEN must pass
`Board.is_valid()` and every move must be legal; a test asserts this.

---

## 11. Puzzles

Selection (user moves only, after pass 2):
1. `win_drop ≥ puzzles.min_drop`.
2. `multipv_json` exists. The best entry's win% ≥ `puzzles.min_best_winpct`.
3. Accepted moves = all multipv entries whose win% ≥ best_win − `accept_within`.
4. If more than one move is accepted AND best − 2nd best < `uniqueness_gap`, mark the puzzle as
   `multi_answer` (still included; the UI shows "several moves work").
5. The played move must NOT be in the accepted set.
6. Dedupe on 4-field EPD + solution; keep the most recent occurrence and count repeats
   (`seen_count`, add to the JSON, not the DB).

Export: `out/puzzles.json`, sorted by `end_time` desc, each:
```json
{"id": "...", "fen": "...", "orientation": "white|black", "played_san": "Qxb7??",
 "accepted": ["d2d4", "c1g5"], "solution_san": "Bg5", "line_san": "Bg5 h6 Bxf6 ...",
 "win_drop": 34.2, "motifs": ["hung_piece"], "phase": "middlegame", "low_clock": false,
 "opening": "Caro-Kann Defense: Advance Variation", "game_url": "https://...", "date": "2026-09-14",
 "multi_answer": false, "seen_count": 1}
```

### Trainer (`out/trainer.html`)
- Self-contained: puzzle JSON inlined in a `<script type="application/json">` tag, so the file works
  via `file://`. No external JS/CSS.
- Board: 8×8 SVG, Unicode chess glyphs (♔♕♖♗♘♙ / ♚♛♜♝♞♟) on light/dark squares, oriented to the
  user's color, coordinates on the edges. Click a piece then a square (and support drag if easy).
  On promotion squares, ask Q/R/B/N.
- **No legality engine in JS:** a guess is checked only against `accepted` (UCI string compare,
  including the promotion letter). Any other move → "Not quite", show the move they played in the
  real game, allow retry or reveal.
- After solving or revealing: show `solution_san`, `line_san`, motif tags, opening, date, and a link
  to the game.
- Spaced repetition: **Leitner boxes 1–5** with review intervals 0, 1, 3, 7, 21 days. Correct first
  try → box+1; wrong or revealed → box 1. State in `localStorage` key `chesscoach.srs.v1`
  `{puzzleId: {box, due, attempts, correct}}`, wrapped in try/catch so the page works without
  storage.
- Queue order: due puzzles (box asc, then oldest due), then new puzzles (largest `win_drop` first).
- Filters: motif, phase, low_clock, time window (last 30/90/365 days/all).
- Buttons: "Export progress" (download JSON) and "Import progress" (file input) for moving between devices.
- Must be usable on a phone (≥ 360 px wide): board fills the width, controls under it.

---

## 12. Report (`out/index.html` + sub-pages)

Every number shows its sample size. Any rate based on fewer than `report.min_games_opening` games
is shown greyed with "small sample". Proportions show a Wilson 95% interval.

**Overview (`index.html`):**
- Games, W/D/L overall and by color and time class; rating over time (line chart per time class).
- Average user accuracy over time (rolling 20-game mean).
- **"Top issues" panel:** auto-generated, at most 5 bullet sentences, from these rules, ranked
  by the number of games affected:
  - share of blunders by phase vs. that phase's share of moves (e.g. "38% of your blunders happen in
    endgames, which are 19% of your moves"),
  - blunder rate per 100 moves when `low_clock` vs. not,
  - the top 3 motif tags by count,
  - failed conversions per 100 games where the user reached ≥ 85 win%,
  - the opening (n ≥ min) with the worst score vs. the user's average score for that color.
- Links to the trainer and the other pages.

**Mistakes (`mistakes.html`):**
- Blunders and mistakes per 100 user moves by phase (bar chart).
- Same, split by low_clock (bar chart).
- Motif counts (bar chart) with a link to the trainer pre-filtered by that motif
  (`trainer.html#motif=hung_piece`).
- Time spent per move distribution vs. blunders (do mistakes happen on quick moves?).
- Table of the 20 most costly user moves: date, opening, move, best move, drop, motifs, game link.

**Openings (`openings.html`):** separate tables for White and Black, grouped by `opening_family`
with an expandable variation level.
- Columns: games, score% (win=1, draw=0.5) with Wilson CI, avg user accuracy, avg win% at
  `theory_exit_ply`, median theory-exit move number, and most common first user inaccuracy-or-worse
  (move + count).
- Flag "consider dropping or studying" only when n ≥ `min_games_opening` AND the CI upper bound is
  below the user's overall score for that color.

**Games (`games.html`):** sortable table of all games: date, color, opponent rating, time class,
opening, result, accuracy, blunders, link. Plain JS sorting, no libs.

Visual style: clean, light/dark via `prefers-color-scheme`, system font stack, mobile-friendly.
Footer: generation time, games analyzed, engine id and depths, note that motif tags are heuristic.

---

## 13. CLI

```
python -m chesscoach init                 # create data/, out/, DB, copy config.example.toml → config.toml if missing
python -m chesscoach openings download    # fetch lichess TSVs into data/openings/
python -m chesscoach fetch                # chess.com API → data/raw → games table (incremental)
python -m chesscoach import FILE.pgn      # alternative/extra input
python -m chesscoach analyze [--limit N] [--since YYYY-MM-DD] [--reanalyze]
python -m chesscoach puzzles              # rebuild puzzles table + out/puzzles.json
python -m chesscoach report               # write out/*.html (incl. trainer.html)
python -m chesscoach update               # fetch → analyze → puzzles → report (for cron)
python -m chesscoach status               # counts: games by status, puzzles, last fetch, engine id
```
Every command prints a one-line summary at the end (e.g. `analyzed 37 games, 0 errors, 6m12s`).
`analyze` shows progress (`[12/37] game <uuid> 8.4s`).

---

## 14. Task breakdown

Status lives in `PROGRESS.md`. IDs are stable; do not renumber. "Deps" must be `done` first.

### M0 — Foundation
**T0.1 Scaffold** (deps: none)
- Create the layout from §4, `pyproject.toml` (deps from §3, `[project.scripts]` optional),
  `.gitignore`, `README.md` stub, `config.example.toml` (§5), `__main__.py`, a typer app with `init`
  and `status` stubs, `ruff` config, `pytest` config registering the `engine` marker.
- AC: `pip install -e .[dev]` works in a fresh venv; `python -m chesscoach --help` lists all commands
  from §13 (stubs may print "not implemented"); `ruff check .` and `pytest -q` pass.

**T0.2 Config + DB** (deps: T0.1)
- `config.py` with a dataclass and validation per §5; `db.py` creating the §6 schema, setting
  `meta.schema_version`, with a `migrate()` entry point. `init` works.
- AC: tests cover loading the example config, the CHANGE_ME error, and the schema creating the 5
  tables and 2 indexes on a temp DB.

**T0.3 Fixtures** (deps: T0.1)
- `tests/fixtures/sample_games.pgn`: ≥ 6 real games with `%clk` comments (the human can supply
  exports; otherwise use well-known public games and add `%clk` values, noting that in a Decision).
  `sample_archive.json`: a chess.com-shaped monthly response built from 3 of those games.
- AC: a test parses every fixture game with zero python-chess errors.

### M1 — Data in
**T1.1 Parse** (deps: T0.2, T0.3) — `parse.py`: PGN + metadata → game dict + move dicts
(ply, color, is_user, san, uci, fen_before, clock_after, time_spent). Time-control parsing for
`"600"`, `"180+2"`, `"1/259200"` (daily → base/inc NULL). Result mapping per §7.1.
- AC: unit tests for time-control parsing, result mapping (every code listed), time_spent incl.
  increment, user color detection case-insensitively.

**T1.2 PGN import** (deps: T1.1) — `import` command; uuid as defined in §6; idempotent.
- AC: importing `sample_games.pgn` twice yields the same row count.

**T1.3 chess.com fetch** (deps: T1.1) — `fetch.py` per §7.1, incl. 429 backoff, ETag/Last-Modified,
current-month refetch, raw JSON saved, filters applied. HTTP is behind a small interface so tests use
`sample_archive.json` with no network.
- AC: mocked test that a second run issues requests only for the newest month; a 429 then 200
  sequence succeeds; filtered-out game types are not inserted. **GATE** (human runs a real fetch on
  their machine and reports the count).

### M2 — Openings
**T2.1 Openings DB** (deps: T0.2) — download command + EPD dict per §7.2, with header fallback.
- AC: with the TSVs present, `1.e4 c6 2.d4 d5 3.e5` resolves to Caro-Kann Defense: Advance Variation
  (B12); `opening_family` = the part before the first ":".
**T2.2 Annotate games** (deps: T2.1, T1.2) — fill `eco`, `opening_name`, `opening_family`,
`theory_exit_ply` for all games on import/fetch and via a backfill in `analyze`.
- AC: tests for theory exit on a fixture game with a known deviation point.

### M3 — Engine
**T3.1 Engine wrapper** (deps: T0.2) — context manager; configures Threads/Hash; `evaluate(board,
depth, multipv)` → list of {uci, san, cp, mate, pv}; normalizes to a given POV per §8.1; reads
`id name`.
- AC: engine-marked test: the start position evaluates within ±100 cp; a mate-in-1 FEN returns mate=1.
**T3.2 Single-game analysis** (deps: T3.1, T1.1, T2.2) — pass 1 + pass 2 for one game per §9,
returning move rows; no DB writes inside.
- AC: engine test on one fixture game: every ply has evals; pass-2 rows have multipv_json.
**T3.3 Batch, workers, resume** (deps: T3.2) — `analyze` command per §9 and §13.
- AC: killing the process mid-run and rerunning finishes the remaining games without redoing done ones
  (test with `--limit` and a forced exception); errors are recorded per game.
**T3.4 Benchmark** (deps: T3.3) — run on the fixtures (and on real data if available); record
s/game at default depths and the machine in PROGRESS.md. **GATE.**

### M4 — Classification
**T4.1 classify.py** (deps: T0.1) — pure functions for §8.2–8.8.
- AC: tests for win(0/1000/-1000), accuracy at drop 0 (= 100 after clamp) and drop 30, every class
  boundary, both §8.5 exceptions, phase boundaries, low_clock, conversion and saved flags.
**T4.2 Wire into analysis** (deps: T4.1, T3.3) — compute and store all derived columns + game
accuracy and min/max win%.
- AC: after `analyze` on the fixtures no user move has a NULL classification; the accuracy values
  are within 0–100. **GATE** (orchestrator spot-checks 3 games against lichess analysis for sanity:
  classes should broadly agree, not exactly).

### M5 — Motifs
**T5.1 Detectors + fixtures** (deps: T4.1) — §10, test-first.
**T5.2 Wire in** (deps: T5.1, T4.2) — compute `motifs_json` for qualifying moves.
- AC: over the fixtures, every inaccuracy-or-worse user move has ≥ 1 tag.

### M6 — Puzzles
**T6.1 Selection + export** (deps: T5.2) — §11, `puzzles` command.
- AC: tests on synthetic move rows covering each selection rule and the dedupe; the JSON validates
  against the documented shape; no puzzle whose `played` move is in `accepted`. **GATE.**

### M7 — Report
**T7.1 stats.py** (deps: T4.2, T5.2) — every aggregate in §12 as plain dicts, with Wilson CI helper.
- AC: unit tests on a small synthetic DB with hand-computed expected numbers.
**T7.2 charts.py** (deps: T7.1) — matplotlib → SVG strings; consistent palette; readable on light and dark.
**T7.3 Templates + report command** (deps: T7.2) — overview, mistakes, openings, games pages per §12.
- AC: `report` on the fixtures produces 4 HTML files with no Jinja errors, no external requests
  (grep for `http` in `src=`/`href=` except chess.com game links), and pages pass a quick visual check
  at 375 px and 1280 px widths (screenshots attached to the handoff if a browser is available).

### M8 — Trainer
**T8.1 trainer.html** (deps: T6.1, T7.3) — §11 trainer spec, rendered by `report`.
- AC: manual test script in the handoff: solve one correctly, fail one, reveal one, reload and see the
  boxes persist, export then import progress, the motif filter via URL hash works, and the layout
  works at 375 px. **GATE.**

### M9 — Automation
**T9.1 update + status** (deps: T8.1) — `update` pipeline; `status` real output.
**T9.2 Server setup docs** (deps: T9.1) — README section: install Stockfish on Ubuntu, create a venv,
a cron line for `update` nightly, serving `out/` on the LAN (`python -m http.server 8080 -d out`
or nginx/Caddy snippet), and a backup note for `data/chesscoach.db`.
- AC: the human follows the README on the home server from scratch without help. **GATE (final).**

---

## 15. Backlog (not scheduled — do not start without the human's go-ahead)
- Multi-move puzzles (verify each user move against the engine; auto-play opponent replies).
- Opening "repertoire drill": quiz the user's own most-played lines up to their usual exit point.
- Endgame-specific stats (rook endgame conversion, etc.).
- Natural-language explanation of a blunder via a local LLM (Ollama), strictly grounded on
  engine lines + motif tags, clearly labelled as possibly wrong.
- Sync trainer progress through a tiny local API instead of export/import.
- Lichess account support (its API also exports PGN with clocks).

---

## 16. Orchestrator review checklist (used at each GATE)
- Do the numbers make chess sense? (A queen hang must be a blunder; an opening move in book must
  not be one.)
- Spot-check 3 random user blunders against lichess analysis of the same game.
- Are all tests meaningful (not just asserting that a function returns something)?
- Any network calls in tests? Any invented engine numbers in fixtures?
- PROGRESS.md handoff complete and honest?
