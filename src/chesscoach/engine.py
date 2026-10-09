"""Stockfish wrapper (§9).

A thin context manager around `chess.engine.SimpleEngine` that configures the
thread/hash budget and normalizes scores to a requested point of view (§8.1).
`evaluate` returns ranked `EngineLine`s (uci, san, cp, mate, pv) — the building
block for both analysis passes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chess
import chess.engine

from chesscoach.config import Config, require_engine

CP_CLAMP = 1000
PV_MAX_PLIES = 10


@dataclass
class EngineLine:
    """One engine line: the top move plus its principal variation."""

    uci: str
    san: str
    cp: int | None          # centipawns, clamped to ±1000, from `pov`; None if mate
    mate: int | None        # mate-in-N from `pov` (+ mate for pov, - against)
    pv_uci: list[str] = field(default_factory=list)   # best line, ≤ 10 plies


class Engine:
    """A running Stockfish process. Use as a context manager."""

    def __init__(self, path: str, threads: int = 1, hash_mb: int = 128):
        self.path = path
        self.threads = threads
        self.hash_mb = hash_mb
        self._engine: chess.engine.SimpleEngine | None = None

    @classmethod
    def from_config(cls, config: Config) -> Engine:
        """Build an `Engine` from `[engine]` in the config (resolving the path)."""
        return cls(
            path=require_engine(config),
            threads=config.engine.threads_per_worker,
            hash_mb=config.engine.hash_mb,
        )

    def __enter__(self) -> Engine:
        self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        self._engine.configure({"Threads": self.threads, "Hash": self.hash_mb})
        return self

    def __exit__(self, *exc) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    @property
    def id_name(self) -> str:
        """The engine's `id name` (e.g. 'Stockfish 17.1')."""
        if self._engine is None:
            raise RuntimeError("engine is not running (use it as a context manager)")
        return str(self._engine.id.get("name", "unknown"))

    def evaluate(
        self,
        board: chess.Board,
        depth: int,
        multipv: int = 1,
        pov: chess.Color = chess.WHITE,
    ) -> list[EngineLine]:
        """Analyze `board` at `depth`, returning up to `multipv` ranked lines.

        All scores are from `pov`'s perspective (§8.1): a positive `mate` means
        `pov` plays mate, a positive `cp` means `pov` is better.
        """
        if self._engine is None:
            raise RuntimeError("engine is not running (use it as a context manager)")

        infos = self._engine.analyse(
            board, chess.engine.Limit(depth=depth), multipv=multipv
        )
        if isinstance(infos, dict):
            infos = [infos]

        lines: list[EngineLine] = []
        for info in sorted(infos, key=lambda i: i.get("multipv", 1)):
            pv = info.get("pv") or []
            score = info.get("score")
            if not pv or score is None:
                continue
            best = pv[0]
            pov_score = score.pov(pov)
            if pov_score.is_mate():
                mate = pov_score.mate()
                cp = None
            else:
                mate = None
                raw = pov_score.score() or 0
                cp = CP_CLAMP if raw > CP_CLAMP else (-CP_CLAMP if raw < -CP_CLAMP else raw)

            lines.append(
                EngineLine(
                    uci=best.uci(),
                    san=board.san(best),
                    cp=cp,
                    mate=mate,
                    pv_uci=[move.uci() for move in pv[:PV_MAX_PLIES]],
                )
            )
        return lines
