"""Openings database tests (T2.1) — real lichess TSV subset, no network."""

from pathlib import Path

import chess

from chesscoach.fetch import Response, Transport
from chesscoach.openings import (
    OpeningBook,
    OpeningsError,
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
