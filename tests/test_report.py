"""Report rendering tests (T7.3) — 4 offline HTML pages, no external requests."""

import re
from pathlib import Path

from chesscoach.config import load_config
from chesscoach.db import connect, migrate
from chesscoach.report import render_report

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"
ATTR = re.compile(r'(?:src|href)="([^"]*)"')

PAGES = ("index.html", "mistakes.html", "openings.html", "games.html", "trainer.html")


def _db(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    conn.execute(
        "INSERT INTO games (uuid, source, user_color, result, pgn, time_class,"
        " user_rating, user_accuracy, opening_family, opening_name, theory_exit_ply,"
        " end_time, url, engine_id, pass1_depth, pass2_depth, analysis_status)"
        " VALUES ('g1','api','white','win','x','blitz',1300,80.0,"
        "'Caro-Kann Defense','Caro-Kann Defense: Advance Variation',10,1000,"
        "'https://www.chess.com/game/1','Stockfish 17.1',14,18,'done')"
    )
    conn.execute(
        "INSERT INTO moves (game_uuid, ply, color, is_user, san, uci, fen_before,"
        " win_drop, multipv_json, motifs_json, phase, low_clock, classification,"
        " move_accuracy, win_before, best_san, time_spent)"
        " VALUES ('g1',1,'white',1,'e4','e2e4','x',30.0,'[]','[\"hung_piece\"]',"
        "'opening',0,'blunder',40.0,50.0,'d4',3.0)"
    )
    conn.commit()
    return conn


def test_renders_all_pages(tmp_path):
    conn = _db(tmp_path)
    out = tmp_path / "out"
    pages = render_report(conn, load_config(EXAMPLE), out)
    assert [p.name for p in pages] == list(PAGES)
    for name in PAGES:
        html = (out / name).read_text()
        assert html.lstrip().startswith("<!doctype html>")
        assert "</html>" in html
        assert "chess-coach" in html
    conn.close()


def test_no_external_requests(tmp_path):
    conn = _db(tmp_path)
    out = tmp_path / "out"
    render_report(conn, load_config(EXAMPLE), out)
    for name in PAGES:
        html = (out / name).read_text()
        for value in ATTR.findall(html):
            if value.startswith("http"):
                assert value.startswith("https://www.chess.com"), (name, value)
    conn.close()


def test_empty_db_still_renders(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    out = tmp_path / "out"
    pages = render_report(conn, load_config(EXAMPLE), out)
    assert len(pages) == 5
    # the "no data" fallbacks appear
    assert "Not enough analyzed games" in (out / "index.html").read_text()
    conn.close()


def test_nav_links_are_relative(tmp_path):
    conn = _db(tmp_path)
    out = tmp_path / "out"
    render_report(conn, load_config(EXAMPLE), out)
    html = (out / "index.html").read_text()
    for target in ("mistakes.html", "openings.html", "games.html", "trainer.html"):
        assert f'href="{target}"' in html
    conn.close()
