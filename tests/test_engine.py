"""Engine wrapper tests (T3.1) — these need the real Stockfish binary.

Marked `engine`; skipped automatically when Stockfish is not on PATH.
"""

import shutil

import chess
import pytest

from chesscoach.engine import Engine

pytestmark = pytest.mark.engine

DEPTH = 12
MATE_IN_1 = "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1"
QUEEN_DOWN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1"


@pytest.fixture(scope="module")
def engine():
    path = shutil.which("stockfish") or "/usr/games/stockfish"
    if not shutil.which(path) and not path:
        pytest.skip("stockfish not installed")
    with Engine(path, threads=1, hash_mb=16) as eng:
        yield eng


def test_fixture_fen_is_valid():
    board = chess.Board(MATE_IN_1)
    assert board.is_valid()
    board.push_san("Ra8")
    assert board.is_checkmate()  # the mate-in-1 really is a mate


def test_start_position_eval_near_zero(engine):
    lines = engine.evaluate(chess.Board(), depth=DEPTH, pov=chess.WHITE)
    assert lines
    assert lines[0].cp is not None
    assert abs(lines[0].cp) <= 100
    assert lines[0].mate is None
    assert lines[0].pv_uci and lines[0].pv_uci[0] == lines[0].uci


def test_mate_in_one_returns_mate_1(engine):
    board = chess.Board(MATE_IN_1)
    lines = engine.evaluate(board, depth=DEPTH, pov=chess.WHITE)
    assert lines[0].mate == 1
    assert lines[0].cp is None


def test_score_is_from_requested_pov(engine):
    board = chess.Board(QUEEN_DOWN)  # white is a whole queen down
    assert board.is_valid()
    black_lines = engine.evaluate(board, depth=DEPTH, pov=chess.BLACK)
    white_lines = engine.evaluate(board, depth=DEPTH, pov=chess.WHITE)
    assert black_lines[0].cp is not None and black_lines[0].cp > 300
    assert white_lines[0].cp is not None and white_lines[0].cp < -300


def test_multipv_returns_ranked_lines(engine):
    lines = engine.evaluate(chess.Board(), depth=DEPTH, multipv=3, pov=chess.WHITE)
    assert len(lines) == 3
    assert len({line.uci for line in lines}) == 3


def test_id_name(engine):
    assert "stockfish" in engine.id_name.lower()
