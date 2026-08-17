#!/usr/bin/env python3
"""Behavioral tests for chart.py, the worklog live-diagram renderer.

Run: python3 test_chart.py
Exits 0 on success, non-zero (with a FAIL line) otherwise.

render_chart() is a pure function of (config, points), so every test here is a
string assertion. No server, no browser, no temp directory.
"""
import json
import math
import os
import re
import sys

import chart

failures = []


def check(cond, msg):
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        failures.append(msg)


def cfg(**over):
    base = {"id": "f1", "type": "progress", "title": "Test F1",
            "x_label": "hypothesis", "y_label": "F1", "goal": "higher"}
    base.update(over)
    return base


def pts(*triples):
    """(x, y) or (x, y, series) or (x, y, series, label) -> point dicts."""
    out = []
    for t in triples:
        p = {"x": t[0], "y": t[1]}
        if len(t) > 2 and t[2]:
            p["s"] = t[2]
        if len(t) > 3 and t[3]:
            p["l"] = t[3]
        out.append(p)
    return out


def polyline(svg, cls):
    """The points= attribute of the first polyline carrying `cls`."""
    m = re.search(r'<polyline[^>]*class="[^"]*\b' + cls + r'\b[^"]*"[^>]*>', svg)
    if not m:
        return None
    pm = re.search(r'points="([^"]*)"', m.group(0))
    return pm.group(1) if pm else None


def coords(points_attr):
    return [tuple(float(v) for v in pair.split(","))
            for pair in points_attr.split() if "," in pair]


