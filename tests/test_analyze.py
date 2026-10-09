"""Single-game analysis tests (T3.2) — engine-marked."""

import json
from pathlib import Path

import pytest

from chesscoach.analyze import analyze_game
from chesscoach.config import load_config
from chesscoach.engine import Engine
from chesscoach.parse import parse_game

pytestmark = pytest.mark.engine

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"

FOOLS_MATE = """[Event "Test"]
[White "User"]
[Black "Opp"]
[Result "0-1"]
[TimeControl "300"]
[UTCDate "2026.01.01"]
[UTCTime "00:00:00"]

1. f3 e5 2. g4 Qh4# 0-1
"""


@pytest.fixture(scope="module")
def engine():
    with Engine(path="stockfish", threads=1, hash_mb=64) as eng:
        yield eng


def test_every_ply_has_evals_and_pass2_rows(engine):
    config = load_config(EXAMPLE)
    parsed = parse_game(FOOLS_MATE, "User")
    assert parsed.user_color == "white"

    analysis = analyze_game(parsed, engine, config)

    assert len(analysis.moves) == 4
    assert "stockfish" in analysis.engine_id.lower()

    for move in analysis.moves:
        assert (move.cp_before is not None) or (move.mate_before is not None)
        assert (move.cp_after is not None) or (move.mate_after is not None)
        assert move.phase in {"opening", "middlegame", "endgame"}

    # 2. g4?? is a user blunder → pass 2 must have deepened it.
    g4 = next(m for m in analysis.moves if m.san == "g4")
    assert g4.is_user
    assert g4.multipv_json is not None
    entries = json.loads(g4.multipv_json)
    assert len(entries) == config.engine.pass2_multipv
    assert all({"uci", "san", "cp", "mate", "win"} <= set(e) for e in entries)

    # opponent plies are never deepened by pass 2
    e5 = next(m for m in analysis.moves if m.san == "e5")
    assert not e5.is_user
    assert e5.multipv_json is None


def test_user_moves_are_classified(engine):
    config = load_config(EXAMPLE)
    parsed = parse_game(FOOLS_MATE, "User")
    analysis = analyze_game(parsed, engine, config)

    user_moves = [m for m in analysis.moves if m.is_user]
    assert user_moves and all(m.classification is not None for m in user_moves)

    # the mating blunder should be a mistake or blunder
    g4 = next(m for m in analysis.moves if m.san == "g4")
    assert g4.classification in {"mistake", "blunder"}


def test_final_position_mate_after_from_result(engine):
    config = load_config(EXAMPLE)
    parsed = parse_game(FOOLS_MATE, "User")
    analysis = analyze_game(parsed, engine, config)

    last = analysis.moves[-1]
    assert last.san == "Qh4#"
    assert last.mate_after == -1  # the user was mated
    assert last.win_after == 0.0
