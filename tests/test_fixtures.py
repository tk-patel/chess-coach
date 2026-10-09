"""Fixture validation tests (T0.3).

Every PGN in the fixture must be real and parse cleanly: all moves legal, the
board valid throughout, and the clock comments readable by python-chess.
"""

import io
import json
from pathlib import Path

import chess
import chess.pgn

FIX = Path(__file__).resolve().parent / "fixtures"


def _read_games() -> list[chess.pgn.Game]:
    games = []
    with open(FIX / "sample_games.pgn") as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            games.append(game)
    return games


def test_sample_games_parse_with_zero_errors():
    games = _read_games()
    assert len(games) >= 6

    for game in games:
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)  # raises ValueError on any illegal move
        assert board.is_valid()


def test_sample_games_cover_required_results():
    results = {game.headers["Result"] for game in _read_games()}
    assert {"1-0", "0-1", "1/2-1/2"} <= results


def test_sample_games_include_timeout_and_daily():
    games = _read_games()
    terminations = {game.headers.get("Termination", "") for game in games}
    assert any("time" in t.lower() for t in terminations), "no timeout-terminated game"
    controls = {game.headers.get("TimeControl", "") for game in games}
    assert any(c.startswith("1/") for c in controls), "no daily (1/N) time control"


def test_clocks_are_readable_and_daily_has_none():
    games = _read_games()
    clocked = [g for g in games if g.headers.get("TimeControl", "") != "1/259200"]
    assert clocked, "expected clocked games"
    for game in clocked:
        first_node = game.next()
        assert first_node is not None
        assert first_node.clock() is not None
    daily = next(g for g in games if g.headers.get("TimeControl", "") == "1/259200")
    assert daily.next().clock() is None


def test_sample_archive_has_expected_shape():
    with open(FIX / "sample_archive.json") as f:
        archive = json.load(f)
    games = archive["games"]
    assert len(games) >= 3
    for g in games:
        assert set(g) >= {"url", "pgn", "time_control", "end_time", "rated", "uuid",
                          "time_class", "rules", "white", "black", "eco"}
        assert set(g["white"]) >= {"username", "rating", "result"}
        assert set(g["black"]) >= {"username", "rating", "result"}
        # The embedded PGN must itself parse.
        parsed = chess.pgn.read_game(io.StringIO(g["pgn"]))
        assert parsed is not None
