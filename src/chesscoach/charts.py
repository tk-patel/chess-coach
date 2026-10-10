"""Charts for the report — PLAN.md §12 (matplotlib → inline SVG strings).

Charts are rendered with a transparent background and neutral greys so they read
on both light and dark themes (`prefers-color-scheme`). Each function returns an
SVG string that the templates inline directly — no JS chart library, no external
files.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

PALETTE = {
    "win": "#4c9f70",
    "draw": "#9a9a9a",
    "loss": "#c0504d",
    "accent": "#4a78c2",
    "accent2": "#d08a3a",
    "accent3": "#8e6bbf",
    "accent4": "#4aa3a3",
    "accent5": "#b5651d",
}
_SERIES_COLORS = [
    PALETTE["accent"], PALETTE["accent2"], PALETTE["accent3"],
    PALETTE["accent4"], PALETTE["accent5"],
]
_NEUTRAL = "#8a8a8a"

plt.rcParams.update({
    "svg.fonttype": "none",
    "font.size": 10,
    "text.color": _NEUTRAL,
    "axes.labelcolor": _NEUTRAL,
    "axes.edgecolor": _NEUTRAL,
    "xtick.color": _NEUTRAL,
    "ytick.color": _NEUTRAL,
    "axes.titlecolor": _NEUTRAL,
})


def _save(fig) -> str:
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", transparent=True, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def _empty(title: str) -> str:
    fig, ax = plt.subplots(figsize=(4, 1.6))
    ax.axis("off")
    ax.text(0.5, 0.5, "no data yet", ha="center", va="center", color=_NEUTRAL)
    ax.set_title(title)
    return _save(fig)


def _style(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.grid(True, axis="y", alpha=0.25)


def bar_chart(
    labels: list[str], values: list[float], title: str, ylabel: str = "",
    color: str | None = None,
) -> str:
    """A simple vertical bar chart."""
    if not labels or not any(v is not None for v in values):
        return _empty(title)
    fig, ax = plt.subplots(figsize=(max(3.5, 0.7 * len(labels) + 2), 3))
    bars = ax.bar(labels, [v if v is not None else 0 for v in values],
                  color=color or PALETTE["accent"])
    ax.bar_label(bars, fmt="%g", fontsize=8, color=_NEUTRAL)
    _style(ax, title, ylabel=ylabel)
    ax.tick_params(axis="x", rotation=20)
    return _save(fig)


def grouped_bar(
    categories: list[str], groups: dict[str, list[float]], title: str, ylabel: str = ""
) -> str:
    """Side-by-side bars: one series per key in `groups`."""
    if not categories or not groups:
        return _empty(title)
    n = len(groups)
    width = 0.8 / max(1, n)
    fig, ax = plt.subplots(figsize=(max(3.5, 0.9 * len(categories) + 2), 3))
    for i, (name, values) in enumerate(groups.items()):
        offsets = [j + (i - (n - 1) / 2) * width for j in range(len(categories))]
        ax.bar(offsets, [v if v is not None else 0 for v in values],
               width=width, label=name, color=_SERIES_COLORS[i % len(_SERIES_COLORS)])
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=20)
    ax.legend(frameon=False, fontsize=8)
    _style(ax, title, ylabel=ylabel)
    return _save(fig)


def line_chart(
    points: list[tuple[str, float]], title: str, ylabel: str = "", color: str | None = None
) -> str:
    """A single line; `points` is a list of (label, value) oldest first."""
    if not points:
        return _empty(title)
    xs = list(range(len(points)))
    ys = [value for _, value in points]
    fig, ax = plt.subplots(figsize=(5.5, 3))
    ax.plot(xs, ys, color=color or PALETTE["accent"], linewidth=1.6)
    step = max(1, len(points) // 6)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([label or "" for label, _ in points][::step], rotation=20)
    _style(ax, title, ylabel=ylabel)
    return _save(fig)


def multi_line_chart(
    series: dict[str, list[tuple[str, float]]], title: str, ylabel: str = ""
) -> str:
    """Several lines (e.g. rating per time class)."""
    series = {name: pts for name, pts in series.items() if pts}
    if not series:
        return _empty(title)
    fig, ax = plt.subplots(figsize=(5.5, 3))
    for i, (name, points) in enumerate(series.items()):
        xs = list(range(len(points)))
        ax.plot(xs, [v for _, v in points], linewidth=1.6,
                label=name, color=_SERIES_COLORS[i % len(_SERIES_COLORS)])
    ax.legend(frameon=False, fontsize=8)
    _style(ax, title, ylabel=ylabel)
    return _save(fig)


# --- report-specific wrappers ---------------------------------------------


def rating_charts(series: dict[str, list[dict]]) -> str:
    """One rating-over-time chart per time class, concatenated."""
    out = []
    for time_class, rows in sorted(series.items()):
        points = [(row["date"] or "", row["rating"]) for row in rows]
        out.append(line_chart(points, f"Rating over time — {time_class}", "rating"))
    return "".join(out) if out else _empty("Rating over time")


def accuracy_chart(points: list[dict]) -> str:
    pts = [(row["date"] or "", row["rolling"]) for row in points]
    return line_chart(pts, "Accuracy over time (rolling 20)", "accuracy %",
                      color=PALETTE["accent4"])


def phase_chart(phase: dict) -> str:
    labels = ["opening", "middlegame", "endgame"]
    values = [phase.get(ph, {}).get("per_100") or 0 for ph in labels]
    return bar_chart(labels, values, "Mistakes + blunders per 100 user moves by phase",
                     "per 100", color=PALETTE["accent2"])


def clock_chart(clock: dict) -> str:
    return grouped_bar(
        ["clock"],
        {"low time": [clock["low_clock"]["per_100"] or 0],
         "normal": [clock["normal"]["per_100"] or 0]},
        "Mistakes + blunders per 100 by time trouble",
        "per 100",
    )


def motif_chart(motifs: dict[str, int]) -> str:
    top = sorted(motifs.items(), key=lambda kv: -kv[1])[:12]
    return bar_chart([k.replace("_", " ") for k, _ in top], [v for _, v in top],
                     "Motif frequency", "count", color=PALETTE["accent3"])


def time_chart(buckets: list[dict]) -> str:
    labels = [f"{int(b['lo'])}–{'' if b['hi'] == float('inf') else int(b['hi'])}s"
              for b in buckets]
    return bar_chart(labels, [b["per_100"] or 0 for b in buckets],
                     "Blunder rate by time spent per move", "per 100",
                     color=PALETTE["accent5"])
