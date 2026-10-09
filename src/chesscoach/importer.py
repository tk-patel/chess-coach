"""PGN import: turn a PGN file into `games` + `moves` rows.

Idempotent: the game uuid (§6) is a sha1 of the normalized headers + movetext,
so re-importing the same file skips games that already exist.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.pgn

from chesscoach.parse import parse_game


@dataclass
class ImportResult:
    imported: int = 0
    skipped_existing: int = 0
    skipped_no_user: int = 0
    errors: int = 0


_GAME_INSERT = """
    INSERT OR IGNORE INTO games (
        uuid, url, source, end_time, time_class, time_control,
        base_seconds, increment_seconds, rated, user_color, user_rating,
        opp_rating, opp_username, result, termination, eco, ply_count, pgn
    ) VALUES (?, ?, 'pgn', ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_MOVE_INSERT = """
    INSERT INTO moves (
        game_uuid, ply, color, is_user, san, uci, fen_before, clock_after, time_spent
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def compute_uuid(game: chess.pgn.Game) -> str:
    """sha1 of normalized headers + movetext (the §6 PGN-import uuid)."""
    headers = "\n".join(f"{key}:{game.headers[key]}" for key in sorted(game.headers))
    movetext = []
    node = game
    while node.variations:
        node = node.variation(0)
        movetext.append(node.move.uci())
    canonical = headers + "\n" + " ".join(movetext)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def import_pgn_file(
    conn: sqlite3.Connection, path: str | Path, username: str
) -> ImportResult:
    """Import every game in `path` where `username` plays a side."""
    result = ImportResult()

    with open(path) as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break

            pgn_text = str(game)
            parsed = parse_game(pgn_text, username)

            if parsed.user_color is None:
                result.skipped_no_user += 1
                continue

            uuid = compute_uuid(game)
            cursor = conn.execute(
                _GAME_INSERT,
                (
                    uuid,
                    None,
                    parsed.end_time,
                    parsed.time_class,
                    parsed.time_control,
                    parsed.base_seconds,
                    parsed.increment_seconds,
                    parsed.user_color,
                    parsed.user_rating,
                    parsed.opp_rating,
                    parsed.opp_username,
                    parsed.result,
                    parsed.termination,
                    parsed.eco,
                    parsed.ply_count,
                    pgn_text,
                ),
            )
            if cursor.rowcount == 0:
                result.skipped_existing += 1
                continue

            for move in parsed.moves:
                conn.execute(
                    _MOVE_INSERT,
                    (
                        uuid,
                        move.ply,
                        move.color,
                        int(move.is_user),
                        move.san,
                        move.uci,
                        move.fen_before,
                        move.clock_after,
                        move.time_spent,
                    ),
                )
            result.imported += 1

    conn.commit()
    return result
