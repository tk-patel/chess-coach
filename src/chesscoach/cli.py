"""Command-line interface for chess-coach.

Thin wrappers over the workhorse modules; the real logic lives elsewhere and is
wired in task by task. Every command currently exists as a stub so `--help`
lists the full surface from PLAN.md §13.
"""

from typing import Annotated

import typer

app = typer.Typer(
    no_args_is_help=True,
    help="Analyze your chess.com games and build a personal puzzle trainer.",
)
openings_app = typer.Typer(help="Openings database management.")
app.add_typer(openings_app, name="openings")


def _stub(name: str) -> None:
    typer.echo(f"{name}: not implemented")


@app.command()
def init() -> None:
    """Create data/, out/, the SQLite DB, and config.toml if missing."""
    _stub("init")


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
    _stub("fetch")


@app.command("import")
def import_(file: Annotated[str, typer.Argument(help="Path to a PGN file")]) -> None:
    """Import a PGN file as an alternative/extra input."""
    _stub(f"import {file}")


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
