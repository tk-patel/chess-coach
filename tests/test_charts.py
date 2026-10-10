"""Charts tests (T7.2) — every chart returns inline SVG, empty data is graceful."""

from chesscoach import charts


def _is_svg(text: str) -> bool:
    return isinstance(text, str) and "<svg" in text


def test_bar_chart():
    assert _is_svg(charts.bar_chart(["a", "b"], [1.0, 2.0], "title", "y"))
    assert _is_svg(charts.bar_chart([], [], "empty"))  # graceful


def test_grouped_bar():
    svg = charts.grouped_bar(["x"], {"low": [3.0], "normal": [1.0]}, "t")
    assert _is_svg(svg)
    assert _is_svg(charts.grouped_bar([], {}, "empty"))


def test_line_and_multi_line():
    pts = [("2026-01-01", 100.0), ("2026-01-02", 120.0)]
    assert _is_svg(charts.line_chart(pts, "t"))
    assert _is_svg(charts.line_chart([], "empty"))
    assert _is_svg(charts.multi_line_chart({"blitz": pts, "rapid": []}, "t"))
    assert _is_svg(charts.multi_line_chart({}, "empty"))


def test_report_wrappers():
    assert _is_svg(charts.rating_charts({"blitz": [{"date": "2026-01-01", "rating": 1200}]}))
    assert _is_svg(charts.rating_charts({}))
    assert _is_svg(charts.accuracy_chart([{"date": "2026-01-01", "rolling": 80.0}]))
    assert _is_svg(charts.phase_chart(
        {"opening": {"per_100": 10.0}, "middlegame": {"per_100": 20.0},
         "endgame": {"per_100": None}}
    ))
    assert _is_svg(charts.clock_chart(
        {"low_clock": {"per_100": 40.0}, "normal": {"per_100": 5.0}}
    ))
    assert _is_svg(charts.motif_chart({"hung_piece": 3, "allowed_mate": 1}))
    assert _is_svg(charts.time_chart(
        [{"lo": 0, "hi": 5, "per_100": 10.0}, {"lo": 5, "hi": float("inf"), "per_100": None}]
    ))


def test_svg_is_inline_not_external():
    svg = charts.bar_chart(["a"], [1.0], "t")
    # no external references — matplotlib only emits internal fragment refs
    assert 'xlink:href="http' not in svg
    assert "<image" not in svg
