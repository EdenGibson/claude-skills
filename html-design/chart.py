#!/usr/bin/env python3
"""Live diagrams for worklog: numbers in, inline SVG out.

An agent sends points with `worklog point <slug> <id> --y 0.91`. The server
renders them here, on every request, straight into the task page. No plotting
library, no PNG, no per-project chart script: a chart is text, so it stays
sharp at any width and an update costs one appended line.

    render_chart(cfg, points) -> str   one <figure> holding inline SVG
    render_panel(task_dir)    -> str   every chart of one task, pinned strip

render_chart is a pure function of its two arguments, which is what makes the
whole renderer testable without a server (test_chart.py).

Three types:
    progress   every attempt faint, kept attempts filled, a running-best step
               line, labels on labelled points, an optional dashed baseline
    line       one polyline per series
    scatter    markers only

Nothing here raises on bad input. A chart is decoration on top of a log that
must survive, so a junk config, a torn point or a NaN is dropped and the rest
still draws.
"""
import html as html_mod
import json
import math
import os

# Canvas. Fixed user units, scaled to the page by viewBox, so the same render
# reads correctly on a laptop and on a phone.
W, H = 1000, 440
PAD_L, PAD_R, PAD_T, PAD_B = 76, 28, 48, 58

# Worklog is dark-only, and these match WORKLOG_CSS in server.py.
C_GRID = "#232734"
C_AXIS = "#3a4050"
C_MUTED = "#8b90a0"
C_TEXT = "#e7e9ee"
C_FAINT = "#4b5162"
SERIES_COLORS = ("#7ee2a8", "#7cc4ff", "#ffd479", "#ff9d9d",
                 "#c9a6ff", "#6ee7d7", "#f0a8d0", "#a3e635")

TYPES = ("progress", "line", "scatter")
# Label placement. Width is estimated from the character count, because SVG
# gives no text metrics before the browser lays it out; 6.15 is measured for
# system-ui at 11.5px on mixed-case text.
LABEL_CHAR_W = 6.15
LABEL_ROW = 14
# Placement is quadratic in the labels that overlap, and this renderer runs
# inside the HTTP request, so a runaway label count would hang the page. 2000
# labelled points took 6.5s uncapped, measured. Both bounds below hold it to a
# few milliseconds: only the nearest boxes can collide, and past ~120 labels
# the chart is unreadable anyway.
MAX_LABELS = 120
PLACED_WINDOW = 32

# Every value is pinned into +-1e300 before it is used. Two floats near the
# float64 maximum subtract to inf, and inf/inf is NaN, which reaches the SVG as
# cx="nan" and draws nothing.
VALUE_LIMIT = 1e300


def esc(v):
    """Escape anything into SVG-safe text. Coerces, because json.load yields
    ints, lists and dicts, and a chart must not fall over on one of them."""
    if v is None:
        return ""
    if not isinstance(v, str):
        v = str(v)
    return html_mod.escape(v, quote=True)


