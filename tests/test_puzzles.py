"""Puzzle selection/export tests (T6.1) — synthetic move rows, no engine."""

import json
from pathlib import Path

import chess

from chesscoach.config import load_config
from chesscoach.db import connect, migrate
from chesscoach.puzzles import (
    _EXPORT_KEYS,
    rebuild,
    select_puzzles,
    store_puzzles,
    strip_internal,
)

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"
START = chess.Board().fen()


def _config():
    return load_config(EXAMPLE)


def _db(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    return conn


def _game(conn, uuid, user_color="white", end_time=1000, opening="Caro-Kann Defense",
          url="https://www.chess.com/game/1"):
    conn.execute(
        "INSERT INTO games (uuid, source, user_color, result, pgn, opening_name,"
        " url, end_time) VALUES (?, 'api', ?, 'loss', ?, ?, ?, ?)",
        (uuid, user_color, "[Event \"x\"]\n\n*\n", opening, url, end_time),
    )
    conn.commit()


def _move(conn, uuid, ply=3, san="Qxb7", uci="d5b7", win_drop=30.0, mpv=None,
          pv_uci="e2e4", motifs=None, phase="middlegame", low_clock=0,
          classification="blunder", fen=START):
    conn.execute(
        "INSERT INTO moves (game_uuid, ply, color, is_user, san, uci, fen_before,"
        " win_drop, multipv_json, pv_uci, motifs_json, phase, low_clock,"
        " classification) VALUES (?, ?, 'white', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (uuid, ply, san, uci, fen, win_drop, mpv, pv_uci,
         json.dumps(motifs or []), phase, low_clock, classification),
    )
    conn.commit()


def _mpv(*entries):
    """entries: (uci, san, win)."""
    return json.dumps(
        [{"uci": u, "san": s, "cp": 0, "mate": None, "win": w} for u, s, w in entries]
    )


def _one_puzzle(tmp_path, **move_kwargs):
    conn = _db(tmp_path)
    _game(conn, "g1")
    _move(conn, "g1", **move_kwargs)
    puzzles = select_puzzles(conn, _config())
    conn.close()
    return puzzles


def test_basic_qualifying_puzzle(tmp_path):
    puzzles = _one_puzzle(
        tmp_path, win_drop=34.2, uci="d5b7",
        mpv=_mpv(("c1g5", "Bg5", 60.0), ("d2d4", "d4", 40.0)),
    )
    assert len(puzzles) == 1
    p = puzzles[0]
    assert p["accepted"] == ["c1g5"]  # 40 is >3 below 60
    assert p["solution_uci"] == "c1g5"
    assert p["solution_san"] == "Bg5"
    assert p["played_san"] == "Qxb7??"
    assert p["multi_answer"] is False
    assert p["seen_count"] == 1
    assert p["orientation"] == "white"


def test_rule1_min_drop(tmp_path):
    assert _one_puzzle(tmp_path, win_drop=15.0,
                       mpv=_mpv(("c1g5", "Bg5", 60.0))) == []


def test_rule2_min_best_winpct(tmp_path):
    assert _one_puzzle(tmp_path, win_drop=30.0,
                       mpv=_mpv(("c1g5", "Bg5", 30.0))) == []


def test_rule5_played_move_is_accepted(tmp_path):
    # played move IS the best move → excluded
    assert _one_puzzle(tmp_path, uci="c1g5",
                       mpv=_mpv(("c1g5", "Bg5", 60.0))) == []


def test_rule4_multi_answer(tmp_path):
    puzzles = _one_puzzle(
        tmp_path, uci="a2a3",
        mpv=_mpv(("c1g5", "Bg5", 60.0), ("d2d4", "d4", 58.0)),
    )
    assert len(puzzles) == 1
    assert puzzles[0]["accepted"] == ["c1g5", "d2d4"]
    assert puzzles[0]["multi_answer"] is True


def test_no_multipv_excluded(tmp_path):
    assert _one_puzzle(tmp_path, mpv=None) == []


def test_dedupe_keeps_most_recent_and_counts(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "g1", end_time=1000, url="https://x/old")
    _move(conn, "g1", mpv=_mpv(("c1g5", "Bg5", 60.0)))
    _game(conn, "g2", end_time=2000, url="https://x/new")
    _move(conn, "g2", mpv=_mpv(("c1g5", "Bg5", 60.0)))

    puzzles = select_puzzles(conn, _config())
    assert len(puzzles) == 1
    assert puzzles[0]["seen_count"] == 2
    assert puzzles[0]["game_url"] == "https://x/new"  # most recent kept
    conn.close()


def test_played_within_accept_within_is_excluded(tmp_path):
    # played move is within accept_within of the best → it would be "accepted",
    # so rule 5 must drop the puzzle.
    conn = _db(tmp_path)
    _game(conn, "g1")
    _move(conn, "g1", uci="d2d4",
          mpv=_mpv(("c1g5", "Bg5", 60.0), ("d2d4", "d4", 59.0)))
    assert select_puzzles(conn, _config()) == []
    conn.close()


def test_export_shape_and_store(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "g1")
    _move(conn, "g1", mpv=_mpv(("c1g5", "Bg5", 60.0)), motifs=["hung_piece"])
    out = tmp_path / "puzzles.json"
    count = rebuild(conn, _config(), out)
    assert count == 1

    data = json.loads(out.read_text())
    assert len(data) == 1
    assert list(data[0].keys()) == _EXPORT_KEYS  # documented order/shape
    sample = data[0]
    assert set(sample) == set(_EXPORT_KEYS)
    assert sample["motifs"] == ["hung_piece"]
    # stored in the table too
    assert conn.execute("SELECT COUNT(*) n FROM puzzles").fetchone()["n"] == 1
    conn.close()


def test_strip_internal_drops_private_keys():
    record: dict = {key: None for key in _EXPORT_KEYS}
    record["_end_time"] = 123
    record["game_uuid"] = "g1"
    stripped = strip_internal(record)
    assert "_end_time" not in stripped and "game_uuid" not in stripped


def test_store_replaces(tmp_path):
    conn = _db(tmp_path)
    store_puzzles(conn, [])  # no-op on empty
    assert conn.execute("SELECT COUNT(*) n FROM puzzles").fetchone()["n"] == 0
    conn.close()
