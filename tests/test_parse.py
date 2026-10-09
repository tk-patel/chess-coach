"""Unit tests for parse.py (T1.1): time controls, result mapping, clocks, colors."""

from pathlib import Path

import chess
import chess.pgn
import pytest

from chesscoach.parse import (
    detect_user_color,
    parse_game,
    parse_time_control,
    result_code_to_result,
    time_class_from_control,
    user_result_from_pgn,
)

FIX = Path(__file__).resolve().parent / "fixtures"


def _fixture_pgn(white: str) -> str:
    with open(FIX / "sample_games.pgn") as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            if game.headers["White"] == white:
                return str(game)
    raise AssertionError(f"fixture game with White={white} not found")


# --- time control parsing -------------------------------------------------

def test_parse_time_control_plain():
    assert parse_time_control("600") == (600, 0)


def test_parse_time_control_increment():
    assert parse_time_control("180+2") == (180, 2)


def test_parse_time_control_daily():
    assert parse_time_control("1/259200") == (None, None)


def test_parse_time_control_empty():
    assert parse_time_control("") == (None, None)


def test_time_class_mapping():
    assert time_class_from_control(None) == "daily"
    assert time_class_from_control(60) == "bullet"
    assert time_class_from_control(180) == "blitz"
    assert time_class_from_control(300) == "blitz"
    assert time_class_from_control(600) == "rapid"


# --- result code mapping (every code in §7.1) -----------------------------

@pytest.mark.parametrize("code", ["win"])
def test_result_code_win(code):
    assert result_code_to_result(code) == "win"


@pytest.mark.parametrize(
    "code", ["agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"]
)
def test_result_code_draw(code):
    assert result_code_to_result(code) == "draw"


@pytest.mark.parametrize(
    "code", ["checkmated", "resigned", "timeout", "abandoned", "lose", "something_else"]
)
def test_result_code_loss(code):
    assert result_code_to_result(code) == "loss"


def test_user_result_from_pgn():
    assert user_result_from_pgn("1-0", "white") == "win"
    assert user_result_from_pgn("0-1", "white") == "loss"
    assert user_result_from_pgn("0-1", "black") == "win"
    assert user_result_from_pgn("1-0", "black") == "loss"
    assert user_result_from_pgn("1/2-1/2", "white") == "draw"
    assert user_result_from_pgn("1/2-1/2", "black") == "draw"


# --- user color detection (case-insensitive) ------------------------------

def test_detect_user_color_white_case_insensitive():
    assert detect_user_color("PaulMorphy", "DukeBrunswick", "paulmorphy") == "white"


def test_detect_user_color_black():
    assert detect_user_color("White", "Black", "BLACK") == "black"


def test_detect_user_color_none():
    assert detect_user_color("A", "B", "C") is None


# --- time spent, including increment --------------------------------------

def test_time_spent_with_increment():
    pg = parse_game(_fixture_pgn("Legall"), "Legall")
    first = pg.moves[0]
    assert first.color == "white"
    assert first.is_user is True
    assert first.clock_after == 177
    assert first.time_spent == pytest.approx(5.0)  # 180 - 177 + 2


def test_time_spent_without_increment():
    pg = parse_game(_fixture_pgn("PaulMorphy"), "PaulMorphy")
    first = pg.moves[0]
    assert first.clock_after == 594
    assert first.time_spent == pytest.approx(6.0)  # 600 - 594


# --- full game parsing ----------------------------------------------------

def test_parse_operatic_game():
    pg = parse_game(_fixture_pgn("PaulMorphy"), "paulmorphy")
    assert pg.user_color == "white"
    assert pg.result == "win"
    assert pg.base_seconds == 600
    assert pg.increment_seconds == 0
    assert pg.time_class == "rapid"
    assert pg.ply_count == 33
    assert len(pg.moves) == 33
    assert pg.moves[-1].san.endswith("#")
    assert pg.eco == "C41"


def test_parse_daily_game_has_no_clocks():
    pg = parse_game(_fixture_pgn("Scholar"), "Scholar")
    assert pg.time_class == "daily"
    assert pg.base_seconds is None
    assert pg.increment_seconds is None
    assert all(m.clock_after is None for m in pg.moves)
    assert all(m.time_spent is None for m in pg.moves)


def test_user_color_none_when_username_missing():
    pg = parse_game(_fixture_pgn("PaulMorphy"), "someoneelse")
    assert pg.user_color is None
    assert pg.result is None
    assert all(m.is_user is False for m in pg.moves)
