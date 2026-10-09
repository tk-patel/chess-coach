"""Schema migration tests (T0.2)."""

from chesscoach.db import SCHEMA_VERSION, connect, migrate, schema_version

TABLES = {"meta", "archives", "games", "moves", "puzzles"}
INDEXES = {"idx_moves_user", "idx_games_status"}


def _names(conn, kind):
    return {
        row["name"]
        for row in conn.execute(f"SELECT name FROM sqlite_master WHERE type = '{kind}'")
    }


def test_migrate_creates_tables_and_indexes(tmp_path):
    conn = connect(tmp_path / "test.db")
    migrate(conn)
    assert schema_version(conn) == SCHEMA_VERSION
    assert TABLES <= _names(conn, "table")
    assert INDEXES <= _names(conn, "index")
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    conn = connect(tmp_path / "test.db")
    migrate(conn)
    migrate(conn)
    assert schema_version(conn) == SCHEMA_VERSION
    conn.close()
