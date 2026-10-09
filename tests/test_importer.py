"""PGN import tests (T1.2): idempotency, metadata, and user filtering."""

from pathlib import Path

import chess
import chess.pgn

from chesscoach.db import connect, migrate
from chesscoach.importer import compute_uuid, import_pgn_file

FIX = Path(__file__).resolve().parent / "fixtures"


def _new_conn(tmp_path):
    conn = connect(tmp_path / "test.db")
    migrate(conn)
    return conn


def _counts(conn):
    games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    moves = conn.execute("SELECT COUNT(*) FROM moves").fetchone()[0]
    return games, moves


def test_import_is_idempotent(tmp_path):
    conn = _new_conn(tmp_path)
    import_pgn_file(conn, FIX / "sample_games.pgn", "PaulMorphy")
    assert _counts(conn) == (1, 33)
    import_pgn_file(conn, FIX / "sample_games.pgn", "PaulMorphy")
    assert _counts(conn) == (1, 33)
    conn.close()


def test_import_stores_correct_metadata(tmp_path):
    conn = _new_conn(tmp_path)
    result = import_pgn_file(conn, FIX / "sample_games.pgn", "PaulMorphy")
    assert result.imported == 1
    assert result.skipped_no_user == 5

    row = conn.execute("SELECT * FROM games").fetchone()
    assert row["source"] == "pgn"
    assert row["user_color"] == "white"
    assert row["result"] == "win"
    assert row["time_class"] == "rapid"
    assert row["base_seconds"] == 600
    assert row["eco"] == "C41"
    assert row["opp_username"] == "DukeBrunswick"
    assert row["opp_rating"] == 2100
    assert row["user_rating"] == 2500
    assert row["analysis_status"] == "pending"

    move_count = conn.execute(
        "SELECT COUNT(*) FROM moves WHERE game_uuid = ?", (row["uuid"],)
    ).fetchone()[0]
    assert move_count == 33

    # Every move has a ply, san, uci, fen_before; user moves are flagged.
    sample = conn.execute(
        "SELECT * FROM moves WHERE game_uuid = ? ORDER BY ply", (row["uuid"],)
    ).fetchall()
    assert [m["ply"] for m in sample] == list(range(1, 34))
    assert all(m["fen_before"] for m in sample)
    assert [m["is_user"] for m in sample] == [1 if i % 2 == 1 else 0 for i in range(1, 34)]
    conn.close()


def test_import_skips_games_without_user(tmp_path):
    conn = _new_conn(tmp_path)
    result = import_pgn_file(conn, FIX / "sample_games.pgn", "NobodyReal")
    assert result.imported == 0
    assert result.skipped_no_user == 6
    assert _counts(conn) == (0, 0)
    conn.close()


def test_compute_uuid_is_stable():
    with open(FIX / "sample_games.pgn") as f:
        g1 = chess.pgn.read_game(f)
        f.seek(0)
        g2 = chess.pgn.read_game(f)
    assert g1 is not None and g2 is not None
    assert compute_uuid(g1) == compute_uuid(g2)


def test_compute_uuid_differs_between_games():
    with open(FIX / "sample_games.pgn") as f:
        g1 = chess.pgn.read_game(f)
        g2 = chess.pgn.read_game(f)
    assert g1 is not None and g2 is not None
    assert compute_uuid(g1) != compute_uuid(g2)
