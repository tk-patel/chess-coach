"""Two-pass engine analysis for a single game (§9).

`analyze_game` is pure with respect to the DB: it takes a parsed game plus a
running `Engine` and returns `AnalyzedMove` rows. The batch/worker layer (T3.3)
owns DB writes.

Pass 1 evaluates every position (P0..PN) once at `pass1_depth`, multipv 1. Pass
2 re-analyzes each *user* move whose pass-1 win% drop reached `INACCURACY`
(§8.5) at `pass2_depth`, multipv `pass2_multipv`, and overwrites that ply's
values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import chess

from chesscoach.classify import (
    INACCURACY,
    classify_move,
    low_clock,
    move_accuracy,
    phase,
    win_drop,
    win_percentage,
)
from chesscoach.config import Config
from chesscoach.engine import Engine
from chesscoach.parse import ParsedGame


@dataclass
class AnalyzedMove:
    """One ply's full analysis row (§6 `moves` columns, minus motifs).

    Motifs are added later by T5.2.
    """

    ply: int
    color: str
    is_user: bool
    san: str
    uci: str
    fen_before: str
    clock_after: float | None
    time_spent: float | None
    cp_before: int | None
    mate_before: int | None
    cp_after: int | None
    mate_after: int | None
    win_before: float
    win_after: float
    win_drop: float
    move_accuracy: float
    best_uci: str | None
    best_san: str | None
    pv_uci: str | None
    multipv_json: str | None
    classification: str | None
    phase: str
    low_clock: int | None


@dataclass
class GameAnalysis:
    """The analyzed moves for one game plus engine provenance."""

    moves: list[AnalyzedMove]
    engine_id: str
    pass1_depth: int
    pass2_depth: int


def _colour(user_color: str) -> chess.Color:
    return chess.WHITE if user_color == "white" else chess.BLACK


def _terminal_eval(board: chess.Board, pov: chess.Color) -> dict:
    """Eval of a mate/stalemate position, from `pov` (§8.3)."""
    if board.is_checkmate():
        user_mates = board.turn != pov
        return {
            "cp": None,
            "mate": 1 if user_mates else -1,
            "win": 100.0 if user_mates else 0.0,
            "best_uci": None,
            "best_san": None,
            "pv_uci": None,
        }
    return {
        "cp": None,
        "mate": None,
        "win": 50.0,  # stalemate / no legal moves and not mate → draw
        "best_uci": None,
        "best_san": None,
        "pv_uci": None,
    }


def _line_eval(line) -> dict:
    return {
        "cp": line.cp,
        "mate": line.mate,
        "win": win_percentage(line.cp, line.mate),
        "best_uci": line.uci,
        "best_san": line.san,
        "pv_uci": " ".join(line.pv_uci),
    }


def _multipv_json(lines) -> str:
    entries = [
        {
            "uci": line.uci,
            "san": line.san,
            "cp": line.cp,
            "mate": line.mate,
            "win": win_percentage(line.cp, line.mate),
        }
        for line in lines
    ]
    return json.dumps(entries, sort_keys=True)


def analyze_game(
    parsed: ParsedGame,
    engine: Engine,
    config: Config,
    theory_exit_ply: int | None = None,
) -> GameAnalysis:
    """Run pass 1 and pass 2 over `parsed`, returning one row per ply.

    `theory_exit_ply` comes from the openings annotation (T2.2) and only affects
    the per-ply `phase`.
    """
    pov = _colour(parsed.user_color or "white")
    depths = config.engine
    limits = config.analysis

    # Replay the game, keeping every position P0..PN.
    boards: list[chess.Board] = [chess.Board()]
    for move in parsed.moves:
        boards.append(boards[-1].copy(stack=False))
        boards[-1].push_uci(move.uci)

    # --- Pass 1: evaluate every position once -------------------------------
    evals: list[dict] = []
    for board in boards:
        if not any(board.legal_moves):
            evals.append(_terminal_eval(board, pov))
        else:
            lines = engine.evaluate(board, depth=depths.pass1_depth, pov=pov)
            evals.append(_line_eval(lines[0]))

    # --- Assemble the per-ply rows ------------------------------------------
    prev_clock: dict[chess.Color, float | None] = {
        chess.WHITE: parsed.base_seconds,
        chess.BLACK: parsed.base_seconds,
    }
    rows: list[AnalyzedMove] = []

    for idx, move in enumerate(parsed.moves):
        before = evals[idx]
        after = evals[idx + 1]
        color = chess.WHITE if move.color == "white" else chess.BLACK
        clock_before = prev_clock[color]
        prev_clock[color] = move.clock_after

        drop = win_drop(before["win"], after["win"])
        is_best = before["best_uci"] is not None and move.uci == before["best_uci"]
        classification = (
            classify_move(drop, is_best, before["win"], after["win"])
            if move.is_user
            else None
        )

        rows.append(
            AnalyzedMove(
                ply=move.ply,
                color=move.color,
                is_user=move.is_user,
                san=move.san,
                uci=move.uci,
                fen_before=move.fen_before,
                clock_after=move.clock_after,
                time_spent=move.time_spent,
                cp_before=before["cp"],
                mate_before=before["mate"],
                cp_after=after["cp"],
                mate_after=after["mate"],
                win_before=before["win"],
                win_after=after["win"],
                win_drop=drop,
                move_accuracy=move_accuracy(drop),
                best_uci=before["best_uci"],
                best_san=before["best_san"],
                pv_uci=before["pv_uci"],
                multipv_json=None,
                classification=classification,
                phase=phase(
                    move.fen_before,
                    move.ply,
                    theory_exit_ply,
                    limits.opening_max_ply,
                    limits.endgame_material,
                ),
                low_clock=low_clock(clock_before, parsed.base_seconds),
            )
        )

    # --- Pass 2: deepen the user's candidate mistakes -----------------------
    for row, move in zip(rows, parsed.moves, strict=True):
        if not row.is_user or row.win_drop < INACCURACY:
            continue

        board_before = chess.Board(row.fen_before)
        lines = engine.evaluate(
            board_before, depth=depths.pass2_depth, multipv=depths.pass2_multipv, pov=pov
        )
        best = _line_eval(lines[0])

        board_after = chess.Board(row.fen_before)
        board_after.push_uci(move.uci)
        after_lines = engine.evaluate(board_after, depth=depths.pass2_depth, pov=pov)
        after = _line_eval(after_lines[0])

        drop = win_drop(best["win"], after["win"])
        is_best = move.uci == best["best_uci"]
        row.cp_before = best["cp"]
        row.mate_before = best["mate"]
        row.cp_after = after["cp"]
        row.mate_after = after["mate"]
        row.win_before = best["win"]
        row.win_after = after["win"]
        row.win_drop = drop
        row.move_accuracy = move_accuracy(drop)
        row.best_uci = best["best_uci"]
        row.best_san = best["best_san"]
        row.pv_uci = best["pv_uci"]
        row.multipv_json = _multipv_json(lines)
        row.classification = classify_move(drop, is_best, best["win"], after["win"])

    return GameAnalysis(
        moves=rows,
        engine_id=engine.id_name,
        pass1_depth=depths.pass1_depth,
        pass2_depth=depths.pass2_depth,
    )
