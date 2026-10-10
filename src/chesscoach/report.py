"""Render the static HTML report — PLAN.md §12.

`render_report` writes index.html / mistakes.html / openings.html / games.html
/ trainer.html into the output directory. Everything is offline: charts are inlined SVG, styles
are in the page, the only external links are chess.com game URLs.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from chesscoach import charts
from chesscoach.config import Config
from chesscoach.puzzles import select_puzzles, strip_internal
from chesscoach.stats import build_stats

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
PAGES = [
    ("index.html", "overview.html"),
    ("mistakes.html", "mistakes.html"),
    ("openings.html", "openings.html"),
    ("games.html", "games.html"),
]


def report_meta(conn: sqlite3.Connection) -> dict:
    """Engine provenance + generation time for the footer."""
    engine = conn.execute(
        "SELECT engine_id, COUNT(*) n FROM games WHERE engine_id IS NOT NULL"
        " GROUP BY engine_id ORDER BY n DESC LIMIT 1"
    ).fetchone()
    depths = conn.execute(
        "SELECT pass1_depth, pass2_depth FROM games"
        " WHERE pass1_depth IS NOT NULL LIMIT 1"
    ).fetchone()
    analyzed = conn.execute(
        "SELECT COUNT(*) n FROM games WHERE analysis_status = 'done'"
    ).fetchone()["n"]
    return {
        "engine_id": engine["engine_id"] if engine else "n/a",
        "pass1_depth": depths["pass1_depth"] if depths else None,
        "pass2_depth": depths["pass2_depth"] if depths else None,
        "analyzed": analyzed,
        "generated": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "note": (
            "Accuracy is lichess-style, not chess.com CAPS. Motif tags are "
            "heuristics; sample sizes are shown for every rate."
        ),
    }


def build_charts(stats: dict) -> dict[str, str]:
    return {
        "rating": charts.rating_charts(stats["rating_over_time"]),
        "accuracy": charts.accuracy_chart(stats["accuracy_over_time"]),
        "phase": charts.phase_chart(stats["phase"]),
        "clock": charts.clock_chart(stats["clock"]),
        "motifs": charts.motif_chart(stats["motifs"]),
        "time": charts.time_chart(stats["time_vs_blunders"]),
    }


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals["min_games"] = 15
    return env


def render_report(
    conn: sqlite3.Connection, config: Config, out_dir: str | Path
) -> list[Path]:
    """Render every report page into `out_dir`; returns the written paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    stats = build_stats(conn, config)
    chart_svgs = build_charts(stats)
    meta = report_meta(conn)
    min_games = config.report.min_games_opening

    env = _environment()
    written: list[Path] = []
    for out_name, template_name in PAGES:
        html = env.get_template(template_name).render(
            stats=stats, charts=chart_svgs, meta=meta, min_games=min_games, page=out_name
        )
        path = out / out_name
        path.write_text(html, encoding="utf-8")
        written.append(path)

    # Trainer: self-contained page with the puzzle JSON inlined (section 11).
    puzzles = [strip_internal(p) for p in select_puzzles(conn, config)]
    trainer_html = env.get_template("trainer.html").render(
        puzzles_json=json.dumps(puzzles)
    )
    trainer_path = out / "trainer.html"
    trainer_path.write_text(trainer_html, encoding="utf-8")
    written.append(trainer_path)
    return written
