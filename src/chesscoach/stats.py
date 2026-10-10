"""Aggregate queries for the report — PLAN.md §12.

Every function returns plain dicts/lists of primitives so templates and charts
stay dumb. Proportions carry a Wilson 95% interval; rates expose their sample
size so the report can grey out small ones.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import UTC, datetime

from chesscoach.config import Config

Z_95 = 1.96
ROLLING_WINDOW = 20
BAD_CLASSES = ("mistake", "blunder")
TIME_BUCKETS = [(0, 5), (5, 15), (15, 60), (60, float("inf"))]
CONVERSION_WIN = 85.0
CONVERSION_MIN_PLY = 20


def wilson_ci(successes: float, n: int, z: float = Z_95) -> tuple[float, float] | None:
    """Wilson score interval for a proportion; `None` when n == 0."""
    if n <= 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def _date(end_time: int | None) -> str | None:
    if end_time is None:
        return None
    return datetime.fromtimestamp(end_time, tz=UTC).strftime("%Y-%m-%d")


def _rate_per_100(bad: int, total: int) -> float | None:
    return round(100.0 * bad / total, 1) if total else None


def basic_counts(conn: sqlite3.Connection) -> dict:
    """Games, W/D/L overall and by color and time class."""
    rows = conn.execute(
        "SELECT user_color, time_class, result, COUNT(*) n FROM games"
        " GROUP BY user_color, time_class, result"
    ).fetchall()

    def blank() -> dict:
        return {"games": 0, "win": 0, "draw": 0, "loss": 0, "score_pct": None}

    overall = blank()
    by_color: dict[str, dict] = {"white": blank(), "black": blank()}
    by_time: dict[str, dict] = {}

    for row in rows:
        for bucket in (overall, by_color[row["user_color"]],
                       by_time.setdefault(row["time_class"] or "unknown", blank())):
            bucket["games"] += row["n"]
            bucket[row["result"]] += row["n"]

    def finish(bucket: dict) -> dict:
        n = bucket["games"]
        bucket["score_pct"] = (
            round(100.0 * (bucket["win"] + 0.5 * bucket["draw"]) / n, 1) if n else None
        )
        return bucket

    finish(overall)
    for bucket in by_color.values():
        finish(bucket)
    for bucket in by_time.values():
        finish(bucket)

    return {
        "games": overall["games"],
        "wdl": {"win": overall["win"], "draw": overall["draw"], "loss": overall["loss"]},
        "overall": overall,
        "by_color": by_color,
        "by_time_class": by_time,
    }


def rating_over_time(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """User rating per game, grouped by time class, oldest first."""
    rows = conn.execute(
        "SELECT time_class, end_time, user_rating FROM games"
        " WHERE user_rating IS NOT NULL ORDER BY end_time"
    ).fetchall()
    series: dict[str, list[dict]] = {}
    for row in rows:
        series.setdefault(row["time_class"] or "unknown", []).append(
            {"end_time": row["end_time"], "date": _date(row["end_time"]),
             "rating": row["user_rating"]}
        )
    return series


def accuracy_over_time(conn: sqlite3.Connection) -> list[dict]:
    """Rolling mean of user_accuracy over games with an analyzed accuracy."""
    rows = conn.execute(
        "SELECT end_time, user_accuracy FROM games"
        " WHERE user_accuracy IS NOT NULL ORDER BY end_time"
    ).fetchall()
    values = [row["user_accuracy"] for row in rows]
    series = []
    for i, row in enumerate(rows):
        window = values[max(0, i - ROLLING_WINDOW + 1): i + 1]
        series.append(
            {"date": _date(row["end_time"]),
             "rolling": round(sum(window) / len(window), 1)}
        )
    return series


def blunder_rate_by_phase(conn: sqlite3.Connection) -> dict:
    """(mistakes + blunders) per 100 user moves, per phase."""
    total = dict(
        conn.execute(
            "SELECT phase, COUNT(*) n FROM moves WHERE is_user = 1 GROUP BY phase"
        ).fetchall()
    )
    bad = dict(
        conn.execute(
            "SELECT phase, COUNT(*) n FROM moves WHERE is_user = 1"
            " AND classification IN ('mistake', 'blunder') GROUP BY phase"
        ).fetchall()
    )
    return {
        ph: {"moves": total.get(ph, 0), "bad": bad.get(ph, 0),
             "per_100": _rate_per_100(bad.get(ph, 0), total.get(ph, 0))}
        for ph in ("opening", "middlegame", "endgame")
    }


def blunder_rate_by_clock(conn: sqlite3.Connection) -> dict:
    """(mistakes + blunders) per 100 user moves, split by low_clock (NULL excluded)."""
    rows = conn.execute(
        "SELECT low_clock, COUNT(*) n,"
        " SUM(classification IN ('mistake', 'blunder')) bad"
        " FROM moves WHERE is_user = 1 AND low_clock IS NOT NULL GROUP BY low_clock"
    ).fetchall()
    result = {"low_clock": {"moves": 0, "bad": 0, "per_100": None},
              "normal": {"moves": 0, "bad": 0, "per_100": None}}
    for row in rows:
        key = "low_clock" if row["low_clock"] else "normal"
        result[key]["moves"] += row["n"]
        result[key]["bad"] += row["bad"] or 0
    for bucket in result.values():
        bucket["per_100"] = _rate_per_100(bucket["bad"], bucket["moves"])
    return result


def motif_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Count of each motif tag across qualifying user moves."""
    counts: dict[str, int] = {}
    for row in conn.execute(
        "SELECT motifs_json FROM moves WHERE is_user = 1 AND motifs_json IS NOT NULL"
    ):
        for tag in json.loads(row["motifs_json"]):
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def time_vs_blunders(conn: sqlite3.Connection) -> list[dict]:
    """Blunder rate per time-spent bucket (does quick play cause mistakes?)."""
    rows = conn.execute(
        "SELECT time_spent, classification FROM moves"
        " WHERE is_user = 1 AND time_spent IS NOT NULL"
    ).fetchall()
    buckets = [{"lo": lo, "hi": hi, "moves": 0, "bad": 0} for lo, hi in TIME_BUCKETS]
    for row in rows:
        spent = row["time_spent"]
        for bucket in buckets:
            if bucket["lo"] <= spent < bucket["hi"]:
                bucket["moves"] += 1
                if row["classification"] in BAD_CLASSES:
                    bucket["bad"] += 1
                break
    for bucket in buckets:
        bucket["per_100"] = _rate_per_100(bucket["bad"], bucket["moves"])
    return buckets


