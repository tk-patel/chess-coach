"""stats.py tests (T7.1) — small synthetic DB, hand-computed expectations."""

import json
from pathlib import Path

import pytest

from chesscoach.config import load_config
from chesscoach.db import connect, migrate
from chesscoach.stats import (
    basic_counts,
    blunder_rate_by_clock,
    blunder_rate_by_phase,
    build_stats,
    conversion_stats,
    motif_counts,
    openings_table,
    top_issues,
    wilson_ci,
)

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"


def _db(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    return conn


def _game(conn, uuid, result="win", color="white", time_class="blitz", rating=1300,
          accuracy=None, family=None, name=None, exit_ply=None, end_time=1000,
          url="u"):
    conn.execute(
        "INSERT INTO games (uuid, source, user_color, result, pgn, time_class,"
        " user_rating, user_accuracy, opening_family, opening_name, theory_exit_ply,"
        " end_time, url) VALUES (?, 'api', ?, ?, 'x', ?, ?, ?, ?, ?, ?, ?, ?)",
        (uuid, color, result, time_class, rating, accuracy, family, name,
         exit_ply, end_time, url),
    )
    conn.commit()


def _move(conn, uuid, ply, phase="middlegame", classification=None,
          win_before=None, low_clock=0, time_spent=None, motifs=None):
    conn.execute(
        "INSERT INTO moves (game_uuid, ply, color, is_user, san, uci, fen_before,"
        " phase, classification, win_before, low_clock, time_spent, motifs_json)"
        " VALUES (?, ?, 'white', 1, 'e4', 'e2e4', 'x', ?, ?, ?, ?, ?, ?)",
        (uuid, ply, phase, classification, win_before, low_clock, time_spent,
         json.dumps(motifs) if motifs else None),
    )
    conn.commit()


# --- wilson ---------------------------------------------------------------


def test_wilson_ci_known_values():
    assert wilson_ci(0, 0) is None
    low, high = wilson_ci(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-3)
    assert high == pytest.approx(0.7634, abs=1e-3)
    low0, high0 = wilson_ci(0, 10)
    assert low0 == 0.0
    assert high0 == pytest.approx(0.2776, abs=1e-3)


# --- counts ---------------------------------------------------------------


def test_basic_counts_hand_computed(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "w1", result="win", color="white", time_class="blitz")
    _game(conn, "w2", result="loss", color="white", time_class="blitz")
    _game(conn, "b1", result="draw", color="black", time_class="rapid")
    stats = basic_counts(conn)

    assert stats["games"] == 3
    assert stats["wdl"] == {"win": 1, "draw": 1, "loss": 1}
    assert stats["overall"]["score_pct"] == 50.0
    assert stats["by_color"]["white"]["games"] == 2
    assert stats["by_color"]["white"]["score_pct"] == 50.0
    assert stats["by_color"]["black"]["score_pct"] == 50.0
    assert stats["by_time_class"]["blitz"]["games"] == 2
    assert stats["by_time_class"]["rapid"]["games"] == 1
    conn.close()


# --- mistakes -------------------------------------------------------------


def test_blunder_rate_by_phase(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "g1")
    # opening: 4 moves, 1 bad → 25.0
    for ply in (1, 2, 3):
        _move(conn, "g1", ply, phase="opening", classification="good")
    _move(conn, "g1", 4, phase="opening", classification="blunder")
    # endgame: 2 moves, 2 bad → 100.0
    _move(conn, "g1", 5, phase="endgame", classification="mistake")
    _move(conn, "g1", 6, phase="endgame", classification="blunder")

    result = blunder_rate_by_phase(conn)
    assert result["opening"] == {"moves": 4, "bad": 1, "per_100": 25.0}
    assert result["endgame"] == {"moves": 2, "bad": 2, "per_100": 100.0}
    assert result["middlegame"]["per_100"] is None
    conn.close()


def test_blunder_rate_by_clock(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "g1")
    _move(conn, "g1", 1, classification="blunder", low_clock=1)
    _move(conn, "g1", 2, classification="good", low_clock=1)
    _move(conn, "g1", 3, classification="good", low_clock=0)
    _move(conn, "g1", 4, classification="good", low_clock=0)
    result = blunder_rate_by_clock(conn)
    assert result["low_clock"]["per_100"] == 50.0
    assert result["normal"]["per_100"] == 0.0
    conn.close()


def test_motif_counts(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "g1")
    _move(conn, "g1", 1, motifs=["hung_piece", "low_clock"])
    _move(conn, "g1", 2, motifs=["hung_piece"])
    assert motif_counts(conn) == {"hung_piece": 2, "low_clock": 1}
    conn.close()


# --- conversion -----------------------------------------------------------


def test_failed_conversion_rate(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "g1", result="draw")   # reached ≥85 twice, drew → failed
    _move(conn, "g1", 21, win_before=90.0)
    _move(conn, "g1", 23, win_before=88.0)
    _game(conn, "g2", result="win")    # converted
    _move(conn, "g2", 21, win_before=95.0)
    _move(conn, "g2", 23, win_before=92.0)
    _game(conn, "g3", result="loss")   # never reached ≥85
    _move(conn, "g3", 21, win_before=40.0)

    conv = conversion_stats(conn)
    assert conv["games_reached"] == 2
    assert conv["failed"] == 1
    assert conv["per_100"] == 50.0
    conn.close()


# --- openings -------------------------------------------------------------


def test_openings_table_groups_by_family(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "g1", color="white", result="win", family="Caro-Kann Defense",
          name="Caro-Kann Defense: Advance Variation", accuracy=80.0, exit_ply=10)
    _game(conn, "g2", color="white", result="loss", family="Caro-Kann Defense",
          name="Caro-Kann Defense: Exchange Variation", accuracy=70.0, exit_ply=8)

    openings = openings_table(conn)
    fam = openings["white"][0]
    assert fam["name"] == "Caro-Kann Defense"
    assert fam["games"] == 2
    assert fam["score_pct"] == 50.0
    assert fam["avg_accuracy"] == 75.0
    assert len(fam["variations"]) == 2
    assert openings["black"] == []
    conn.close()


# --- issues / build -------------------------------------------------------


def test_top_issues_capped_at_five(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "g1")
    _move(conn, "g1", 1, phase="endgame", classification="blunder", motifs=["hung_piece"])
    _move(conn, "g1", 2, phase="endgame", classification="blunder", low_clock=1)
    config = load_config(EXAMPLE)
    issues = top_issues(conn, config)
    assert 0 < len(issues) <= 5
    assert any("hung piece" in i for i in issues)
    conn.close()


def test_build_stats_shape(tmp_path):
    conn = _db(tmp_path)
    _game(conn, "g1", result="win")
    config = load_config(EXAMPLE)
    stats = build_stats(conn, config)
    for key in ("counts", "rating_over_time", "accuracy_over_time", "phase", "clock",
                "motifs", "time_vs_blunders", "top_costly", "conversion", "openings",
                "games", "top_issues"):
        assert key in stats
    assert stats["counts"]["games"] == 1
    conn.close()
