"""chess.com Published-Data API client (§7.1).

Fetches a player's monthly archives incrementally. All HTTP goes through a
`Transport`, so tests inject a fake and never touch the network. Requests are
strictly serial; 429s are retried with backoff; ETag/Last-Modified enable 304
short-circuits; raw month responses are saved before parsing.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from chesscoach.config import Config
from chesscoach.openings import OpeningBook, annotate_pgn
from chesscoach.parse import (
    detect_user_color,
    parse_game,
    parse_time_control,
    result_code_to_result,
)

API_BASE = "https://api.chess.com"


class FetchError(Exception):
    """Raised when the archive list cannot be fetched."""


@dataclass
class Response:
    status_code: int
    headers: dict[str, str]
    json_data: dict | None
    text: str


class Transport:
    """Minimal HTTP interface; tests inject a fake."""

    def get(self, url: str, headers: dict[str, str]) -> Response:
        raise NotImplementedError


class RequestsTransport(Transport):
    """Real transport backed by `requests`."""

    def __init__(self, user_agent: str):
        self.user_agent = user_agent

    def get(self, url: str, headers: dict[str, str]) -> Response:
        import requests

        merged = {"User-Agent": self.user_agent, **headers}
        resp = requests.get(url, headers=merged, timeout=30)
        try:
            data = resp.json()
        except ValueError:
            data = None
        return Response(resp.status_code, dict(resp.headers), data, resp.text)


@dataclass
class FetchResult:
    inserted: int = 0
    filtered: int = 0
    skipped_months: int = 0
    errors: int = 0


_GAME_INSERT = """
    INSERT OR IGNORE INTO games (
        uuid, url, source, end_time, time_class, time_control,
        base_seconds, increment_seconds, rated, user_color, user_rating,
        opp_rating, opp_username, result, termination, eco, ply_count, pgn,
        opening_name, opening_family, theory_exit_ply
    ) VALUES (?, ?, 'api', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_MOVE_INSERT = """
    INSERT INTO moves (
        game_uuid, ply, color, is_user, san, uci, fen_before, clock_after, time_spent
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_RETRY_DELAYS = (1, 2, 4, 8)


def month_from_url(url: str) -> str:
    """'.../games/2026/09' -> '2026-09'."""
    parts = url.rstrip("/").split("/")
    return f"{parts[-2]}-{parts[-1]}"


def fetch_archive_list(transport: Transport, username: str) -> list[str]:
    url = f"{API_BASE}/pub/player/{username.lower()}/games/archives"
    resp = transport.get(url, {})
    if resp.status_code != 200 or not resp.json_data:
        raise FetchError(f"archive list for '{username}' returned HTTP {resp.status_code}")
    return list(resp.json_data.get("archives", []))


def _get_with_retry(transport: Transport, url: str, headers: dict[str, str]) -> Response:
    """GET with exponential backoff on 429 (max 5 tries)."""
    for attempt in range(5):
        resp = transport.get(url, headers)
        if resp.status_code != 429 or attempt == 4:
            return resp
        time.sleep(_RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)])
    raise FetchError("too many 429s")  # pragma: no cover - unreachable


def _insert_month(
    conn: sqlite3.Connection,
    games: list[dict],
    config: Config,
    book: OpeningBook | None = None,
) -> tuple[int, int]:
    """Insert a month's games, applying the §7.1 filters. Returns (inserted, filtered)."""
    inserted = 0
    filtered = 0

    for g in games:
        if g.get("rules") != config.fetch.rules:
            filtered += 1
            continue
        if g.get("time_class") not in config.fetch.time_classes:
            filtered += 1
            continue
        if config.fetch.rated_only and not g.get("rated"):
            filtered += 1
            continue

        white = g.get("white") or {}
        black = g.get("black") or {}
        user_color = detect_user_color(
            white.get("username") or "", black.get("username") or "", config.username
        )
        if user_color is None:
            filtered += 1
            continue

        white_result = white.get("result")
        black_result = black.get("result")
        user_code = white_result if user_color == "white" else black_result
        if user_code is None:
            filtered += 1
            continue
        result = result_code_to_result(user_code)
        if white_result == "win":
            termination = black_result
        elif black_result == "win":
            termination = white_result
        else:
            termination = white_result  # a draw code

        pgn_text = g.get("pgn") or ""
        parsed = parse_game(pgn_text, config.username)
        ann = annotate_pgn(pgn_text, book)
        base, inc = parse_time_control(g.get("time_control") or "")

        user_rating = white.get("rating") if user_color == "white" else black.get("rating")
        opp_rating = black.get("rating") if user_color == "white" else white.get("rating")
        opp_username = black.get("username") if user_color == "white" else white.get("username")

        rated = 1 if g.get("rated") else 0
        cursor = conn.execute(
            _GAME_INSERT,
            (
                g.get("uuid"),
                g.get("url"),
                g.get("end_time"),
                g.get("time_class"),
                g.get("time_control"),
                base,
                inc,
                rated,
                user_color,
                user_rating,
                opp_rating,
                opp_username or None,
                result,
                termination,
                ann.eco if ann.eco is not None else parsed.eco,
                parsed.ply_count,
                pgn_text,
                ann.name,
                ann.family,
                ann.theory_exit_ply,
            ),
        )
        if cursor.rowcount == 0:
            continue  # already imported

        for move in parsed.moves:
            conn.execute(
                _MOVE_INSERT,
                (
                    g.get("uuid"),
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
        inserted += 1

    return inserted, filtered


def fetch_all(
    conn: sqlite3.Connection,
    config: Config,
    transport: Transport,
    raw_dir: str | Path,
    book: OpeningBook | None = None,
) -> FetchResult:
    """Fetch every archive month incrementally, saving raw JSON to `raw_dir`."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    archives = fetch_archive_list(transport, config.username)
    if not archives:
        return FetchResult()

    result = FetchResult()
    current_url = archives[-1]

    for url in archives:
        month = month_from_url(url)
        stored = conn.execute(
            "SELECT etag, last_modified FROM archives WHERE url = ?", (url,)
        ).fetchone()

        if stored is not None and url != current_url:
            result.skipped_months += 1
            continue

        headers: dict[str, str] = {}
        if stored and stored["etag"]:
            headers["If-None-Match"] = stored["etag"]
        if stored and stored["last_modified"]:
            headers["If-Modified-Since"] = stored["last_modified"]

        resp = _get_with_retry(transport, url, headers)

        if resp.status_code == 304:
            continue
        if resp.status_code != 200 or resp.json_data is None:
            result.errors += 1
            continue

        (raw_dir / f"{month}.json").write_text(json.dumps(resp.json_data), encoding="utf-8")

        games = resp.json_data.get("games", [])
        inserted, filtered = _insert_month(conn, games, config, book)
        result.inserted += inserted
        result.filtered += filtered

        conn.execute(
            "INSERT OR REPLACE INTO archives (url, fetched_at, etag, last_modified, game_count)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                url,
                int(time.time()),
                resp.headers.get("ETag"),
                resp.headers.get("Last-Modified"),
                len(games),
            ),
        )
        conn.commit()

    return result
