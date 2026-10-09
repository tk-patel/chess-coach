"""Pure classification math — PLAN.md §8.2–§8.8.

No I/O, no engine, no DB: every function takes numbers/FENs and returns numbers,
so the whole module is unit-testable with hand-computed expectations.

`win`/`win_drop`/`move_accuracy`/`classify_move`/`phase`/`low_clock` follow the
Definitions section exactly. All win% values are 0–100.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import chess

MATE_WIN = 100.0
MATE_LOSS = 0.0

# §8.5 thresholds
INACCURACY = 10.0
MISTAKE = 20.0
BLUNDER = 30.0
STILL_WINNING_BEFORE = 97.0
STILL_WINNING_AFTER = 90.0
ALREADY_LOST = 3.0
CONVERSION_WIN = 85.0
RESOURCEFUL_LOSS = 15.0
CONVERSION_MIN_PLY = 20

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def win_percentage(cp: int | None = None, mate: int | None = None) -> float:
    """Lichess win% (§8.2): win(0)=50, win(1000)≈97.5, win(-1000)≈2.5."""
    if mate is not None:
        return MATE_WIN if mate > 0 else MATE_LOSS
    if cp is None:
        raise ValueError("win_percentage needs cp or mate")
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-0.00368208 * cp)) - 1.0)


def win_drop(win_before: float, win_after: float) -> float:
    """Mover-POV drop, floored at 0 (§8.3)."""
    return max(0.0, win_before - win_after)


def move_accuracy(drop: float) -> float:
    """Lichess-style move accuracy for a given win% drop (§8.4), clamped 0–100."""
    raw = 103.1668 * math.exp(-0.04354 * drop) - 3.1669
    return max(0.0, min(100.0, raw))


def game_accuracy(move_accuracies: Iterable[float]) -> float:
    """Arithmetic mean of move accuracies (§8.4); 0.0 for an empty side.

    Callers exclude plies ≤ theory_exit_ply before calling.
    """
    values = list(move_accuracies)
    if not values:
        return 0.0
    return sum(values) / len(values)


def classify_move(
    drop: float,
    is_best: bool,
    win_before: float | None = None,
    win_after: float | None = None,
) -> str:
    """Classify a user move (§8.5): best|good|inaccuracy|mistake|blunder."""
    if is_best:
        return "best"
    if win_before is not None and win_after is not None:
        if win_before >= STILL_WINNING_BEFORE and win_after >= STILL_WINNING_AFTER:
            return "good"  # still totally winning
        if win_before <= ALREADY_LOST:
            return "good"  # already lost — the drop is noise
    if drop < INACCURACY:
        return "good"
    if drop < MISTAKE:
        return "inaccuracy"
    if drop < BLUNDER:
        return "mistake"
    return "blunder"


def non_pawn_material(fen: str) -> int:
    """Sum of non-pawn, non-king material for both sides (§8.7)."""
    board = chess.Board(fen)
    total = 0
    for piece in board.piece_map().values():
        if piece.piece_type not in (chess.PAWN, chess.KING):
            total += PIECE_VALUES[piece.piece_type]
    return total


def phase(
    fen: str,
    ply: int,
    theory_exit_ply: int | None,
    opening_max_ply: int,
    endgame_material: int,
) -> str:
    """Classify a ply's phase from `fen` (§8.7): opening|middlegame|endgame."""
    if non_pawn_material(fen) <= endgame_material:
        return "endgame"
    if ply <= opening_max_ply or (
        theory_exit_ply is not None and ply < theory_exit_ply
    ):
        return "opening"
    return "middlegame"


def low_clock(clock_before: float | None, base_seconds: int | None) -> int | None:
    """1 if the mover was in time trouble when moving, else 0 (§8.6).

    `None` for daily games (no base clock) or when the clock is unknown.
    """
    if clock_before is None or base_seconds is None:
        return None
    threshold = max(30.0, 0.10 * base_seconds)
    return 1 if clock_before < threshold else 0


def _count_after_ply20(
    user_moves: Iterable[tuple[int, float | None]], predicate
) -> int:
    return sum(
        1
        for ply, win_before in user_moves
        if ply > CONVERSION_MIN_PLY and win_before is not None and predicate(win_before)
    )


def failed_conversion(
    user_moves: Iterable[tuple[int, float | None]], result: str
) -> bool:
    """§8.8: ≥2 user moves with win_before ≥ 85 after ply 20 AND result ≠ win."""
    return _count_after_ply20(user_moves, lambda w: w >= CONVERSION_WIN) >= 2 and (
        result != "win"
    )


def saved_game(
    user_moves: Iterable[tuple[int, float | None]], result: str
) -> bool:
    """§8.8: ≥2 user moves with win_before ≤ 15 after ply 20 AND result ≠ loss."""
    return _count_after_ply20(user_moves, lambda w: w <= RESOURCEFUL_LOSS) >= 2 and (
        result != "loss"
    )
