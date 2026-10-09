"""SQLite storage: connection, schema, and migrations.

The schema is defined in PLAN.md §6. `SCHEMA_VERSION` must be bumped whenever the
schema changes; add the new version's DDL to `MIGRATIONS` (never edit an already-
released version) and record a Decision in PROGRESS.md.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

MIGRATIONS: dict[int, list[str]] = {
    1: [
        """
        CREATE TABLE archives (
          url TEXT PRIMARY KEY, fetched_at INTEGER, etag TEXT, last_modified TEXT,
          game_count INTEGER
        )
        """,
        """
        CREATE TABLE games (
          uuid TEXT PRIMARY KEY,
          url TEXT,
          source TEXT NOT NULL,
          end_time INTEGER,
          time_class TEXT,
          time_control TEXT,
          base_seconds INTEGER, increment_seconds INTEGER,
          rated INTEGER,
          user_color TEXT NOT NULL,
          user_rating INTEGER, opp_rating INTEGER, opp_username TEXT,
          result TEXT NOT NULL,
          termination TEXT,
          eco TEXT, opening_name TEXT, opening_family TEXT,
          theory_exit_ply INTEGER,
          ply_count INTEGER,
          pgn TEXT NOT NULL,
          analysis_status TEXT NOT NULL DEFAULT 'pending',
          analysis_error TEXT,
          engine_id TEXT, pass1_depth INTEGER, pass2_depth INTEGER,
          user_accuracy REAL, opp_accuracy REAL,
          max_user_winpct REAL, min_user_winpct REAL
        )
        """,
        """
        CREATE TABLE moves (
          game_uuid TEXT NOT NULL REFERENCES games(uuid),
          ply INTEGER NOT NULL,
          color TEXT NOT NULL,
          is_user INTEGER NOT NULL,
          san TEXT NOT NULL, uci TEXT NOT NULL,
          fen_before TEXT NOT NULL,
          clock_after REAL,
          time_spent REAL,
          cp_before INTEGER, mate_before INTEGER,
          cp_after INTEGER, mate_after INTEGER,
          win_before REAL, win_after REAL,
          win_drop REAL,
          move_accuracy REAL,
          best_uci TEXT, best_san TEXT,
          pv_uci TEXT,
          multipv_json TEXT,
          classification TEXT,
          phase TEXT,
          low_clock INTEGER,
          motifs_json TEXT,
          PRIMARY KEY (game_uuid, ply)
        )
        """,
        """
        CREATE TABLE puzzles (
          id TEXT PRIMARY KEY,
          game_uuid TEXT NOT NULL, ply INTEGER NOT NULL,
          fen TEXT NOT NULL,
          played_san TEXT NOT NULL,
          solution_uci TEXT NOT NULL, solution_san TEXT NOT NULL,
          accepted_uci_json TEXT NOT NULL,
          line_san TEXT,
          win_drop REAL, motifs_json TEXT, phase TEXT, low_clock INTEGER,
          opening_name TEXT, game_url TEXT, end_time INTEGER
        )
        """,
        "CREATE INDEX idx_moves_user ON moves(game_uuid, is_user)",
        "CREATE INDEX idx_games_status ON games(analysis_status)",
    ],
}


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a connection with foreign keys on and row access by name."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Bring the schema up to `SCHEMA_VERSION`; returns the resulting version."""
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    current = int(row["value"]) if row else 0

    for version in sorted(MIGRATIONS):
        if version > current:
            for statement in MIGRATIONS[version]:
                conn.execute(statement)
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(version),),
            )
            current = version
    conn.commit()
    return current


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    return int(row["value"]) if row else 0
