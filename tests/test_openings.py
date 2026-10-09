"""Openings database tests (T2.1) — real lichess TSV subset, no network."""

from pathlib import Path

import chess

from chesscoach.db import connect, migrate
from chesscoach.fetch import Response, Transport
from chesscoach.importer import import_pgn_file
from chesscoach.openings import (
    OpeningBook,
    OpeningsError,
    annotate_pgn,
    backfill_openings,
    download_openings,
    eco_name_from_headers,
    epd_of,
    load_openings,
    opening_family,
)

FIX = Path(__file__).resolve().parent / "fixtures"
SAMPLE = FIX / "openings_sample.tsv"


def _epd_after(moves_uci: str) -> str:
    board = chess.Board()
    for uci in moves_uci.split():
        board.push_uci(uci)
    return epd_of(board.fen())


def test_caro_kann_advance_resolves():
    book = load_openings([SAMPLE])
    # 1. e4 c6 2. d4 d5 3. e5
    epd = _epd_after("e2e4 c7c6 d2d4 d7d5 e4e5")
    assert book[epd] == ("B12", "Caro-Kann Defense: Advance Variation")


def test_longest_line_wins():
    book = load_openings([SAMPLE])
    # after 3...e5 the position is reached by two lines; the shallower one wins
    # because both reach it at the same depth and the first is kept.
    epd_advance = _epd_after("e2e4 c7c6 d2d4 d7d5 e4e5")
    # one move deeper (4. g4) belongs to the Bayonet Attack line.
    epd_bayonet = _epd_after("e2e4 c7c6 d2d4 d7d5 e4e5 c8f5 g2g4")
    assert book[epd_advance][1] == "Caro-Kann Defense: Advance Variation"
    assert book[epd_bayonet][1] == (
        "Caro-Kann Defense: Advance Variation, Bayonet Attack"
    )
    assert len(book) > 5


def test_sicilian_najdorf_english_attack_deeper_line():
    book = load_openings([SAMPLE])
    epd_najdorf = _epd_after(
        "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6"
    )
    assert book[epd_najdorf] == ("B90", "Sicilian Defense: Najdorf Variation")
    epd_english = _epd_after(
        "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6 c1e3"
    )
    assert book[epd_english] == (
        "B90",
        "Sicilian Defense: Najdorf Variation, English Attack",
    )


def test_out_of_book_returns_none():
    book = load_openings([SAMPLE])
    assert book.get(_epd_after("a2a3")) is None


def test_from_dir_reads_tsvs(tmp_path):
    (tmp_path / "b.tsv").write_text(SAMPLE.read_text())
    book = OpeningBook.from_dir(tmp_path)
    assert len(book) > 0
    assert bool(book)
    epd = _epd_after("e2e4 c7c6 d2d4 d7d5 e4e5")
    assert book.name_for_epd(epd) == ("B12", "Caro-Kann Defense: Advance Variation")


def test_empty_dir_is_empty_book(tmp_path):
    book = OpeningBook.from_dir(tmp_path)
    assert len(book) == 0
    assert not book


def test_opening_family():
    assert opening_family("Caro-Kann Defense: Advance Variation") == "Caro-Kann Defense"
    assert opening_family("Italian Game") == "Italian Game"


def test_header_fallback():
    eco, name = eco_name_from_headers(
        {
            "ECO": "B12",
            "ECOUrl": "https://www.chess.com/openings/Caro-Kann-Defense-Advance-Variation",
        }
    )
    assert eco == "B12"
    assert name == "Caro Kann Defense Advance Variation"


def test_header_fallback_missing():
    assert eco_name_from_headers({}) == (None, None)


class _FakeTransport(Transport):
    def __init__(self, status: int = 200, text: str = "x\ty\tz\n"):
        self.status = status
        self.text = text
        self.calls: list[str] = []

    def get(self, url: str, headers: dict) -> Response:
        self.calls.append(url)
        return Response(self.status, {}, None, self.text)


def test_download_openings_writes_files(tmp_path):
    transport = _FakeTransport(text="eco\tname\tpgn\nB00\tX\t1. e4\n")
    written = download_openings(tmp_path, transport, base_url="http://x/{letter}.tsv")
    assert len(written) == 5
    assert sorted(p.name for p in written) == ["a.tsv", "b.tsv", "c.tsv", "d.tsv", "e.tsv"]
    assert len(transport.calls) == 5


