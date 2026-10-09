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
import multiprocessing
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import chess

from chesscoach.classify import (
    INACCURACY,
    classify_move,
    game_accuracy,
    low_clock,
    move_accuracy,
    phase,
    win_drop,
    win_percentage,
)
from chesscoach.config import Config
from chesscoach.engine import Engine
from chesscoach.parse import ParsedGame, parse_game


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


# --- Batch orchestration (§9, T3.3) ----------------------------------------

_MOVE_COLUMNS = [
    "ply", "color", "is_user", "san", "uci", "fen_before", "clock_after",
    "time_spent", "cp_before", "mate_before", "cp_after", "mate_after",
    "win_before", "win_after", "win_drop", "move_accuracy", "best_uci",
    "best_san", "pv_uci", "multipv_json", "classification", "phase",
    "low_clock", "motifs_json",
]


@dataclass
class BatchResult:
    analyzed: int = 0
    errors: int = 0
    skipped: int = 0
    seconds: float = 0.0
    engine_id: str | None = None


def _coerce(value):
    return int(value) if isinstance(value, bool) else value


def _write_moves(conn: sqlite3.Connection, uuid: str, move_dicts: list[dict]) -> None:
    """Replace a game's move rows with freshly analyzed ones."""
    conn.execute("DELETE FROM moves WHERE game_uuid = ?", (uuid,))
    columns = ", ".join(["game_uuid", *_MOVE_COLUMNS])
    placeholders = ", ".join(["?"] * (len(_MOVE_COLUMNS) + 1))
    sql = f"INSERT INTO moves ({columns}) VALUES ({placeholders})"
    for move in move_dicts:
        conn.execute(sql, [uuid, *(_coerce(move.get(col)) for col in _MOVE_COLUMNS)])


def _worker(spec: dict) -> tuple:
    """Analyze one game in a worker process. Returns (uuid, status, rows, engine_id, error)."""
    try:
        parsed = parse_game(spec["pgn"], spec["username"])
        with Engine.from_config(spec["config"]) as engine:
            analysis = analyze_game(
                parsed, engine, spec["config"], spec["theory_exit_ply"]
            )
        rows = [asdict(move) for move in analysis.moves]
        return (spec["uuid"], "done", rows, analysis.engine_id, None)
    except Exception as exc:  # noqa: BLE001 - per-game isolation is the point
        return (spec["uuid"], "error", None, None, f"{type(exc).__name__}: {exc}")


def _multiprocessing_executor(config: Config):
    workers = max(1, config.engine.workers)

    def run(specs):
        ctx = multiprocessing.get_context()
        with ctx.Pool(workers) as pool:
            yield from pool.imap_unordered(_worker, specs)

    return run


def _since_timestamp(since: str) -> int:
    return int(datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())


def _side_accuracy(rows: list[dict], theory_exit_ply: int | None) -> float | None:
    """Mean move accuracy for one side, excluding plies ≤ theory_exit_ply (§8.4)."""
    values = [
        row["move_accuracy"]
        for row in rows
        if row.get("move_accuracy") is not None
        and (theory_exit_ply is None or row["ply"] > theory_exit_ply)
    ]
    return game_accuracy(values) if values else None


def game_totals(
    move_dicts: list[dict], theory_exit_ply: int | None
) -> dict:
    """Game-level aggregates (§6 `games` columns) from analyzed move dicts."""
    user_moves = [row for row in move_dicts if row["is_user"]]
    opp_moves = [row for row in move_dicts if not row["is_user"]]
    user_wins = [
        row["win_before"] for row in user_moves if row.get("win_before") is not None
    ]
    return {
        "user_accuracy": _side_accuracy(user_moves, theory_exit_ply),
        "opp_accuracy": _side_accuracy(opp_moves, theory_exit_ply),
        "max_user_winpct": max(user_wins) if user_wins else None,
        "min_user_winpct": min(user_wins) if user_wins else None,
    }


