"""Heuristic tactic detectors — PLAN.md §10.

Pure functions: they take a position (user to move), the move the user played,
and the engine lines already computed by the two analysis passes, and return a
list of motif tags. They are *heuristics* (labelled as such in the UI), not
solver-verified.

Material values: P=1, N=3, B=3, R=5, Q=9, K=0. "Material swing along a line" =
user material minus opponent material after playing the first n plies of the
line, minus the same difference before.
"""

from __future__ import annotations

import chess

VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}
SWING_PLIES = 4
PROMOTION_PIECES = "qrbn"


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(
        VALUES[piece.piece_type]
        for piece in board.piece_map().values()
        if piece.color == color
    )


def _play_delta(
    board_before: chess.Board,
    moves: list[str],
    user_color: chess.Color,
    plies: int = SWING_PLIES,
) -> int:
    """User-minus-opponent material change after `plies` of `moves`."""
    board = board_before.copy()
    opp = not user_color
    before = _material(board, user_color) - _material(board, opp)
    for uci in moves[:plies]:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            break
        board.push(move)
    return (_material(board, user_color) - _material(board, opp)) - before


def _is_capture(board: chess.Board, uci: str) -> int:
    """Value of the piece captured by `uci` on `board` (en passant counts as 1)."""
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        return 0
    if board.is_en_passant(move):
        return VALUES[chess.PAWN]
    target = board.piece_at(move.to_square)
    return VALUES[target.piece_type] if target else 0


def _is_fork(board: chess.Board, move: chess.Move, mover: chess.Color) -> bool:
    """Does `move` create a fork of the enemy pieces worth more than the mover?"""
    if move not in board.legal_moves:
        return False
    after = board.copy()
    after.push(move)
    piece = after.piece_at(move.to_square)
    if piece is None:
        return False
    attacker = VALUES[piece.piece_type]
    higher = 0
    has_king = False
    big_piece = False
    for square in after.attacks(move.to_square):
        target = after.piece_at(square)
        if target is None or target.color == mover:
            continue
        if target.piece_type == chess.KING:
            has_king = True
        else:
            if VALUES[target.piece_type] > attacker:
                higher += 1
            if VALUES[target.piece_type] >= 3:
                big_piece = True
    return higher >= 2 or (has_king and big_piece)


def _pinned_big_pieces(board: chess.Board, color: chess.Color) -> set[int]:
    return {
        square
        for square, piece in board.piece_map().items()
        if piece.color == color
        and VALUES[piece.piece_type] >= 3
        and board.is_pinned(color, square)
    }


def _has_promotion(moves: list[str]) -> bool:
    return any(len(uci) >= 5 and uci[4] in PROMOTION_PIECES for uci in moves[:4])


def _back_rank_mate(
    board_before: chess.Board,
    played: chess.Move,
    reply_pv: list[str],
    user_color: chess.Color,
) -> bool:
    """allowed_mate by a rook/queen landing on the user's occupied back rank."""
    board = board_before.copy()
    board.push(played)
    last: chess.Move | None = None
    for uci in reply_pv:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            break
        board.push(move)
        last = move
    if last is None or not board.is_checkmate() or board.turn != user_color:
        return False
    piece = board.piece_at(last.to_square)
    if piece is None or piece.piece_type not in (chess.ROOK, chess.QUEEN):
        return False
    back_rank = 0 if user_color == chess.WHITE else 7
    if chess.square_rank(last.to_square) != back_rank:
        return False
    king_square = board.king(user_color)
    return king_square is not None and chess.square_rank(king_square) == back_rank


def detect_motifs(
    board_before: chess.Board,
    played_uci: str,
    best_pv: list[str] | None = None,
    reply_pv: list[str] | None = None,
    mate_before: int | None = None,
    mate_after: int | None = None,
    low_clock: bool = False,
) -> list[str]:
    """Return the heuristic motif tags for a user move (§10).

    `best_pv` is the engine's best line from `board_before`; `reply_pv` is the
    opponent's best line from the post-`played` position. Both are UCI lists.
    """
    best_pv = best_pv or []
    reply_pv = reply_pv or []
    user_color = board_before.turn
    opp = not user_color
    played = chess.Move.from_uci(played_uci)

    board_after = board_before.copy()
    if played in board_after.legal_moves:
        board_after.push(played)

    tags: set[str] = set()

    if mate_after is not None and mate_after < 0 and abs(mate_after) <= 5:
        tags.add("allowed_mate")
    if mate_before is not None and mate_before > 0 and not (
        mate_after is not None and mate_after > 0
    ):
        tags.add("missed_mate")

    if "allowed_mate" in tags and _back_rank_mate(
        board_before, played, reply_pv, user_color
    ):
        tags.add("back_rank")

    # Post-move line (opponent's reply and follow-up), from before the user's move.
    post_line = [played_uci, *reply_pv]
    post_delta = _play_delta(board_before, post_line, user_color)

    if reply_pv and post_delta <= -2:
        reply0 = chess.Move.from_uci(reply_pv[0])
        if _is_capture(board_after, reply_pv[0]):
            tags.add("hung_piece")
        if _is_fork(board_after, reply0, opp):
            tags.add("allowed_fork")
        pinned_after = _pinned_big_pieces(
            _advance(board_after, reply_pv[0]), user_color
        )
        if pinned_after - _pinned_big_pieces(board_before, user_color):
            tags.add("allowed_pin")

    if best_pv:
        best_delta = _play_delta(board_before, best_pv, user_color)
        best0 = chess.Move.from_uci(best_pv[0])
        if best_delta >= 2 and _is_fork(board_before, best0, user_color):
            tags.add("missed_fork")
        best_capture = _is_capture(board_before, best_pv[0])
        played_capture = _is_capture(board_before, played_uci)
        if best_capture > 0 and best_delta >= 2 and played_capture < best_capture:
            tags.add("missed_capture")

    if _has_promotion(best_pv) or _has_promotion(reply_pv):
        tags.add("promotion")

    if low_clock:
        tags.add("low_clock")

    if not (tags - {"low_clock"}):
        tags.add("positional")

    return sorted(tags)


def _advance(board: chess.Board, uci: str) -> chess.Board:
    """Return `board` with `uci` pushed (a copy); unchanged if illegal."""
    after = board.copy()
    move = chess.Move.from_uci(uci)
    if move in after.legal_moves:
        after.push(move)
    return after
