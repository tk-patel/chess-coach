"""Pure PGN parsing: PGN text + metadata -> game and move records.

No I/O beyond reading the PGN string, no DB writes, no engine. The functions
here implement the time-control, result, clock, and user-color rules from
PLAN.md §7.1 and §8.6.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import UTC, datetime

import chess
import chess.pgn

# Result codes that map to a draw (§7.1).
DRAW_CODES = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


class ParseError(Exception):
    """Raised when PGN text cannot be parsed."""


@dataclass
class ParsedMove:
    ply: int                 # 1-based; ply 1 = white's first move
    color: str               # mover: 'white' | 'black'
    is_user: bool
    san: str
    uci: str
    fen_before: str
    clock_after: float | None   # seconds left for the mover, or None
    time_spent: float | None    # seconds, or None (daily / no clock)


@dataclass
class ParsedGame:
    pgn: str
    end_time: int | None
    time_class: str
    time_control: str
    base_seconds: int | None
    increment_seconds: int | None
    user_color: str | None     # 'white' | 'black' | None (username not in game)
    user_rating: int | None
    opp_rating: int | None
    opp_username: str | None
    result: str | None         # 'win' | 'draw' | 'loss' from the user's POV
    termination: str | None
    eco: str | None
    ply_count: int
    moves: list[ParsedMove] = field(default_factory=list)


def parse_time_control(tc: str) -> tuple[int | None, int | None]:
    """Parse a chess.com time control into (base_seconds, increment_seconds).

    "600" -> (600, 0); "180+2" -> (180, 2); "1/259200" (daily) -> (None, None).
    """
    tc = tc.strip()
    if not tc:
        return None, None
    if "/" in tc:
        return None, None  # correspondence/daily
    base_str, _, inc_str = tc.partition("+")
    base = int(base_str)
    inc = int(inc_str) if inc_str else 0
    return base, inc


def time_class_from_control(base_seconds: int | None) -> str:
    """Infer the chess.com time class from the base clock (seconds)."""
    if base_seconds is None:
        return "daily"
    if base_seconds < 180:
        return "bullet"
    if base_seconds < 600:
        return "blitz"
    return "rapid"


def result_code_to_result(code: str) -> str:
    """Map a chess.com result code to 'win' | 'draw' | 'loss' (§7.1)."""
    if code == "win":
        return "win"
    if code in DRAW_CODES:
        return "draw"
    return "loss"


def user_result_from_pgn(pgn_result: str, user_color: str) -> str:
    """Map a PGN Result header to the user's result, given their color."""
    if pgn_result == "1/2-1/2":
        return "draw"
    if user_color == "white":
        return "win" if pgn_result == "1-0" else "loss"
    return "win" if pgn_result == "0-1" else "loss"


def detect_user_color(white: str, black: str, username: str) -> str | None:
    """Return 'white'/'black' if username matches a side (case-insensitive), else None."""
    target = username.casefold()
    if white.casefold() == target:
        return "white"
    if black.casefold() == target:
        return "black"
    return None


def parse_end_time(headers: chess.pgn.Headers) -> int | None:
    """Extract a unix timestamp from UTCDate/UTCTime or Date headers."""
    utc_date = headers.get("UTCDate")
    utc_time = headers.get("UTCTime")
    date_str = headers.get("Date")
    try:
        if utc_date:
            combined = f"{utc_date.replace('.', '-')} {utc_time or '00:00:00'}"
            return int(datetime.strptime(combined, "%Y-%m-%d %H:%M:%S")
                       .replace(tzinfo=UTC).timestamp())
        if date_str:
            return int(datetime.strptime(date_str, "%Y.%m.%d")
                       .replace(tzinfo=UTC).timestamp())
    except ValueError:
        pass
    return None


def _int_header(headers: chess.pgn.Headers, key: str) -> int | None:
    value = headers.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_game(pgn_text: str, username: str) -> ParsedGame:
    """Parse one PGN game into a `ParsedGame`.

    Raises `ParseError` if the PGN is unreadable. A `user_color` of None means
    the username is not a player in this game (caller decides whether to skip).
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ParseError("could not parse PGN")

    headers = game.headers
    white = headers.get("White", "")
    black = headers.get("Black", "")

    user_color = detect_user_color(white, black, username)

    time_control = headers.get("TimeControl", "")
    base_seconds, increment_seconds = parse_time_control(time_control)

    if user_color == "white":
        user_rating = _int_header(headers, "WhiteElo")
        opp_rating = _int_header(headers, "BlackElo")
        opp_username = black or None
    elif user_color == "black":
        user_rating = _int_header(headers, "BlackElo")
        opp_rating = _int_header(headers, "WhiteElo")
        opp_username = white or None
    else:
        user_rating = None
        opp_rating = None
        opp_username = None

    pgn_result = headers.get("Result", "*")
    result = user_result_from_pgn(pgn_result, user_color) if user_color else None

    moves: list[ParsedMove] = []
    board = game.board()
    node = game
    prev_clock = {"white": base_seconds, "black": base_seconds}
    ply = 0

    while node.variations:
        node = node.variation(0)
        move = node.move
        ply += 1
        fen_before = board.fen()
        color = "white" if board.turn == chess.WHITE else "black"
        clock_after = node.clock()

        clock_before = prev_clock[color]
        if clock_before is not None and clock_after is not None:
            time_spent = max(0.0, clock_before - clock_after + (increment_seconds or 0))
        else:
            time_spent = None

        moves.append(
            ParsedMove(
                ply=ply,
                color=color,
                is_user=(color == user_color),
                san=board.san(move),
                uci=move.uci(),
                fen_before=fen_before,
                clock_after=clock_after,
                time_spent=time_spent,
            )
        )
        board.push(move)
        prev_clock[color] = clock_after

    return ParsedGame(
        pgn=pgn_text,
        end_time=parse_end_time(headers),
        time_class=time_class_from_control(base_seconds),
        time_control=time_control,
        base_seconds=base_seconds,
        increment_seconds=increment_seconds,
        user_color=user_color,
        user_rating=user_rating,
        opp_rating=opp_rating,
        opp_username=opp_username,
        result=result,
        termination=headers.get("Termination"),
        eco=headers.get("ECO"),
        ply_count=ply,
        moves=moves,
    )