def _reset_status(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE games SET analysis_status = 'pending', analysis_error = NULL"
    )
    conn.commit()


def _mark_short_games_skipped(conn: sqlite3.Connection, min_plies: int) -> int:
    cursor = conn.execute(
        "UPDATE games SET analysis_status = 'skipped'"
        " WHERE ply_count < ? AND analysis_status IN ('pending', 'pass1')",
        (min_plies,),
    )
    conn.commit()
    return cursor.rowcount


def _select_specs(
    conn: sqlite3.Connection, config: Config, limit: int | None, since: str | None
) -> list[dict]:
    query = (
        "SELECT uuid, pgn, user_color, theory_exit_ply FROM games"
        " WHERE analysis_status IN ('pending', 'pass1')"
    )
    params: list = []
    if since is not None:
        query += " AND end_time >= ?"
        params.append(_since_timestamp(since))
    query += " ORDER BY end_time"
    if limit is not None:
        query += " LIMIT ?"
        params.append(int(limit))

    specs = []
    for row in conn.execute(query, params):
        specs.append(
            {
                "uuid": row["uuid"],
                "pgn": row["pgn"],
                "user_color": row["user_color"],
                "theory_exit_ply": row["theory_exit_ply"],
                "username": config.username,
                "config": config,
            }
        )
    return specs


def run_batch(
    conn: sqlite3.Connection,
    config: Config,
    *,
    book=None,
    limit: int | None = None,
    since: str | None = None,
    reanalyze: bool = False,
    executor=None,
    progress=None,
) -> BatchResult:
    """Analyze pending games with a worker pool, committing after each game.

    The unit of work is one game; the parent process alone writes to SQLite.
    `executor` (for tests) is a callable: `specs -> iterable of worker tuples`.
    """
    from chesscoach.openings import backfill_openings

    started = time.monotonic()
    result = BatchResult()

    if reanalyze:
        _reset_status(conn)

    if book is not None and bool(book):
        backfill_openings(conn, book)

    result.skipped = _mark_short_games_skipped(conn, config.analysis.min_plies)

    specs = _select_specs(conn, config, limit, since)
    if not specs:
        result.seconds = time.monotonic() - started
        return result

    # Mark everything in flight as pass1 so a crash leaves it resumable.
    conn.executemany(
        "UPDATE games SET analysis_status = 'pass1' WHERE uuid = ?",
        [(spec["uuid"],) for spec in specs],
    )
    conn.commit()

    run = executor if executor is not None else _multiprocessing_executor(config)
    total = len(specs)
    spec_by_uuid = {spec["uuid"]: spec for spec in specs}
    for done, item in enumerate(run(specs), start=1):
        uuid, status, rows, engine_id, error = item
        if status == "done":
            _write_moves(conn, uuid, rows)
            totals = game_totals(rows, spec_by_uuid[uuid]["theory_exit_ply"])
            conn.execute(
                "UPDATE games SET analysis_status = 'done', analysis_error = NULL,"
                " engine_id = ?, pass1_depth = ?, pass2_depth = ?,"
                " user_accuracy = ?, opp_accuracy = ?,"
                " max_user_winpct = ?, min_user_winpct = ? WHERE uuid = ?",
                (
                    engine_id,
                    config.engine.pass1_depth,
                    config.engine.pass2_depth,
                    totals["user_accuracy"],
                    totals["opp_accuracy"],
                    totals["max_user_winpct"],
                    totals["min_user_winpct"],
                    uuid,
                ),
            )
            result.analyzed += 1
            result.engine_id = engine_id
        else:
            conn.execute(
                "UPDATE games SET analysis_status = 'error', analysis_error = ?"
                " WHERE uuid = ?",
                (error, uuid),
            )
            result.errors += 1
        conn.commit()
        if progress is not None:
            progress(f"[{done}/{total}] {uuid} {status}")

    result.seconds = time.monotonic() - started
    return result
