# chess-coach

Personal chess.com game analysis: download your games, analyze them with Stockfish, and get
(1) a blunder profile report and (2) a personal puzzle trainer built from your own mistakes.

## Install

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
python -m chesscoach init          # create data/, out/, the DB, and config.toml
```

## The three commands a human runs

```sh
python -m chesscoach update        # fetch -> analyze -> puzzles -> report
python -m chesscoach status        # what's in the DB
```

Then open `out/index.html` in a browser (or serve `out/` on the LAN).

Full docs: `PLAN.md`.
