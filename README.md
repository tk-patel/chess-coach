# chess-coach

Personal chess.com game analysis: download your games, analyze them with Stockfish, and get
(1) a blunder profile report and (2) a personal puzzle trainer built from your own mistakes.

Everything runs locally as a Python CLI. Outputs are static HTML files in `out/` that open via
`file://` or any static file server on your LAN. Full design: `PLAN.md`.

---

## Quick start

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e .[dev]

python -m chesscoach init              # create data/, out/, the DB, and config.toml
# edit config.toml -> set [player] username to your chess.com handle
python -m chesscoach openings download # one-time: lichess openings DB into data/openings/
python -m chesscoach update            # fetch -> analyze -> puzzles -> report
```

Open `out/index.html` in a browser. The trainer is `out/trainer.html`.

Two commands you'll actually re-run:

```sh
python -m chesscoach update   # the whole pipeline (safe to run repeatedly; it's incremental)
python -m chesscoach status   # games by analysis state, puzzles, last fetch, engine id
```

---

## Home-server setup (Ubuntu, from scratch)

These steps assume a fresh Ubuntu box (e.g. the i7 home server). Run them once.

### 1. System packages

```sh
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip stockfish git
stockfish --help | head -1     # confirm the engine runs
```

### 2. Get the code and create a virtualenv

```sh
cd ~                       # or wherever you keep projects
git clone https://github.com/tk-patel/chess-coach.git chess-coach
cd chess-coach
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e .
```

### 3. Initialise and configure

```sh
python -m chesscoach init
```

This writes `config.toml` (git-ignored), creates `data/`, `data/raw/`, `data/openings/`, `out/`,
and the SQLite DB. Edit `config.toml`:

- `[player] username` — **required**; your chess.com username (compared case-insensitively).
- `[engine] path` — leave as `stockfish` (found on `PATH`), or an absolute path to a binary.
- `[engine] workers` — how many games analyze in parallel; set to **CPU cores − 1**.
- Depths/limits are fine at their defaults (`pass1_depth = 14`, `pass2_depth = 18`).

### 4. Opening database (one-time)

```sh
python -m chesscoach openings download   # writes data/openings/{a..e}.tsv
```

If the network is blocked, it prints the 5 URLs to fetch manually; drop those files into
`data/openings/` and continue. Without them, games still import (opening names fall back to PGN
headers).

### 5. First import

Preferred (uses the chess.com public API, no password needed):

```sh
python -m chesscoach fetch        # incremental; safe to re-run
```

Alternative / extra input — export your games as PGN from chess.com and import the file:

```sh
python -m chesscoach import ~/Downloads/mygames.pgn
```

### 6. Analyze and build the report

```sh
python -m chesscoach analyze      # two-pass Stockfish; commits after every game, resumable
python -m chesscoach puzzles      # out/puzzles.json
python -m chesscoach report       # out/*.html incl. trainer.html
```

`update` runs fetch → analyze → puzzles → report in one go (see below).

---

## Nightly automation (cron)

Add a cron entry that runs the whole pipeline each night. Cron uses a minimal `PATH`, so use the
venv's absolute paths:

```cron
# crontab -e
30 3 * * * cd /home/<you>/chess-coach && /home/<you>/chess-coach/.venv/bin/python -m chesscoach update >> /home/<you>/chess-coach/data/update.log 2>&1
```

`update` is best-effort per step: a blocked network or a missing engine is logged and skipped
rather than killing the run, and `analyze` resumes only the games not yet done.

---

## Serving the report on the LAN

The report is static HTML, so any static server works.

**Quick and dirty** (bind to your LAN IP so other devices can reach it):

```sh
python -m http.server 8080 --bind 0.0.0.0 -d out
# then browse http://<server-ip>:8080/
```

**nginx** (drop-in):

```nginx
server {
    listen 8080;
    root /home/<you>/chess-coach/out;
    index index.html;
    location / { try_files $uri $uri/ =404; }
}
```

**Caddy** (two lines):

```caddy
:8080 {
    root * /home/<you>/chess-coach/out
    file_server
}
```

Open `http://<server-ip>:8080/` on your phone to use the trainer.

---

## Backup

All state lives in one file: `data/chesscoach.db` (plus `out/`, which is regenerable, and
`data/raw/`, the downloaded JSON). Back up the DB nightly, e.g. with SQLite's online backup:

```sh
mkdir -p ~/chesscoach-backups
sqlite3 /home/<you>/chess-coach/data/chesscoach.db \
  ".backup '/home/<you>/chesscoach-backups/chesscoach-$(date +%F).db'"
```

Keep the last ~30 files (`find ~/chesscoach-backups -mtime +30 -delete`). To restore, stop
`update`/serving, copy the file back to `data/chesscoach.db`, and restart.

---

## Command reference

| Command | What it does |
|---|---|
| `python -m chesscoach init` | Create `data/`, `out/`, the DB, and `config.toml`. |
| `python -m chesscoach openings download` | Fetch the lichess openings TSVs into `data/openings/`. |
| `python -m chesscoach fetch` | chess.com API → `data/raw/` → games table (incremental). |
| `python -m chesscoach import FILE.pgn` | Import games from a PGN file. |
| `python -m chesscoach analyze [--limit N] [--since YYYY-MM-DD] [--reanalyze]` | Two-pass Stockfish analysis. |
| `python -m chesscoach puzzles` | Rebuild the puzzles table + `out/puzzles.json`. |
| `python -m chesscoach report` | Write `out/*.html` (incl. `trainer.html`). |
| `python -m chesscoach update` | fetch → analyze → puzzles → report (for cron). |
| `python -m chesscoach status` | Counts: games by state, puzzles, last fetch, engine id. |

## Notes

- Accuracy is **lichess-style**, not chess.com CAPS; motif tags are **heuristics** — both are
  labelled in the report footer.
- Never commit `config.toml`, `data/`, or `out/` (they are git-ignored).
- Never enter your chess.com password anywhere — the public API needs only your username.
