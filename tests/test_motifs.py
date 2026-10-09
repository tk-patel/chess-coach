"""Motif detector tests (T5.1) — driven by tests/fixtures/positions.json.

Every fixture is self-validating: the FEN must be legal and every UCI move in the
best/reply lines must be legal in sequence. No engine needed (§10 fixture rule).
"""

import json
from pathlib import Path

import chess
import pytest

from chesscoach.motifs import detect_motifs

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "positions.json"

CASES = json.loads(FIXTURE.read_text())
BY_TAG: dict[str, list[dict]] = {}
for case in CASES:
    BY_TAG.setdefault(case["tag"], []).append(case)


def _detect(case):
    board = chess.Board(case["fen"])
    return detect_motifs(
        board,
        case["played"],
        best_pv=case["best_pv"],
        reply_pv=case["reply_pv"],
        mate_before=case["mate_before"],
        mate_after=case["mate_after"],
        low_clock=case["low_clock"],
    )


def test_fixture_covers_every_tag():
    expected = {
        "allowed_mate", "missed_mate", "back_rank", "hung_piece", "allowed_fork",
        "missed_fork", "allowed_pin", "missed_capture", "promotion", "low_clock",
        "positional",
    }
    assert expected <= set(BY_TAG)
    for tag in expected:
        positives = [c for c in BY_TAG[tag] if c["positive"]]
        negatives = [c for c in BY_TAG[tag] if not c["positive"]]
        assert len(positives) >= 2, f"{tag}: need ≥2 positive fixtures"
        assert len(negatives) >= 1, f"{tag}: need ≥1 negative fixture"


def _case_id(case: dict) -> str:
    kind = "P" if case["positive"] else "N"
    return f"{case['tag']}-{kind}-{case['fen'][:12]}"


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_fixture_is_valid(case):
    board = chess.Board(case["fen"])
    assert board.is_valid()
    played = chess.Move.from_uci(case["played"])
    assert played in board.legal_moves
    after = board.copy()
    after.push(played)
    for uci in case["reply_pv"]:
        move = chess.Move.from_uci(uci)
        assert move in after.legal_moves, f"reply {uci} illegal"
        after.push(move)
    best = board.copy()
    for uci in case["best_pv"]:
        move = chess.Move.from_uci(uci)
        assert move in best.legal_moves, f"best {uci} illegal"
        best.push(move)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_fixture_expectation(case):
    tags = _detect(case)
    if case["positive"]:
        assert case["tag"] in tags, f"expected {case['tag']} in {tags}"
    else:
        assert case["tag"] not in tags, f"did not expect {case['tag']} in {tags}"


def test_deterministic_and_sorted():
    case = BY_TAG["hung_piece"][0]
    first = _detect(case)
    assert first == _detect(case)
    assert first == sorted(first)


def test_positional_is_the_fallback():
    case = next(c for c in BY_TAG["positional"] if c["positive"])
    assert _detect(case) == ["positional"]


def test_low_clock_is_only_tag_when_quiet():
    case = next(c for c in BY_TAG["low_clock"] if c["positive"])
    assert set(_detect(case)) <= {"low_clock", "positional"}