def test_download_openings_error_has_instructions(tmp_path):
    transport = _FakeTransport(status=404)
    try:
        download_openings(tmp_path, transport)
        raise AssertionError("expected OpeningsError")
    except OpeningsError as exc:
        assert str(tmp_path) in str(exc)
        assert "a.tsv" in str(exc) or "raw.githubusercontent" in str(exc)


# --- T2.2 annotation -------------------------------------------------------


def _pgn(moves: str, result: str = "*", **headers: str) -> str:
    base = {"Event": "Test", "White": "A", "Black": "B", "Result": result}
    base.update(headers)
    tag = "\n".join(f'[{k} "{v}"]' for k, v in base.items())
    return f"{tag}\n\n{moves} {result}\n"


def test_annotate_theory_exit_on_deviation():
    book = OpeningBook(load_openings([SAMPLE]))
    pgn = _pgn("1. e4 c6 2. d4 d5 3. e5 e6")
    ann = annotate_pgn(pgn, book)
    assert ann.theory_exit_ply == 6  # 3...e6 leaves the known Caro-Kann lines
    assert ann.name == "Caro-Kann Defense: Advance Variation"
    assert ann.family == "Caro-Kann Defense"
    assert ann.eco == "B12"


def test_annotate_whole_game_in_book_has_null_exit():
    book = OpeningBook(load_openings([SAMPLE]))
    ann = annotate_pgn(_pgn("1. e4 c6 2. d4 d5 3. e5"), book)
    assert ann.theory_exit_ply is None
    assert ann.name == "Caro-Kann Defense: Advance Variation"


def test_annotate_out_of_book_ply1_uses_header_fallback():
    book = OpeningBook(load_openings([SAMPLE]))
    pgn = _pgn(
        "1. a3 e5",
        ECO="A00",
        ECOUrl="https://www.chess.com/openings/Amar-Opening",
    )
    ann = annotate_pgn(pgn, book)
    assert ann.theory_exit_ply == 1
    assert ann.eco == "A00"
    assert ann.name == "Amar Opening"
    assert ann.family == "Amar Opening"


def test_annotate_no_book_no_headers():
    ann = annotate_pgn(_pgn("1. a3 e5"))
    assert ann == annotate_pgn(_pgn("1. a3 e5"))  # deterministic
    assert ann.theory_exit_ply == 1
    assert ann.name is None


def test_annotate_empty_pgn():
    ann = annotate_pgn("")
    assert ann.theory_exit_ply is None and ann.name is None


def test_backfill_fills_opening_columns(tmp_path):
    pgn_file = tmp_path / "g.pgn"
    pgn_file.write_text(_pgn("1. e4 c6 2. d4 d5 3. e5 e6", result="1-0"))

    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    # import without a book: name stays NULL and even ply 1 is "out of book"
    import_pgn_file(conn, pgn_file, "A", None)
    row = conn.execute("SELECT opening_name, theory_exit_ply FROM games").fetchone()
    assert row["opening_name"] is None and row["theory_exit_ply"] == 1

    updated = backfill_openings(conn, OpeningBook(load_openings([SAMPLE])))
    assert updated == 1
    row = conn.execute("SELECT opening_name, theory_exit_ply FROM games").fetchone()
    assert row["opening_name"] == "Caro-Kann Defense: Advance Variation"
    assert row["theory_exit_ply"] == 6
    conn.close()


def test_import_with_book_stores_opening(tmp_path):
    pgn_file = tmp_path / "g.pgn"
    pgn_file.write_text(_pgn("1. e4 c6 2. d4 d5 3. e5 e6", result="1-0"))

    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    import_pgn_file(conn, pgn_file, "A", OpeningBook(load_openings([SAMPLE])))
    row = conn.execute("SELECT opening_name, opening_family, theory_exit_ply FROM games").fetchone()
    assert row["opening_name"] == "Caro-Kann Defense: Advance Variation"
    assert row["opening_family"] == "Caro-Kann Defense"
    assert row["theory_exit_ply"] == 6
    conn.close()