def numbers(svg):
    return [float(n) for n in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", svg)]


def test_nice_ticks_uses_1_2_5_steps():
    for lo, hi in ((0.0, 1.0), (0.975, 1.0), (0, 83), (-3.5, 12.25),
                   (1e-6, 3e-6), (100.0, 100.4)):
        ticks = chart.nice_ticks(lo, hi)
        check(len(ticks) >= 3, f"nice_ticks({lo},{hi}) gives 3+ ticks (got {len(ticks)})")
        steps = {round(b - a, 12) for a, b in zip(ticks, ticks[1:])}
        check(len(steps) == 1, f"nice_ticks({lo},{hi}) is evenly spaced (got {steps})")
        step = steps.pop()
        mant = step / 10 ** math.floor(math.log10(step))
        check(abs(mant - round(mant)) < 1e-9 and round(mant) in (1, 2, 5),
              f"nice_ticks({lo},{hi}) step {step} is 1/2/5 x 10^k")
        check(ticks[0] <= lo + 1e-12 and ticks[-1] >= hi - 1e-12,
              f"nice_ticks({lo},{hi}) spans the range")


def test_empty_chart_still_renders_a_frame():
    svg = chart.render_chart(cfg(), [])
    check("<svg" in svg and "</svg>" in svg, "an empty chart still renders an svg")
    check("wl-empty" in svg, "an empty chart says it has no points")
    check("Test F1" in svg, "an empty chart still shows its title")
    check("nan" not in svg.lower(), "an empty chart emits no NaN")


def test_running_best_is_monotonic_for_higher_is_better():
    svg = chart.render_chart(
        cfg(), pts((0, 0.90, "kept"), (1, 0.85), (2, 0.93, "kept"),
                   (3, 0.80), (4, 0.91)))
    line = polyline(svg, "wl-best")
    check(line is not None, "progress draws a running-best polyline")
    ys = [y for _, y in coords(line)]
    # SVG y grows downward, so higher-is-better means the line never descends.
    check(all(b <= a + 1e-9 for a, b in zip(ys, ys[1:])),
          f"running best never worsens for goal=higher (got {ys})")


def test_running_best_follows_goal_lower():
    svg = chart.render_chart(
        cfg(goal="lower", y_label="BPB"),
        pts((0, 0.998), (1, 0.991), (2, 0.995), (3, 0.987)))
    ys = [y for _, y in coords(polyline(svg, "wl-best"))]
    check(all(b >= a - 1e-9 for a, b in zip(ys, ys[1:])),
          f"running best never worsens for goal=lower (got {ys})")


def test_labels_and_title_are_escaped():
    nasty = '<script>alert("x")</script>'
    svg = chart.render_chart(cfg(title=nasty, y_label=nasty),
                             pts((0, 1.0, "kept", nasty)))
    check("<script>" not in svg, "a hostile label never reaches the page as markup")
    check("&lt;script&gt;" in svg, "a hostile label is escaped, not dropped")
    check(svg.count("&lt;script&gt;") >= 3,
          "title, axis label and point label are all escaped")


def test_single_point_and_flat_series_render():
    one = chart.render_chart(cfg(), pts((0, 0.9106, "kept")))
    check("<circle" in one, "one point renders a marker")
    check("nan" not in one.lower() and "inf" not in one.lower(),
          "one point produces no NaN or inf")
    flat = chart.render_chart(cfg(), pts((0, 0.5), (1, 0.5), (2, 0.5)))
    check("nan" not in flat.lower(), "a flat series produces no NaN")
    check(all(math.isfinite(n) for n in numbers(flat)),
          "every number in a flat series render is finite")
    zero = chart.render_chart(cfg(), pts((0, 0.0), (1, 0.0)))
    check("nan" not in zero.lower(), "an all-zero series produces no NaN")


def test_bad_points_are_dropped_not_fatal():
    svg = chart.render_chart(cfg(), [
        {"x": 0, "y": 0.9},
        {"x": 1, "y": "abc"},
        {"x": 2},
        {"x": None, "y": 0.8},          # a null x is an omitted x: still usable
        {"x": 3, "y": float("nan")},
        {"x": 4, "y": float("inf")},
        "not a dict",
        {"x": 5, "y": 0.95, "s": "kept"},
    ])
    check(svg.count("<circle") == 3,
          f"only the three usable points render (got {svg.count('<circle')})")
    check("nan" not in svg.lower(), "a NaN point does not leak into the output")


def test_baseline_is_drawn_with_its_label():
    svg = chart.render_chart(
        cfg(baseline=0.8448, baseline_label="always unchanged"),
        pts((0, 0.90), (1, 0.91)))
    check("wl-baseline" in svg, "a baseline draws a line")
    check("always unchanged" in svg, "a baseline draws its label")
    check("stroke-dasharray" in svg, "the baseline is dashed")


def test_baseline_widens_the_y_range():
    without = chart.render_chart(cfg(), pts((0, 0.90), (1, 0.91)))
    with_base = chart.render_chart(cfg(baseline=0.5), pts((0, 0.90), (1, 0.91)))
    check("0.5" in with_base, "a baseline below the data still appears on the axis")
    check(without != with_base, "a baseline changes the render")


def test_line_type_draws_one_polyline_per_series():
    svg = chart.render_chart(
        cfg(type="line", title="Latency"),
        pts((0, 120, "p50"), (1, 118, "p50"), (0, 400, "p95"), (1, 380, "p95")))
    check(svg.count('class="wl-line') == 2, "two series draw two polylines")
    check("p50" in svg and "p95" in svg, "the legend names both series")
    check(svg.count("<circle") == 4, "every point still gets a marker")


def test_scatter_type_draws_no_connecting_line():
    svg = chart.render_chart(cfg(type="scatter"), pts((0, 1), (1, 3), (2, 2)))
    check("wl-line" not in svg, "scatter draws no connecting polyline")
    check("wl-best" not in svg, "scatter draws no running-best line")
    check(svg.count("<circle") == 3, "scatter draws every marker")


def test_explicit_bounds_win_over_the_data():
    svg = chart.render_chart(cfg(y_min=0.0, y_max=2.0), pts((0, 0.9), (1, 1.0)))
    check("2" in svg and "0.5" in svg,
          "explicit y bounds set the axis, not the data range")


def test_unknown_type_falls_back_rather_than_raising():
    svg = chart.render_chart(cfg(type="sunburst"), pts((0, 1), (1, 2)))
    check("<svg" in svg, "an unknown type still renders something")
    check(svg.count("<circle") == 2, "an unknown type keeps the points")


def test_render_is_deterministic():
    p = pts((0, 0.9, "kept", "baseline"), (1, 0.85), (2, 0.93, "kept", "H2"))
    check(chart.render_chart(cfg(), p) == chart.render_chart(cfg(), p),
          "two renders of the same data are byte-identical")


def test_missing_x_is_positional():
    svg = chart.render_chart(cfg(), [{"y": 1.0}, {"y": 2.0}, {"y": 3.0}])
    check(svg.count("<circle") == 3, "points without x still render")
    xs = sorted(float(m) for m in re.findall(r'<circle[^>]*cx="(-?[\d.]+)"', svg))
    check(len(set(xs)) == 3, f"points without x spread across the axis (got {xs})")


def test_points_stay_inside_the_plot_area():
    svg = chart.render_chart(cfg(), pts((0, 0.1), (5, 0.9), (10, 0.5)))
    box = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    w, h = float(box.group(1)), float(box.group(2))
    for cx, cy in re.findall(r'<circle[^>]*cx="(-?[\d.]+)"[^>]*cy="(-?[\d.]+)"', svg):
        check(0 < float(cx) < w and 0 < float(cy) < h,
              f"marker ({cx},{cy}) sits inside the {w}x{h} viewBox")


def test_out_of_range_points_stay_visible_at_the_edge():
    """A forced range must not swallow the datum that broke it.

    Clamping, not clipping: matplotlib would drop the marker off-canvas, and
    the run's new best is exactly the point Eden is watching for.
    """
    svg = chart.render_chart(cfg(y_min=0.0, y_max=1.0),
                             pts((0, 0.5, "kept"), (1, 1.4, "kept", "over")))
    check(svg.count("<circle") == 2, "both points render")
    for cx, cy in re.findall(r'<circle[^>]*cx="(-?[\d.]+)"[^>]*cy="(-?[\d.]+)"', svg):
        check(0 < float(cy) < 440, f"marker cy={cy} sits inside the viewBox")
    for pl in re.findall(r'<polyline[^>]*points="([^"]*)"', svg):
        check(all(0 < y < 440 for _, y in coords(pl)),
              "every polyline vertex sits inside the viewBox")


def test_an_overflowing_span_never_emits_nan():
    svg = chart.render_chart(cfg(type="line"),
                             pts((0, -1.7e308), (1, 1.7e308)))
    check("nan" not in svg.lower(), "a span that overflows float64 emits no NaN")
    check(all(math.isfinite(n) for n in numbers(svg)),
          "every number stays finite when the span overflows")


def test_huge_x_does_not_divide_by_zero():
    # Epoch nanoseconds: at this magnitude the float ulp is 256, so widening
    # the domain by +-1 is a no-op and the old code divided by zero.
    for x in (1.755e18, 1e300):
        svg = chart.render_chart(cfg(), [{"x": x, "y": 0.91}])
        check("<circle" in svg, f"a single point at x={x:g} still renders")
        check("nan" not in svg.lower(), f"x={x:g} emits no NaN")


def test_legend_never_leaves_the_plot_area():
    svg = chart.render_chart(
        cfg(type="line"),
        pts(*[(i, i, f"a-very-long-series-name-{i}") for i in range(8)]))
    xs = [float(x) for x in re.findall(r'<rect[^>]*x="(-?[\d.]+)"', svg)]
    check(xs, "the legend drew swatches")
    check(all(x >= 70 for x in xs),
          f"every legend swatch stays inside the plot area (got min {min(xs):.1f})")


def test_many_labels_render_in_reasonable_time():
    """The renderer runs inside the request, so a slow chart hangs the page."""
    import time as _time
    points = [{"x": i, "y": 0.9 + (i % 7) * 0.001, "s": "kept",
               "l": f"hypothesis {i} changed something"} for i in range(2000)]
    t0 = _time.time()
    svg = chart.render_chart(cfg(), points)
    elapsed = _time.time() - t0
    check(elapsed < 2.0, f"2000 labelled points render in under 2s (took {elapsed:.2f}s)")
    check("<circle" in svg, "the 2000-point chart still renders")


def test_load_charts_ignores_half_written_temp_files():
    import tempfile as _tf
    task = _tf.mkdtemp(prefix="chart-tmpfile-")
    charts = os.path.join(task, "charts")
    os.makedirs(charts)
    body = json.dumps({"v": 1, "id": "f1", "type": "progress", "title": "Real"})
    for name in ("f1.json", ".chart-abc123.json"):
        with open(os.path.join(charts, name), "w", encoding="utf-8") as f:
            f.write(body)
    loaded = chart.load_charts(task)
    check(len(loaded) == 1,
          f"a leftover .chart-*.json temp file is not a chart (got {len(loaded)})")
    check(loaded[0][0]["id"] == "f1", "the real chart is the one that loads")


def test_config_survives_junk_values():
    svg = chart.render_chart(
        {"id": "x", "type": None, "title": 42, "y_min": "oops",
         "baseline": "nope", "goal": 7},
        pts((0, 1), (1, 2)))
    check("<svg" in svg, "junk config still renders")
    check("42" in svg, "a non-string title is coerced, not dropped")


def main():
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print()
    if failures:
        print(f"FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("all chart checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
