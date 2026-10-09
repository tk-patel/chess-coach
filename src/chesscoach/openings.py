"""Openings database (§7.2): lichess TSVs -> EPD -> (eco, name).

The lichess `chess-openings` repo (CC0) ships five TSVs (`a.tsv`..`e.tsv`) with
columns `eco`, `name`, `pgn`. We replay every line and map each position's EPD
(the first four FEN fields) to the *longest* line that reaches it, so a
transposition resolves to the more specific opening.

When the TSVs are absent the annotation step (T2.2) falls back to the PGN `ECO`
header and the `ECOUrl` slug via `eco_name_from_headers`.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.pgn

OPENING_FILES = ("a", "b", "c", "d", "e")
OPENINGS_URL = (
    "https://raw.githubusercontent.com/lichess-org/chess-openings/master/{letter}.tsv"
)


class OpeningsError(Exception):
    """Raised when the openings TSVs cannot be downloaded."""


def epd_of(fen: str) -> str:
    """Return the EPD key: the first four whitespace-separated FEN fields."""
    return " ".join(fen.split()[:4])


def opening_family(name: str) -> str:
    """The part of an opening name before the first colon (PLAN.md §7.2)."""
    return name.split(":", 1)[0].strip()


def load_openings(tsv_paths: Iterable[str | Path]) -> dict[str, tuple[str, str]]:
    """Build an EPD -> (eco, name) dict from lichess TSV files.

    Each position after a move is recorded; if several lines reach the same
    EPD, the longest (deepest) line wins.
    """
    # epd -> (depth, eco, name)
    book: dict[str, tuple[int, str, str]] = {}

    for path in tsv_paths:
        text = Path(path).read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.strip() or line.startswith("eco\t"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            eco, name, pgn = parts[0].strip(), parts[1].strip(), parts[2].strip()
            game = chess.pgn.read_game(io.StringIO(pgn))
            if game is None:
                continue
            board = game.board()
            node = game
            depth = 0
            while node.variations:
                node = node.variation(0)
                board.push(node.move)
                depth += 1
                key = epd_of(board.fen())
                existing = book.get(key)
                if existing is None or depth > existing[0]:
                    book[key] = (depth, eco, name)

    return {key: (eco, name) for key, (_, eco, name) in book.items()}


class OpeningBook:
    """A loaded openings dict with a small lookup surface."""

    def __init__(self, entries: Mapping[str, tuple[str, str]] | None = None):
        self.entries: dict[str, tuple[str, str]] = dict(entries or {})

    @classmethod
    def from_dir(cls, directory: str | Path) -> OpeningBook:
        """Load every `*.tsv` under `directory` (empty book if none)."""
        paths = sorted(Path(directory).glob("*.tsv"))
        return cls(load_openings(paths))

    def name_for_epd(self, epd: str) -> tuple[str, str] | None:
        """Return (eco, name) for an EPD, or None if out of book."""
        return self.entries.get(epd)

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)


def eco_name_from_headers(headers: Mapping[str, str]) -> tuple[str | None, str | None]:
    """Fallback when no TSVs are present: (ECO header, name from ECOUrl slug).

    The `ECOUrl` slug is expanded by replacing hyphens with spaces (best effort;
    the slug does not preserve the colon in variation names — see Decision D4).
    """
    eco = headers.get("ECO")
    eco_url = headers.get("ECOUrl") or ""
    name = None
    if eco_url:
        slug = eco_url.rstrip("/").split("/")[-1]
        if slug:
            name = slug.replace("-", " ").strip()
    return (eco or None), name


def download_openings(
    dest_dir: str | Path, transport, base_url: str = OPENINGS_URL
) -> list[Path]:
    """Download the five lichess TSVs into `dest_dir`.

    `transport` is a `chesscoach.fetch.Transport`. Raises `OpeningsError` with
    manual-download instructions if any file cannot be fetched.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for letter in OPENING_FILES:
        url = base_url.format(letter=letter)
        resp = transport.get(url, {})
        if resp.status_code != 200 or not resp.text.strip():
            raise OpeningsError(_manual_instructions(dest))
        target = dest / f"{letter}.tsv"
        target.write_text(resp.text, encoding="utf-8")
        written.append(target)

    return written


def _manual_instructions(dest: Path) -> str:
    urls = "\n".join(
        f"  {OPENINGS_URL.format(letter=letter)}" for letter in OPENING_FILES
    )
    return (
        "could not download the lichess openings TSVs (network blocked?).\n"
        f"Download these five files into {dest}:\n{urls}"
    )


@dataclass
class OpeningAnnotation:
    """Result of annotating one game's opening (§8.9)."""

    eco: str | None
    name: str | None
    family: str | None
    theory_exit_ply: int | None


def annotate_pgn(pgn_text: str, book: OpeningBook | None = None) -> OpeningAnnotation:
    """Replay a game and annotate its opening, per PLAN.md §8.9.

    `theory_exit_ply` is the first ply whose resulting position is *not* in the
    openings book (`1` when even the first move is out of book, `None` when the
    whole game stays in book). The name is that of the last in-book position;
    when nothing is in book we fall back to the PGN `ECO`/`ECOUrl` headers.
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return OpeningAnnotation(None, None, None, None)

    headers = game.headers
    board = game.board()
    node = game
    ply = 0
    last_eco: str | None = None
    last_name: str | None = None
    exit_ply: int | None = None

    while node.variations:
        node = node.variation(0)
        board.push(node.move)
        ply += 1
        hit = book.name_for_epd(epd_of(board.fen())) if book else None
        if hit is not None:
            last_eco, last_name = hit
        else:
            exit_ply = ply
            break

    if last_name is None:
        # Out of book from the first move (or no book at all): header fallback.
        eco, name = eco_name_from_headers(headers)
        if name is None:
            return OpeningAnnotation(eco, None, None, 1 if ply >= 1 else None)
        return OpeningAnnotation(eco, name, opening_family(name), 1)

    return OpeningAnnotation(last_eco, last_name, opening_family(last_name), exit_ply)


def backfill_openings(conn, book: OpeningBook) -> int:
    """Recompute opening columns for every game in the DB; returns rows updated."""
    rows = conn.execute("SELECT uuid, pgn FROM games").fetchall()
    updated = 0
    for row in rows:
        ann = annotate_pgn(row["pgn"], book)
        conn.execute(
            "UPDATE games SET eco = ?, opening_name = ?, opening_family = ?,"
            " theory_exit_ply = ? WHERE uuid = ?",
            (ann.eco, ann.name, ann.family, ann.theory_exit_ply, row["uuid"]),
        )
        updated += 1
    conn.commit()
    return updated