def top_costly_moves(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        "SELECT m.san, m.best_san, m.win_drop, m.motifs_json, m.phase,"
        " m.game_uuid, g.opening_name, g.url, g.end_time"
        " FROM moves m JOIN games g ON g.uuid = m.game_uuid"
        " WHERE m.is_user = 1 AND m.win_drop IS NOT NULL"
        " ORDER BY m.win_drop DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {
            "date": _date(row["end_time"]),
            "opening": row["opening_name"],
            "san": row["san"],
            "best_san": row["best_san"],
            "win_drop": round(row["win_drop"], 1),
            "motifs": json.loads(row["motifs_json"]) if row["motifs_json"] else [],
            "phase": row["phase"],
            "game_url": row["url"],
        }
        for row in rows
    ]


def conversion_stats(conn: sqlite3.Connection) -> dict:
    """Failed conversions per 100 games where the user reached ≥85 win% (§8.8)."""
    reached = 0
    failed = 0
    uuids = [r["uuid"] for r in conn.execute("SELECT uuid FROM games")]
    for uuid in uuids:
        wins = [
            r["win_before"]
            for r in conn.execute(
                "SELECT win_before FROM moves WHERE game_uuid = ? AND is_user = 1"
                " AND ply > ? AND win_before IS NOT NULL",
                (uuid, CONVERSION_MIN_PLY),
            )
        ]
        peaks = [w for w in wins if w >= CONVERSION_WIN]
        if not peaks:
            continue
        reached += 1
        result = conn.execute(
            "SELECT result FROM games WHERE uuid = ?", (uuid,)
        ).fetchone()["result"]
        if len(peaks) >= 2 and result != "win":
            failed += 1
    return {
        "games_reached": reached,
        "failed": failed,
        "per_100": _rate_per_100(failed, reached),
    }


