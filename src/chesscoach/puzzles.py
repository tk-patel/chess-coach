"""Puzzle selection and export — PLAN.md §11.

Reads the analyzed `moves` table (user moves only, after pass 2) and produces
the puzzle records that drive the trainer. Selection rules:

1. user `win_drop` ≥ `puzzles.min_drop`;
2. `multipv_json` exists and its best line's win% ≥ `puzzles.min_best_winpct`;
3. accepted moves = every multipv entry within `accept_within` of the best;
4. `multi_answer` when >1 accepted and best − 2nd-best < `uniqueness_gap`;
5. the played move must NOT be an accepted move;
6. dedupe on (4-field EPD + solution); keep the most recent, count `seen_count`.

The exported JSON is sorted by `end_time` desc.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import chess

from chesscoach.config import Config
from chesscoach.openings import epd_of

LINE_MAX_PLIES = 6


def _puzzle_id(fen: str, solution_uci: str) -> str:
    key = f"{epd_of(fen)}|{solution_uci}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _line_san(fen: str, pv_uci: list[str], max_plies: int = LINE_MAX_PLIES) -> str:
    board = chess.Board(fen)
    sans: list[str] = []
    for uci in pv_uci[:max_plies]:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            break
        sans.append(board.san(move))
        board.push(move)
    return " ".join(sans)


def _date(end_time: int | None) -> str | None:
    if end_time is None:
        return None
    return datetime.fromtimestamp(end_time, tz=UTC).strftime("%Y-%m-%d")


def _played_san(san: str, classification: str | None) -> str:
    if classification == "blunder":
        return f"{san}??"
    if classification == "mistake":
        return f"{san}?"
    return san


def select_puzzles(conn: sqlite3.Connection, config: Config) -> list[dict]:
    """Build the deduped, sorted puzzle list from the DB (§11)."""
    rows = conn.execute(
        """
        SELECT m.game_uuid, m.ply, m.san, m.uci, m.fen_before, m.pv_uci,
               m.win_drop, m.multipv_json, m.motifs_json, m.phase, m.low_clock,
               m.classification,
               g.user_color, g.opening_name, g.url, g.end_time
        FROM moves m JOIN games g ON g.uuid = m.game_uuid
        WHERE m.is_user = 1
        ORDER BY g.end_time
        """
    ).fetchall()

    puzzles: dict[tuple[str, str], dict] = {}

    for row in rows:
        if row["win_drop"] is None or row["win_drop"] < config.puzzles.min_drop:
            continue
        if not row["multipv_json"]:
            continue

        entries = json.loads(row["multipv_json"])
        if not entries:
            continue
        entries.sort(key=lambda entry: entry["win"], reverse=True)
        best = entries[0]
        if best["win"] < config.puzzles.min_best_winpct:
            continue

        accepted = [
            entry
            for entry in entries
            if entry["win"] >= best["win"] - config.puzzles.accept_within
        ]
        accepted_uci = [entry["uci"] for entry in accepted]
        if row["uci"] in accepted_uci:  # the played move must not be acceptable
            continue

        multi_answer = (
            len(accepted) > 1
            and len(entries) > 1
            and (entries[0]["win"] - entries[1]["win"]) < config.puzzles.uniqueness_gap
        )

        fen = row["fen_before"]
        solution_uci = best["uci"]
        pv_uci = str(row["pv_uci"] or "").split()
        motifs = json.loads(row["motifs_json"]) if row["motifs_json"] else []

        record = {
            "id": _puzzle_id(fen, solution_uci),
            "fen": fen,
            "orientation": row["user_color"],
            "played_san": _played_san(row["san"], row["classification"]),
            "accepted": accepted_uci,
            "solution_uci": solution_uci,
            "solution_san": best["san"],
            "line_san": _line_san(fen, pv_uci),
            "win_drop": round(row["win_drop"], 1),
            "motifs": motifs,
            "phase": row["phase"],
            "low_clock": bool(row["low_clock"]),
            "opening": row["opening_name"],
            "game_url": row["url"],
            "date": _date(row["end_time"]),
            "multi_answer": multi_answer,
            "seen_count": 1,
            "game_uuid": row["game_uuid"],
            "ply": row["ply"],
        }

        key = (epd_of(fen), solution_uci)
        existing = puzzles.get(key)
        if existing is None or (row["end_time"] or 0) >= (existing["_end_time"] or 0):
            seen = (existing["seen_count"] + 1) if existing else 1
            record["seen_count"] = seen
            record["_end_time"] = row["end_time"]
            puzzles[key] = record
        else:
            existing["seen_count"] += 1

    result = list(puzzles.values())
    result.sort(key=lambda record: record["date"] or "", reverse=True)
    return result


def export_puzzles(puzzles: list[dict], path: str | Path) -> Path:
    """Write the puzzle list to `path` as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(puzzles, indent=2) + "\n", encoding="utf-8")
    return path


_EXPORT_KEYS = [
    "id", "fen", "orientation", "played_san", "accepted", "solution_san",
    "line_san", "win_drop", "motifs", "phase", "low_clock", "opening",
    "game_url", "date", "multi_answer", "seen_count",
]


def store_puzzles(conn: sqlite3.Connection, puzzles: list[dict]) -> int:
    """Replace the `puzzles` table with `puzzles`; returns the row count."""
    conn.execute("DELETE FROM puzzles")
    for puzzle in puzzles:
        conn.execute(
            """
            INSERT INTO puzzles (
              id, game_uuid, ply, fen, played_san, solution_uci, solution_san,
              accepted_uci_json, line_san, win_drop, motifs_json, phase,
              low_clock, opening_name, game_url, end_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                puzzle["id"],
                puzzle["game_uuid"],
                puzzle["ply"],
                puzzle["fen"],
                puzzle["played_san"],
                puzzle["solution_uci"],
                puzzle["solution_san"],
                json.dumps(puzzle["accepted"]),
                puzzle["line_san"],
                puzzle["win_drop"],
                json.dumps(puzzle["motifs"]),
                puzzle["phase"],
                int(puzzle["low_clock"]),
                puzzle["opening"],
                puzzle["game_url"],
                puzzle.get("_end_time"),
            ),
        )
    conn.commit()
    return len(puzzles)


def strip_internal(record: dict) -> dict:
    """Return just the exported keys, in the documented order (§11)."""
    return {key: record[key] for key in _EXPORT_KEYS}


def rebuild(conn: sqlite3.Connection, config: Config, out_path: str | Path) -> int:
    """Select, store, and export puzzles. Returns the count."""
    puzzles = select_puzzles(conn, config)
    store_puzzles(conn, puzzles)
    export_puzzles([strip_internal(p) for p in puzzles], out_path)
    return len(puzzles)
