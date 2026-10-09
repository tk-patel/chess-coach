"""Batch analysis tests (T3.3) — executor injected, no engine needed."""

from pathlib import Path

import chess

from chesscoach.analyze import run_batch
from chesscoach.config import load_config
from chesscoach.db import connect, migrate
from chesscoach.importer import import_pgn_file

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"

LONG = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6"
SHORT = "1. f3 e5 2. g4 Qh4#"


def _pgn(moves: str, result: str, date: str) -> str:
    return (
        f'[Event "T"]\n[White "A"]\n[Black "B"]\n[Result "{result}"]\n'
        f'[UTCDate "{date}"]\n[UTCTime "00:00:00"]\n\n{moves} {result}\n'
    )


def _fake_rows(n: int = 2) -> list[dict]:
    fen = chess.Board().fen()
    return [
        {
            "ply": i + 1,
            "color": "white" if i % 2 == 0 else "black",
            "is_user": i % 2 == 0,
            "san": "e4",
            "uci": "e2e4",
            "fen_before": fen,
        }
        for i in range(n)
    ]


def _db(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    return conn


def _import_games(conn, tmp_path, n_long: int = 2):
    path = tmp_path / "games.pgn"
    chunks = [
        _pgn(LONG, "*", f"2020.01.0{i + 1}") for i in range(n_long)
    ]
    path.write_text("\n".join(chunks))
    import_pgn_file(conn, path, "A")
    return conn


def test_second_run_skips_already_done_games(tmp_path):
    conn = _db(tmp_path)
    _import_games(conn, tmp_path, 2)
    config = load_config(EXAMPLE)

    seen_first: list[str] = []

    def first_run(specs):
        for spec in specs:
            seen_first.append(spec["uuid"])
            yield (spec["uuid"], "done", _fake_rows(), "FakeEngine 1.0", None)

    result1 = run_batch(conn, config, executor=first_run)
    assert result1.analyzed == 2
    assert len(seen_first) == 2

    # Nothing left pending → a second run selects no games.
    result2 = run_batch(conn, config, executor=first_run)
    assert result2.analyzed == 0

    statuses = [r["analysis_status"] for r in conn.execute("SELECT analysis_status FROM games")]
    assert statuses == ["done", "done"]
    conn.close()


def test_crash_mid_run_resumes_without_redoing_done(tmp_path):
    conn = _db(tmp_path)
    _import_games(conn, tmp_path, 2)
    config = load_config(EXAMPLE)

    def crashing(specs):
        yield (specs[0]["uuid"], "done", _fake_rows(), "FakeEngine 1.0", None)
        raise RuntimeError("simulated crash")

    try:
        run_batch(conn, config, executor=crashing)
    except RuntimeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected the crash to propagate")

    rows = {
        r["uuid"]: r["analysis_status"]
        for r in conn.execute("SELECT uuid, analysis_status FROM games")
    }
    assert sorted(rows.values()) == ["done", "pass1"]

    still_pending = next(u for u, st in rows.items() if st == "pass1")

    seen: list[str] = []

    def resume(specs):
        for spec in specs:
            seen.append(spec["uuid"])
            yield (spec["uuid"], "done", _fake_rows(), "FakeEngine 1.0", None)

    result = run_batch(conn, config, executor=resume)
    assert result.analyzed == 1
    assert seen == [still_pending]  # the done game was not redone
    statuses = [
        r["analysis_status"]
        for r in conn.execute("SELECT analysis_status FROM games")
    ]
    assert statuses == ["done", "done"]
    conn.close()


def test_per_game_error_is_recorded(tmp_path):
    conn = _db(tmp_path)
    _import_games(conn, tmp_path, 1)
    config = load_config(EXAMPLE)

    def failing(specs):
        for spec in specs:
            yield (spec["uuid"], "error", None, None, "ParseError: boom")

    result = run_batch(conn, config, executor=failing)
    assert result.errors == 1
    assert result.analyzed == 0
    row = conn.execute("SELECT analysis_status, analysis_error FROM games").fetchone()
    assert row["analysis_status"] == "error"
    assert "boom" in row["analysis_error"]
    conn.close()


def test_short_games_are_skipped(tmp_path):
    conn = _db(tmp_path)
    path = tmp_path / "g.pgn"
    path.write_text(_pgn(SHORT, "0-1", "2020.01.01"))
    import_pgn_file(conn, path, "A")
    config = load_config(EXAMPLE)

    def noop(specs):
        return iter(())

    result = run_batch(conn, config, executor=noop)
    assert result.skipped == 1
    row = conn.execute("SELECT analysis_status FROM games").fetchone()
    assert row["analysis_status"] == "skipped"
    conn.close()


def test_limit_selects_oldest_first(tmp_path):
    conn = _db(tmp_path)
    _import_games(conn, tmp_path, 3)
    config = load_config(EXAMPLE)

    seen: list[str] = []
    expected = [r["uuid"] for r in conn.execute("SELECT uuid FROM games ORDER BY end_time")]

    def record(specs):
        for spec in specs:
            seen.append(spec["uuid"])
            yield (spec["uuid"], "done", _fake_rows(), "FakeEngine", None)

    result = run_batch(conn, config, limit=2, executor=record)
    assert result.analyzed == 2
    assert seen == expected[:2]
    conn.close()