def openings_table(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Per-color opening families with an expandable variation level."""
    rows = conn.execute(
        "SELECT user_color, opening_family, opening_name, result, user_accuracy,"
        " theory_exit_ply FROM games WHERE opening_family IS NOT NULL"
    ).fetchall()

    def new_bucket() -> dict:
        return {"games": 0, "score": 0.0, "accuracy": [], "exit_plies": []}

    families: dict[str, dict[str, dict]] = {"white": {}, "black": {}}
    for row in rows:
        color = row["user_color"]
        for key in (row["opening_family"], row["opening_name"]):
            bucket = families[color].setdefault(key, new_bucket())
            bucket["games"] += 1
            bucket["score"] += {"win": 1.0, "draw": 0.5, "loss": 0.0}[row["result"]]
            if row["user_accuracy"] is not None:
                bucket["accuracy"].append(row["user_accuracy"])
            if row["theory_exit_ply"] is not None:
                bucket["exit_plies"].append(row["theory_exit_ply"])

    def finalize(bucket: dict, family: str, color: str, conn) -> dict:
        n = bucket["games"]
        ci = wilson_ci(bucket["score"], n)
        exit_plies = sorted(bucket["exit_plies"])
        common = _common_first_mistake(conn, family, color)
        return {
            "name": family,
            "games": n,
            "score_pct": round(100.0 * bucket["score"] / n, 1) if n else None,
            "score_ci": [round(100 * ci[0], 1), round(100 * ci[1], 1)] if ci else None,
            "avg_accuracy": (
                round(sum(bucket["accuracy"]) / len(bucket["accuracy"]), 1)
                if bucket["accuracy"] else None
            ),
            "median_exit_move": (
                exit_plies[len(exit_plies) // 2] if exit_plies else None
            ),
            "common_first_mistake": common,
        }

    result: dict[str, list[dict]] = {}
    for color in ("white", "black"):
        fam_rows = []
        for family, bucket in families[color].items():
            if family not in {r["opening_family"] for r in rows}:
                continue  # only families at the top level
            variations = []
            for name, var_bucket in families[color].items():
                if name != family and name.startswith(family):
                    variations.append(finalize(var_bucket, name, color, conn))
            entry = finalize(bucket, family, color, conn)
            entry["variations"] = sorted(variations, key=lambda v: -v["games"])
            fam_rows.append(entry)
        result[color] = sorted(fam_rows, key=lambda e: -e["games"])
    return result


def _common_first_mistake(conn: sqlite3.Connection, opening: str, color: str) -> dict | None:
    row = conn.execute(
        "SELECT m.san, COUNT(*) n FROM moves m JOIN games g ON g.uuid = m.game_uuid"
        " WHERE m.is_user = 1 AND m.classification IN ('mistake', 'blunder')"
        " AND g.user_color = ? AND g.opening_name = ?"
        " GROUP BY m.san ORDER BY n DESC, m.san LIMIT 1",
        (color, opening),
    ).fetchone()
    return {"san": row["san"], "count": row["n"]} if row else None


def games_table(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT g.end_time, g.user_color, g.opp_rating, g.time_class, g.opening_name,"
        " g.result, g.user_accuracy, g.url,"
        " (SELECT COUNT(*) FROM moves m WHERE m.game_uuid = g.uuid AND m.is_user = 1"
        "  AND m.classification = 'blunder') blunders"
        " FROM games g ORDER BY g.end_time DESC"
    ).fetchall()
    return [
        {
            "date": _date(row["end_time"]),
            "color": row["user_color"],
            "opp_rating": row["opp_rating"],
            "time_class": row["time_class"],
            "opening": row["opening_name"],
            "result": row["result"],
            "accuracy": (
                round(row["user_accuracy"], 1)
                if row["user_accuracy"] is not None else None
            ),
            "blunders": row["blunders"],
            "game_url": row["url"],
        }
        for row in rows
    ]


def top_issues(conn: sqlite3.Connection, config: Config) -> list[str]:
    """≤5 auto-generated bullet sentences (§12), ranked by games affected."""
    from chesscoach.classify import win_percentage  # noqa: F401 (kept for parity)

    issues: list[tuple[int, str]] = []

    phase = blunder_rate_by_phase(conn)
    total_bad = sum(p["bad"] for p in phase.values())
    total_moves = sum(p["moves"] for p in phase.values())
    if total_bad and total_moves:
        worst = max(phase, key=lambda p: (phase[p]["per_100"] or 0))
        bad_share = 100.0 * phase[worst]["bad"] / total_bad
        move_share = 100.0 * phase[worst]["moves"] / total_moves
        if phase[worst]["bad"]:
            issues.append((
                phase[worst]["bad"],
                f"{bad_share:.0f}% of your blunders/mistakes happen in {worst}s, "
                f"which are only {move_share:.0f}% of your moves.",
            ))

    clock = blunder_rate_by_clock(conn)
    lc, norm = clock["low_clock"], clock["normal"]
    lc_rate, norm_rate = lc["per_100"], norm["per_100"]
    if lc_rate is not None and norm_rate is not None and lc_rate > norm_rate:
        issues.append((
            lc["bad"],
            f"You blunder {lc_rate:.1f} moves per 100 in time trouble vs "
            f"{norm_rate:.1f} when you have time.",
        ))

    motifs = motif_counts(conn)
    for tag, count in sorted(motifs.items(), key=lambda kv: -kv[1])[:3]:
        issues.append((count, f"Top tactical theme: {tag.replace('_', ' ')} ({count}×)."))

    conv = conversion_stats(conn)
    if conv["per_100"] is not None and conv["failed"]:
        issues.append((
            conv["failed"],
            f"You failed to convert {conv['failed']} of {conv['games_reached']} games "
            f"where you reached a winning position.",
        ))

    issues.sort(key=lambda pair: -pair[0])
    return [text for _, text in issues[:5]]


def build_stats(conn: sqlite3.Connection, config: Config) -> dict:
    """Everything the report templates need, in one dict."""
    return {
        "counts": basic_counts(conn),
        "rating_over_time": rating_over_time(conn),
        "accuracy_over_time": accuracy_over_time(conn),
        "phase": blunder_rate_by_phase(conn),
        "clock": blunder_rate_by_clock(conn),
        "motifs": motif_counts(conn),
        "time_vs_blunders": time_vs_blunders(conn),
        "top_costly": top_costly_moves(conn),
        "conversion": conversion_stats(conn),
        "openings": openings_table(conn),
        "games": games_table(conn),
        "top_issues": top_issues(conn, config),
    }
