"""Config loading and validation tests (T0.2)."""

import sys
from pathlib import Path

import pytest

from chesscoach.config import (
    ConfigError,
    load_config,
    require_engine,
    require_username,
)

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"


def test_load_example_config():
    cfg = load_config(EXAMPLE)
    assert cfg.username == "CHANGE_ME"
    assert cfg.fetch.time_classes == ["bullet", "blitz", "rapid", "daily"]
    assert cfg.fetch.rules == "chess"
    assert cfg.engine.pass1_depth == 14
    assert cfg.engine.pass2_depth == 18
    assert cfg.engine.pass2_multipv == 3
    assert cfg.analysis.endgame_material == 26
    assert cfg.puzzles.min_drop == 20.0
    assert cfg.report.min_games_opening == 15


def test_require_username_raises_on_placeholder():
    with pytest.raises(ConfigError):
        require_username(load_config(EXAMPLE))


def test_require_username_returns_real_name(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(EXAMPLE.read_text().replace("CHANGE_ME", "tjpatel"), encoding="utf-8")
    assert require_username(load_config(path)) == "tjpatel"


def test_require_engine_resolves_executable(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        EXAMPLE.read_text().replace('path = "stockfish"', f'path = "{sys.executable}"'),
        encoding="utf-8",
    )
    assert require_engine(load_config(path)) == sys.executable


def test_require_engine_raises_on_missing_binary(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        EXAMPLE.read_text().replace('path = "stockfish"', 'path = "/nonexistent/engine"'),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        require_engine(load_config(path))


def test_missing_section_raises(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text('[player]\nusername = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_bad_type_raises(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text(
        EXAMPLE.read_text().replace("pass1_depth = 14", "pass1_depth = \"fourteen\""),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(path)