def num(v):
    """A finite float, or None. bools, strings, NaN and inf all become None."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def clamp(v, lo, hi):
    """v held inside [lo, hi]. Used for values and for screen coordinates."""
    if v < lo:
        return lo
    return hi if v > hi else v


def sig(v, digits=12):
    """Round to significant digits, not decimal places.

    round(1.5e-7, 12) is 0, which would collapse every tick on a small-step
    axis into the same value.
    """
    try:
        return float(f"{v:.{digits}g}")
    except (TypeError, ValueError, OverflowError):
        return v


def nice_ticks(lo, hi, target=6, min_step=None):
    """Evenly spaced ticks with a 1, 2 or 5 x 10^k step, spanning [lo, hi].

    Always at least three ticks, so a flat or degenerate range still draws an
    axis instead of a single line of text.
    """
    lo, hi = num(lo), num(hi)
    if lo is None or hi is None:
        lo, hi = 0.0, 1.0
    if hi < lo:
        lo, hi = hi, lo
    if hi - lo < 1e-15:
        pad = abs(hi) * 0.05 or 0.5
        lo, hi = lo - pad, hi + pad

    raw = (hi - lo) / max(2, target - 1)
    mag = 10.0 ** math.floor(math.log10(raw))
    step = 10 * mag
    for m in (1, 2, 5):
        if raw <= m * mag * (1 + 1e-9):
            step = m * mag
            break
    if min_step and step < min_step:
        step = float(min_step)

    start = math.floor(lo / step) * step
    ticks = []
    i = 0
    while i < 1000:
        t = start + i * step
        ticks.append(sig(t))
        if t >= hi - 1e-12 and len(ticks) >= 3:
            break
        i += 1
    return ticks


def tick_format(step):
    """A formatter for one axis, chosen from its step size."""
    if step <= 0:
        return lambda v: f"{v:g}"
    decimals = max(0, -int(math.floor(math.log10(step))))
    if decimals > 8:
        return lambda v: f"{v:g}"
    return lambda v: f"{v:.{decimals}f}"


def normalise(points):
    """Usable points only, in the order given, with x filled in.

    A point with no x takes its index, which is what an eval loop wants: the
    agent sends `--y 0.91` per hypothesis and the x axis counts them.
    """
    out = []
    for i, p in enumerate(points or []):
        if not isinstance(p, dict):
            continue
        y = num(p.get("y"))
        if y is None:
            continue
        x = num(p.get("x"))
        series = p.get("s")
        series = series if isinstance(series, str) and series else None
        label = p.get("l")
        label = label if isinstance(label, str) and label else None
        out.append({"x": i if x is None else clamp(x, -VALUE_LIMIT, VALUE_LIMIT),
                    "y": clamp(y, -VALUE_LIMIT, VALUE_LIMIT),
                    "s": series, "l": label, "i": i})
    return out


def running_best(points, goal):
    """The best-so-far value after each point, in x order.

    Derived from the numbers and the goal, never from the kept flag, so the
    line cannot disagree with the data it sits on.
    """
    better = (lambda a, b: a > b) if goal != "lower" else (lambda a, b: a < b)
    best = None
    out = []
    for p in sorted(points, key=lambda p: p["x"]):
        if best is None or better(p["y"], best):
            best = p["y"]
        out.append((p["x"], best))
    return out


def _cfg_str(cfg, key, fallback=""):
    v = cfg.get(key)
    if v is None or isinstance(v, (dict, list)):
        return fallback
    v = v if isinstance(v, str) else str(v)
    return v or fallback


def render_chart(cfg, points):
    """One chart as an HTML <figure> holding inline SVG."""
    cfg = cfg if isinstance(cfg, dict) else {}
    chart_id = _cfg_str(cfg, "id", "chart")
    ctype = _cfg_str(cfg, "type", "progress")
    if ctype not in TYPES:
        ctype = "progress"
    goal = "lower" if _cfg_str(cfg, "goal") == "lower" else "higher"
    title = _cfg_str(cfg, "title", chart_id)
    x_label = _cfg_str(cfg, "x_label")
    y_label = _cfg_str(cfg, "y_label")
    baseline = num(cfg.get("baseline"))
    baseline_label = _cfg_str(cfg, "baseline_label")

    pts = normalise(points)
    parts = [
        f'<text x="{PAD_L - 48}" y="28" class="wl-chart-title" fill="{C_TEXT}" '
        f'font-size="16" font-weight="600">{esc(title)}</text>'
    ]

    if not pts:
        parts.append(
            f'<text class="wl-empty" x="{W / 2:.0f}" y="{H / 2:.0f}" '
            f'text-anchor="middle" fill="{C_MUTED}" font-size="14">'
            f'No points yet</text>')
        return _figure(chart_id, title, parts)

    # --- domains -----------------------------------------------------------
    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    if baseline is not None:
        ys = ys + [baseline]

    y_lo, y_hi = min(ys), max(ys)
    span = y_hi - y_lo
    pad = span * 0.06 if span > 0 else (abs(y_hi) * 0.05 or 0.5)
    y_lo, y_hi = y_lo - pad, y_hi + pad
    forced_lo, forced_hi = num(cfg.get("y_min")), num(cfg.get("y_max"))
    if (forced_lo is not None and forced_hi is not None
            and forced_hi <= forced_lo):
        forced_lo = forced_hi = None      # a range that is not a range
    if forced_lo is not None:
        y_lo = clamp(forced_lo, -VALUE_LIMIT, VALUE_LIMIT)
    if forced_hi is not None:
        y_hi = clamp(forced_hi, -VALUE_LIMIT, VALUE_LIMIT)

    x_lo, x_hi = min(xs), max(xs)
    x_pad = (x_hi - x_lo) * 0.03
    if x_pad <= 0:
        # One x value, or several at the same x. Widen by a unit, or by a
        # fraction of the magnitude when a unit is below the float step: at
        # x=1.7e18 (epoch nanoseconds) the ulp is 256, so x - 1 == x and the
        # domain would stay empty, then divide by zero.
        x_pad = max(1.0, abs(x_hi) * 1e-9)
    x_lo, x_hi = x_lo - x_pad, x_hi + x_pad

    integral_x = all(abs(x - round(x)) < 1e-9 for x in xs)
    x_ticks = nice_ticks(x_lo, x_hi, target=8, min_step=1 if integral_x else None)
    y_ticks = nice_ticks(y_lo, y_hi, target=6)
    # The y range grows to its ticks, so the axis ends on a round number. The x
    # range does not: 84 experiments would otherwise draw an axis from -20 to
    # 100, spending a third of the width on experiment numbers that cannot
    # exist. Ticks outside the range are dropped when they are drawn.
    y_lo, y_hi = min(y_lo, y_ticks[0]), max(y_hi, y_ticks[-1])

    # Last line of defence before any division. A zero or non-finite span is a
    # bug upstream, and the cost of one here is a page full of cx="nan".
    x_span, y_span = x_hi - x_lo, y_hi - y_lo
    if not (x_span > 0) or not math.isfinite(x_span):
        x_lo, x_hi, x_span = 0.0, 1.0, 1.0
    if not (y_span > 0) or not math.isfinite(y_span):
        y_lo, y_hi, y_span = 0.0, 1.0, 1.0

    plot_w, plot_h = W - PAD_L - PAD_R, H - PAD_T - PAD_B

    def sx(x):
        return PAD_L + (x - x_lo) / x_span * plot_w

    def sy(y):
        return PAD_T + (y_hi - y) / y_span * plot_h

    # Data geometry uses the clamped pair. A forced --y-max smaller than the
    # data would otherwise put the marker outside the viewBox, where it is not
    # drawn at all: the run's new best is exactly the point Eden is watching
    # for, so it sits on the boundary instead of vanishing. Ticks keep the raw
    # sx/sy, because out-of-range ticks are dropped by position.
    def mx(x):
        return clamp(sx(x), PAD_L, PAD_L + plot_w)

    def my(y):
        return clamp(sy(y), PAD_T, PAD_T + plot_h)

    # --- grid and axes -----------------------------------------------------
    fmt_y = tick_format(y_ticks[1] - y_ticks[0])
    fmt_x = tick_format(x_ticks[1] - x_ticks[0])
    for t in y_ticks:
        y = sy(t)
        if y < PAD_T - 0.5 or y > PAD_T + plot_h + 0.5:
            continue
        parts.append(
            f'<line x1="{PAD_L:.2f}" y1="{y:.2f}" x2="{PAD_L + plot_w:.2f}" '
            f'y2="{y:.2f}" stroke="{C_GRID}" stroke-width="1"/>')
        parts.append(
            f'<text x="{PAD_L - 10:.2f}" y="{y + 4:.2f}" text-anchor="end" '
            f'fill="{C_MUTED}" font-size="12">{esc(fmt_y(t))}</text>')
    for t in x_ticks:
        x = sx(t)
        if x < PAD_L - 0.5 or x > PAD_L + plot_w + 0.5:
            continue
        parts.append(
            f'<text x="{x:.2f}" y="{PAD_T + plot_h + 22:.2f}" '
            f'text-anchor="middle" fill="{C_MUTED}" font-size="12">'
            f'{esc(fmt_x(t))}</text>')
    parts.append(
        f'<line x1="{PAD_L:.2f}" y1="{PAD_T + plot_h:.2f}" '
        f'x2="{PAD_L + plot_w:.2f}" y2="{PAD_T + plot_h:.2f}" '
        f'stroke="{C_AXIS}" stroke-width="1"/>')
    if x_label:
        parts.append(
            f'<text x="{PAD_L + plot_w / 2:.2f}" y="{H - 14}" '
            f'text-anchor="middle" fill="{C_MUTED}" font-size="13">'
            f'{esc(x_label)}</text>')
    if y_label:
        cy = PAD_T + plot_h / 2
        parts.append(
            f'<text transform="rotate(-90 22 {cy:.2f})" x="22" y="{cy:.2f}" '
            f'text-anchor="middle" fill="{C_MUTED}" font-size="13">'
            f'{esc(y_label)}</text>')

    # --- baseline ----------------------------------------------------------
    if baseline is not None:
        by = my(baseline)
        parts.append(
            f'<line class="wl-baseline" x1="{PAD_L:.2f}" y1="{by:.2f}" '
            f'x2="{PAD_L + plot_w:.2f}" y2="{by:.2f}" stroke="{C_MUTED}" '
            f'stroke-width="1.5" stroke-dasharray="6 5"/>')
        if baseline_label:
            parts.append(
                f'<text x="{PAD_L + plot_w - 6:.2f}" y="{by - 7:.2f}" '
                f'text-anchor="end" fill="{C_MUTED}" font-size="12">'
                f'{esc(baseline_label)}</text>')

    # --- series ------------------------------------------------------------
    order = []
    for p in pts:
        name = p["s"] or ("kept" if ctype == "progress" and p["l"] else "series")
        if name not in order:
            order.append(name)
    colors = {name: SERIES_COLORS[i % len(SERIES_COLORS)]
              for i, name in enumerate(order)}
    legend = []

    if ctype == "progress":
        best = running_best(pts, goal)
        step = []
        prev = None
        for x, b in best:
            if prev is not None and b != prev:
                step.append((x, prev))
            step.append((x, b))
            prev = b
        pl = " ".join(f"{mx(x):.2f},{my(y):.2f}" for x, y in step)
        parts.append(
            f'<polyline class="wl-best" points="{pl}" fill="none" '
            f'stroke="{SERIES_COLORS[0]}" stroke-width="2" '
            f'stroke-linejoin="round"/>')
        legend = [("running best", SERIES_COLORS[0], "line")]
        if any(p["s"] != "kept" for p in pts):
            legend.append(("other", C_FAINT, "dot"))
        if any(p["s"] == "kept" for p in pts):
            legend.append(("kept", SERIES_COLORS[0], "dot"))
    elif ctype == "line":
        for name in order:
            members = sorted((p for p in pts if (p["s"] or "series") == name),
                             key=lambda p: p["x"])
            if len(members) < 2:
                continue
            pl = " ".join(f"{mx(p['x']):.2f},{my(p['y']):.2f}" for p in members)
            parts.append(
                f'<polyline class="wl-line" data-series="{esc(name)}" '
                f'points="{pl}" fill="none" stroke="{colors[name]}" '
                f'stroke-width="2" stroke-linejoin="round"/>')
        legend = [(n, colors[n], "line") for n in order]
    else:
        legend = [(n, colors[n], "dot") for n in order if n != "series"]

    # Markers last, so a line never covers a point.
    for p in pts:
        cx, cy = mx(p["x"]), my(p["y"])
        if ctype == "progress":
            kept = p["s"] == "kept"
            if kept:
                parts.append(
                    f'<circle class="wl-pt kept" cx="{cx:.2f}" cy="{cy:.2f}" '
                    f'r="5.5" fill="{SERIES_COLORS[0]}" stroke="#0f1115" '
                    f'stroke-width="1.5"/>')
            else:
                parts.append(
                    f'<circle class="wl-pt" cx="{cx:.2f}" cy="{cy:.2f}" '
                    f'r="3.2" fill="{C_FAINT}"/>')
        else:
            name = p["s"] or "series"
            parts.append(
                f'<circle class="wl-pt" cx="{cx:.2f}" cy="{cy:.2f}" r="3.6" '
                f'fill="{colors[name]}"/>')

    # --- point labels ------------------------------------------------------
    # Labels are horizontal, never rotated. Rotated text reads worse, and a
    # long rotated label sweeps upward through every label to its right, which
    # is exactly where the next kept experiment sits. Each label instead takes
    # the lowest free row above its own point.
    placed = []
    label_color = SERIES_COLORS[0] if ctype == "progress" else C_MUTED
    labelled = sorted((p for p in pts if p["l"]), key=lambda p: p["x"])
    dropped = 0
    if len(labelled) > MAX_LABELS:
        keep = [p for p in labelled if p["s"] == "kept"][:MAX_LABELS]
        keep += [p for p in labelled
                 if p["s"] != "kept"][:MAX_LABELS - len(keep)]
        dropped = len(labelled) - len(keep)
        labelled = sorted(keep, key=lambda p: p["x"])
    for p in labelled:
        cx, cy = mx(p["x"]), my(p["y"])
        width = LABEL_CHAR_W * len(p["l"])
        flip = cx + width + 12 > PAD_L + plot_w      # would run off the right
        x0 = cx - 8 - width if flip else cx + 8
        ty = cy - 9
        for _ in range(24):
            if not any(abs(ty - oy) < LABEL_ROW and x0 < ox1 and ox0 < x0 + width
                       for ox0, ox1, oy in placed):
                break
            ty -= LABEL_ROW
        ty = max(ty, PAD_T + 10)
        # Labels arrive in x order, so only the nearest boxes can still collide
        # and the scan stays bounded instead of quadratic.
        placed = placed[-PLACED_WINDOW:] + [(x0, x0 + width, ty)]
        # A label pushed several rows up has lost sight of its point, so it
        # gets a hairline back to it.
        if cy - ty > LABEL_ROW + 12:
            parts.append(
                f'<line class="wl-leader" x1="{cx:.2f}" y1="{cy - 6:.2f}" '
                f'x2="{(cx - 6) if flip else (cx + 6):.2f}" y2="{ty + 3:.2f}" '
                f'stroke="{C_FAINT}" stroke-width="1"/>')
        anchor = ' text-anchor="end"' if flip else ""
        parts.append(
            f'<text class="wl-label" x="{(cx - 8) if flip else (cx + 8):.2f}" '
            f'y="{ty:.2f}"{anchor} fill="{label_color}" font-size="11.5">'
            f'{esc(p["l"])}</text>')

    if dropped:
        parts.append(
            f'<text class="wl-label-note" x="{PAD_L:.2f}" '
            f'y="{PAD_T + plot_h + 40:.2f}" fill="{C_MUTED}" font-size="11.5">'
            f'{len(labelled)} of {len(labelled) + dropped} labels shown</text>')

    # --- legend ------------------------------------------------------------
    if legend:
        lx, ly = PAD_L + plot_w, PAD_T - 12
        for name, color, kind in reversed(legend):
            # Long series names walked the legend off the left edge, to x=-668
            # with 8 of them, measured. Truncate each, then stop at the axis.
            if len(name) > 24:
                name = name[:23] + "…"
            entry_w = 7 * len(name) + 30
            if lx - entry_w < PAD_L:
                break
            text = esc(name)
            lx -= entry_w
            if kind == "line":
                parts.append(
                    f'<rect x="{lx:.2f}" y="{ly - 4:.2f}" width="16" '
                    f'height="2.5" fill="{color}"/>')
            else:
                parts.append(
                    f'<rect x="{lx + 5:.2f}" y="{ly - 7:.2f}" width="8" '
                    f'height="8" rx="4" fill="{color}"/>')
            parts.append(
                f'<text x="{lx + 22:.2f}" y="{ly:.2f}" fill="{C_MUTED}" '
                f'font-size="12">{text}</text>')

    return _figure(chart_id, title, parts)


def _figure(chart_id, title, parts):
    body = "\n".join(parts)
    return (
        f'<figure class="wl-chart" id="chart-{esc(chart_id)}">\n'
        f'<svg viewBox="0 0 {W} {H}" role="img" '
        f'preserveAspectRatio="xMidYMid meet" '
        f'style="width:100%;height:auto;display:block" '
        f'font-family="system-ui,sans-serif">\n'
        f'<title>{esc(title)}</title>\n{body}\n</svg>\n</figure>'
    )


# --------------------------------------------------------------------------
# Reading one task's charts off disk.
# --------------------------------------------------------------------------

def read_points(path):
    """Every parsable line of a JSONL point file.

    A torn last line is normal: the writer appends under O_APPEND while the
    server reads. Skip it and render the rest rather than blanking the chart.
    """
    points = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    p = json.loads(line)
                except ValueError:
                    continue
                if isinstance(p, dict):
                    points.append(p)
    except OSError:
        return []
    return points


def load_charts(task_dir):
    """(cfg, points) for every readable chart of one task, in display order.

    Order is the chart's `order` field, which the CLI sets from a counter at
    creation, then the id. A chart declared first stays first, however often
    its points change.
    """
    charts_dir = os.path.join(task_dir, "charts")
    try:
        # A dot-prefixed name is a half-written temp file from a killed CLI
        # process, never a chart: `worklog chart --remove` cannot delete one,
        # so rendering it would pin a phantom chart to the page for good.
        names = sorted(n for n in os.listdir(charts_dir)
                       if n.endswith(".json") and not n.startswith("."))
    except OSError:
        return []

    loaded = []
    for name in names:
        chart_id = name[:-len(".json")]
        try:
            with open(os.path.join(charts_dir, name), encoding="utf-8") as f:
                cfg = json.load(f)
        # Every exception, matching worklog_read_meta in server.py: one broken
        # chart file must never take the task page down.
        except Exception:
            continue
        if not isinstance(cfg, dict):
            continue
        cfg["id"] = chart_id      # the filename wins: it is what --remove takes
        order = num(cfg.get("order"))
        loaded.append((order if order is not None else 0.0, chart_id, cfg))

    loaded.sort(key=lambda t: (t[0], t[1]))
    out = []
    for _, chart_id, cfg in loaded:
        points = read_points(os.path.join(charts_dir, chart_id + ".jsonl"))
        out.append((cfg, points))
    return out


def render_panel(task_dir):
    """Every chart of one task, or "" when it has none."""
    charts = load_charts(task_dir)
    if not charts:
        return ""
    figures = []
    for cfg, points in charts:
        try:
            figures.append(render_chart(cfg, points))
        except Exception:
            # One chart that somehow still explodes costs its own figure, not
            # the page. Nothing above this catches, so nothing else would.
            continue
    if not figures:
        return ""
    return '<div class="wl-charts">\n' + "\n".join(figures) + "\n</div>"
