"""Configuration loading and validation.

`config.toml` (see `config.example.toml` / PLAN.md §5) is parsed into a
`Config` dataclass. Loading itself never fails on placeholder values — only the
checks a given command actually needs (`require_username`, `require_engine`)
raise, so e.g. `init` works before the user has edited the file.
"""

from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    """Raised when a config value is missing, malformed, or a placeholder."""


@dataclass
class FetchConfig:
    user_agent: str
    time_classes: list[str]
    rules: str
    rated_only: bool


@dataclass
class EngineConfig:
    path: str
    threads_per_worker: int
    hash_mb: int
    workers: int
    pass1_depth: int
    pass2_depth: int
    pass2_multipv: int


@dataclass
class AnalysisConfig:
    min_plies: int
    opening_max_ply: int
    endgame_material: int


@dataclass
class PuzzlesConfig:
    min_drop: float
    min_best_winpct: float
    uniqueness_gap: float
    accept_within: float


@dataclass
class ReportConfig:
    min_games_opening: int


@dataclass
class Config:
    username: str
    fetch: FetchConfig
    engine: EngineConfig
    analysis: AnalysisConfig
    puzzles: PuzzlesConfig
    report: ReportConfig


def _default_workers() -> int:
    return max(1, (os.cpu_count() or 1) - 1)


def _section(data: dict, name: str) -> dict:
    section = data.get(name)
    if not isinstance(section, dict):
        raise ConfigError(f"config.toml is missing the [{name}] section")
    return section


def _get(section: dict, key: str, section_name: str) -> object:
    if key not in section:
        raise ConfigError(f"config.toml [{section_name}] is missing required key '{key}'")
    return section[key]


def _int(section: dict, key: str, name: str, *, minimum: int | None = None) -> int:
    value = _get(section, key, name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"[{name}] {key} must be an integer")
    if minimum is not None and value < minimum:
        raise ConfigError(f"[{name}] {key} must be >= {minimum}")
    return value


def _float(section: dict, key: str, name: str) -> float:
    value = _get(section, key, name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"[{name}] {key} must be a number")
    return float(value)


def _bool(section: dict, key: str, name: str) -> bool:
    value = _get(section, key, name)
    if not isinstance(value, bool):
        raise ConfigError(f"[{name}] {key} must be a boolean")
    return value


def _str(section: dict, key: str, name: str) -> str:
    value = _get(section, key, name)
    if not isinstance(value, str):
        raise ConfigError(f"[{name}] {key} must be a string")
    return value


def _str_list(section: dict, key: str, name: str) -> list[str]:
    value = _get(section, key, name)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"[{name}] {key} must be a list of strings")
    return list(value)


def load_config(path: str | Path) -> Config:
    """Parse and validate `path`, returning a `Config`.

    Raises `ConfigError` on missing sections, wrong types, or out-of-range
    values. Placeholder values (e.g. username == "CHANGE_ME") load fine; call
    `require_username` when a command needs the real one.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read config at {path}: {exc}") from exc
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config at {path} is not valid TOML: {exc}") from exc

    username = _str(_section(data, "player"), "username", "player")

    fetch = _section(data, "fetch")
    engine = _section(data, "engine")
    analysis = _section(data, "analysis")
    puzzles = _section(data, "puzzles")
    report = _section(data, "report")

    workers = engine.get("workers")
    if workers is None:
        workers = _default_workers()
    elif isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ConfigError("[engine] workers must be an integer >= 1")

    return Config(
        username=username,
        fetch=FetchConfig(
            user_agent=_str(fetch, "user_agent", "fetch"),
            time_classes=_str_list(fetch, "time_classes", "fetch"),
            rules=_str(fetch, "rules", "fetch"),
            rated_only=_bool(fetch, "rated_only", "fetch"),
        ),
        engine=EngineConfig(
            path=_str(engine, "path", "engine"),
            threads_per_worker=_int(engine, "threads_per_worker", "engine", minimum=1),
            hash_mb=_int(engine, "hash_mb", "engine", minimum=1),
            workers=workers,
            pass1_depth=_int(engine, "pass1_depth", "engine", minimum=1),
            pass2_depth=_int(engine, "pass2_depth", "engine", minimum=1),
            pass2_multipv=_int(engine, "pass2_multipv", "engine", minimum=1),
        ),
        analysis=AnalysisConfig(
            min_plies=_int(analysis, "min_plies", "analysis", minimum=1),
            opening_max_ply=_int(analysis, "opening_max_ply", "analysis", minimum=1),
            endgame_material=_int(analysis, "endgame_material", "analysis", minimum=0),
        ),
        puzzles=PuzzlesConfig(
            min_drop=_float(puzzles, "min_drop", "puzzles"),
            min_best_winpct=_float(puzzles, "min_best_winpct", "puzzles"),
            uniqueness_gap=_float(puzzles, "uniqueness_gap", "puzzles"),
            accept_within=_float(puzzles, "accept_within", "puzzles"),
        ),
        report=ReportConfig(
            min_games_opening=_int(report, "min_games_opening", "report", minimum=1),
        ),
    )


def require_username(config: Config) -> str:
    """Return the username, raising if it is still the placeholder."""
    if config.username.strip() == "CHANGE_ME":
        raise ConfigError(
            "config.toml still has username = \"CHANGE_ME\"; set your chess.com username first"
        )
    return config.username


def require_engine(config: Config) -> str:
    """Resolve the engine path, raising if it cannot be executed (for analysis)."""
    path = config.engine.path
    if os.sep in path or (os.altsep and os.altsep in path):
        resolved = str(Path(path).expanduser())
        if not os.access(resolved, os.X_OK):
            raise ConfigError(f"engine binary is not executable: {resolved}")
        return resolved
    resolved = shutil.which(path)
    if resolved is None:
        raise ConfigError(
            f"engine '{path}' not found on PATH; set [engine] path in config.toml"
        )
    return resolved
