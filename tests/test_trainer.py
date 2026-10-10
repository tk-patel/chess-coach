"""Trainer page tests (T8.1) — self-contained, puzzle JSON inlined, offline."""

import json
import re
from pathlib import Path

import chess

from chesscoach.config import load_config
from chesscoach.db import connect, migrate
from chesscoach.puzzles import _EXPORT_KEYS
from chesscoach.report import render_report

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"
DATA = re.compile(
    r'<script type="application/json" id="puzzles">(.*?)</script>', re.DOTALL
)


def _db_with_puzzle(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    conn.execute(
        "INSERT INTO games (uuid, source, user_color, result, pgn, time_class,"
        " url, end_time, opening_name) VALUES"
        " ('g1','api','white','loss','x','blitz','https://www.chess.com/game/1',"
        " 1000,'Caro-Kann Defense: Advance Variation')"
    )
    mpv = json.dumps([
        {"uci": "c1g5", "san": "Bg5", "cp": 20, "mate": None, "win": 60.0},
        {"uci": "d2d4", "san": "d4", "cp": 10, "mate": None, "win": 40.0},
    ])
    conn.execute(
        "INSERT INTO moves (game_uuid, ply, color, is_user, san, uci, fen_before,"
        " win_drop, multipv_json, pv_uci, motifs_json, phase, low_clock,"
        " classification) VALUES ('g1',3,'white',1,'Qxb7','d5b7',?,30.0,?,"
        " 'c1g5 d8c8', '[\"hung_piece\"]','middlegame',1,'blunder')",
        (chess.Board().fen(), mpv),
    )
    conn.commit()
    return conn


def test_trainer_inlines_puzzle_json(tmp_path):
    conn = _db_with_puzzle(tmp_path)
    out = tmp_path / "out"
    pages = render_report(conn, load_config(EXAMPLE), out)
    assert (out / "trainer.html") in pages

    html = (out / "trainer.html").read_text()
    match = DATA.search(html)
    assert match, "the puzzle JSON must be inlined in a script tag"
    data = json.loads(match.group(1))
    assert len(data) == 1
    assert set(data[0]) == set(_EXPORT_KEYS)
    assert data[0]["accepted"] == ["c1g5"]
    assert data[0]["played_san"] == "Qxb7??"
    assert data[0]["motifs"] == ["hung_piece"]

    # self-contained + offline
    assert "chesscoach.srs.v1" in html          # Leitner state key
    assert "localStorage" in html
    assert 'id="f-motif"' in html               # filters
    assert "URL.createObjectURL" in html        # export progress
    conn.close()


def test_trainer_has_no_external_assets(tmp_path):
    conn = _db_with_puzzle(tmp_path)
    out = tmp_path / "out"
    render_report(conn, load_config(EXAMPLE), out)
    html = (out / "trainer.html").read_text()
    for value in re.findall(r'(?:src|href)="([^"]*)"', html) + \
            re.findall(r"href='([^']*)'", html):
        if value.startswith("http"):
            assert value.startswith("https://www.chess.com")
    # no external stylesheet or script includes
    assert "<link" not in html
    assert "<script src" not in html
    conn.close()


def test_trainer_with_no_puzzles_is_empty_list(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    out = tmp_path / "out"
    render_report(conn, load_config(EXAMPLE), out)
    match = DATA.search((out / "trainer.html").read_text())
    assert match and json.loads(match.group(1)) == []
    conn.close()
