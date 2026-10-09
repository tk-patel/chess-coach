"""classify.py tests (T4.1) — hand-computed values from PLAN.md §8."""

import chess
import pytest

from chesscoach.classify import (
    classify_move,
    failed_conversion,
    game_accuracy,
    low_clock,
    move_accuracy,
    non_pawn_material,
    phase,
    saved_game,
    win_drop,
    win_percentage,
)

START = chess.Board().fen()
KQ_VS_K = "8/8/8/4k3/8/8/4Q3/4K3 w - - 0 1"


def test_win_percentage_anchors():
    assert win_percentage(cp=0) == 50.0
    assert abs(win_percentage(cp=1000) - 97.5) < 0.1
    assert abs(win_percentage(cp=-1000) - 2.5) < 0.1
    assert win_percentage(cp=1000) > 97.0
    assert win_percentage(cp=-1000) < 3.0


def test_win_percentage_mate():
    assert win_percentage(mate=1) == 100.0
    assert win_percentage(mate=-3) == 0.0
    assert win_percentage(mate=1) > win_percentage(cp=1000)


def test_win_percentage_needs_an_argument():
    with pytest.raises(ValueError):
        win_percentage()


def test_win_drop_floor():
    assert win_drop(60.0, 30.0) == 30.0
    assert win_drop(30.0, 60.0) == 0.0  # improvement → 0


def test_move_accuracy_anchors():
    assert abs(move_accuracy(0.0) - 100.0) < 0.01
    assert abs(move_accuracy(30.0) - 24.78) < 0.05
    assert move_accuracy(1e9) == 0.0  # clamped at 0
    # monotonic decreasing in the drop
    assert move_accuracy(5) > move_accuracy(15) > move_accuracy(40)


def test_game_accuracy_mean():
    assert game_accuracy([100.0, 80.0, 90.0]) == 90.0
    assert game_accuracy([]) == 0.0


def test_classify_boundaries():
    assert classify_move(0.0, is_best=False) == "good"
    assert classify_move(9.99, is_best=False) == "good"
    assert classify_move(10.0, is_best=False) == "inaccuracy"
    assert classify_move(19.99, is_best=False) == "inaccuracy"
    assert classify_move(20.0, is_best=False) == "mistake"
    assert classify_move(29.99, is_best=False) == "mistake"
    assert classify_move(30.0, is_best=False) == "blunder"
    assert classify_move(99.0, is_best=False) == "blunder"


def test_classify_best_wins_over_drop():
    assert classify_move(80.0, is_best=True) == "best"


def test_classify_still_winning_cap():
    # drop 10 would be an inaccuracy, but both sides of the move are winning.
    assert classify_move(10.0, is_best=False, win_before=100.0, win_after=90.0) == "good"
    # a genuine collapse while still technically winning is NOT capped:
    assert classify_move(60.0, is_best=False, win_before=100.0, win_after=40.0) == "blunder"


def test_classify_already_lost_cap():
    assert classify_move(2.0, is_best=False, win_before=2.0, win_after=0.0) == "good"
    # if the mover was already lost, a 30-point drop is noise → good
    assert classify_move(30.0, is_best=False, win_before=3.0, win_after=0.0) == "good"


def test_non_pawn_material():
    assert non_pawn_material(START) == 62  # 2*(3+3+5)+9 per side
    assert non_pawn_material(KQ_VS_K) == 9


def test_phase_boundaries():
    assert phase(START, ply=1, theory_exit_ply=None, opening_max_ply=24,
                 endgame_material=26) == "opening"
    assert phase(START, ply=24, theory_exit_ply=None, opening_max_ply=24,
                 endgame_material=26) == "opening"
    assert phase(START, ply=25, theory_exit_ply=None, opening_max_ply=24,
                 endgame_material=26) == "middlegame"
    # out of book late keeps it "opening" even past opening_max_ply
    assert phase(START, ply=25, theory_exit_ply=30, opening_max_ply=24,
                 endgame_material=26) == "opening"
    # material rule wins over everything
    assert phase(KQ_VS_K, ply=1, theory_exit_ply=None, opening_max_ply=24,
                 endgame_material=26) == "endgame"


def test_low_clock():
    # base 600 → threshold max(30, 60) = 60
    assert low_clock(45.0, 600) == 1
    assert low_clock(60.0, 600) == 0
    assert low_clock(100.0, 600) == 0
    # base 60 → threshold max(30, 6) = 30
    assert low_clock(29.0, 60) == 1
    assert low_clock(31.0, 60) == 0
    # daily / unknown clock
    assert low_clock(45.0, None) is None
    assert low_clock(None, 600) is None


def test_failed_conversion():
    moves = [(21, 90.0), (24, 88.0), (27, 50.0)]
    assert failed_conversion(moves, "loss") is True
    assert failed_conversion(moves, "draw") is True
    assert failed_conversion(moves, "win") is False  # they converted
    assert failed_conversion([(21, 90.0)], "loss") is False  # only one hit
    # plies at or before 20 do not count
    assert failed_conversion([(20, 90.0), (19, 99.0)], "loss") is False


def test_saved_game():
    moves = [(21, 10.0), (24, 5.0)]
    assert saved_game(moves, "draw") is True
    assert saved_game(moves, "win") is True
    assert saved_game(moves, "loss") is False
    assert saved_game([(21, 10.0)], "draw") is False
