"""Command-line interface for chess-coach.

Thin wrappers over the workhorse modules; the real logic lives elsewhere and is
wired in task by task. Every command currently exists as a stub so `--help`
lists the full surface from PLAN.md §13.
"""

from pathlib import Path
from typing import Annotated

import typer

from chesscoach import db

app = typer.Typer(
    no_args_is_help=True,
    help="Analyze your chess.com games and build a personal puzzle trainer.",
)
openings_app = typer.Typer(help="Openings database management.")
app.add_typer(openings_app, name="openings")


def _stub(name: str) -> None:
    typer.echo(f"{name}: not implemented")


def _example_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config.example.toml"


@app.command()
def init() -> None:
    """Create data/, out/, the SQLite DB, and config.toml if missing."""
    root = Path.cwd()

    config_path = root / "config.toml"
    if config_path.exists():
        typer.echo(f"config.toml already exists at {config_path}")
    else:
        example = _example_config_path()
        if not example.exists():
            typer.echo(f"error: cannot find example config at {example}", err=True)
            raise typer.Exit(1)
        config_path.write_text(example.read_text(), encoding="utf-8")
        typer.echo(f"wrote {config_path} (edit your username there)")

    for directory in ("data", "data/raw", "data/openings", "out"):
        (root / directory).mkdir(parents=True, exist_ok=True)

    db_path = root / "data" / "chesscoach.db"
    conn = db.connect(db_path)
    try:
        version = db.migrate(conn)
    finally:
        conn.close()
    typer.echo(f"initialized {db_path} (schema v{version})")


@app.command()
def status() -> None:
    """Show counts: games by status, puzzles, last fetch, engine id."""
    _stub("status")


@openings_app.command()
def download() -> None:
    """Fetch the lichess openings TSVs into data/openings/."""
    _stub("openings download")


@app.command()
def fetch() -> None:
    """Download games from the chess.com API (incremental)."""
    from chesscoach.config import load_config, require_username
    from chesscoach.fetch import FetchError, RequestsTransport, fetch_all

    root = Path.cwd()
    config = load_config(root / "config.toml")
    require_username(config)
    transport = RequestsTransport(config.fetch.user_agent)

    db_path = root / "data" / "chesscoach.db"
    conn = db.connect(db_path)
    try:
        db.migrate(conn)
        try:
            result = fetch_all(conn, config, transport, root / "data" / "raw")
        except FetchError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(1) from exc
    finally:
        conn.close()

    typer.echo(
        f"fetched {result.inserted} games "
        f"({result.filtered} filtered, {result.skipped_months} months skipped, "
        f"{result.errors} errors)"
    )


@app.command("import")
def import_(file: Annotated[str, typer.Argument(help="Path to a PGN file")]) -> None:
    """Import a PGN file as an alternative/extra input."""
    from chesscoach.config import load_config, require_username
    from chesscoach.importer import import_pgn_file

    root = Path.cwd()
    config = load_config(root / "config.toml")
    username = require_username(config)

    db_path = root / "data" / "chesscoach.db"
    conn = db.connect(db_path)
    try:
        db.migrate(conn)
        result = import_pgn_file(conn, Path(file), username)
    finally:
        conn.close()

    typer.echo(
        f"imported {result.imported} games, "
        f"skipped {result.skipped_existing} existing, "
        f"{result.skipped_no_user} without user"
    )


@app.command()
def analyze(
    limit: Annotated[int | None, typer.Option(help="Only analyze this many games")] = None,
    since: Annotated[str | None, typer.Option(help="Only games on/after YYYY-MM-DD")] = None,
    reanalyze: Annotated[bool, typer.Option(help="Reset everything to pending first")] = False,
) -> None:
    """Analyze pending games with Stockfish (two passes)."""
    _stub("analyze")


@app.command()
def puzzles() -> None:
    """Rebuild the puzzles table and out/puzzles.json."""
    _stub("puzzles")


@app.command()
def report() -> None:
    """Render the report and trainer HTML into out/."""
    _stub("report")


@app.command()
def update() -> None:
    """Fetch, analyze, build puzzles, and render the report (for cron)."""
    _stub("update")
