#!/usr/bin/env python3
"""Generate SVG charts for SEO reports — health score gauge, category radar, CWV bars."""

from __future__ import annotations

import math
from typing import Any


COLORS = {
    "red": "#e74c3c",
    "orange": "#f39c12",
    "yellow": "#f1c40f",
    "green": "#27ae60",
    "blue": "#3498db",
    "grey": "#bdc3c7",
    "dark": "#2c3e50",
    "light_grey": "#ecf0f1",
    "white": "#ffffff",
}

CWV_THRESHOLDS = {
    "lcp": {"good": 2.5, "poor": 4.0, "unit": "s", "label": "LCP"},
    "inp": {"good": 200, "poor": 500, "unit": "ms", "label": "INP"},
    "cls": {"good": 0.1, "poor": 0.25, "unit": "", "label": "CLS"},
}

SEVERITY_COLORS = {
    "critical": "#e74c3c",
    "high": "#f39c12",
    "medium": "#f1c40f",
    "low": "#3498db",
}


def _score_color(score: int) -> str:
    if score >= 80:
        return COLORS["green"]
    if score >= 50:
        return COLORS["orange"]
    return COLORS["red"]


def _cwv_color(value: float, metric: str) -> str:
    t = CWV_THRESHOLDS[metric]
    if value <= t["good"]:
        return COLORS["green"]
    if value <= t["poor"]:
        return COLORS["orange"]
    return COLORS["red"]


def health_score_gauge(score: int) -> str:
    """Semi-circular gauge chart showing health score 0–100."""
    score = max(0, min(100, score))
    w, h = 400, 260
    cx, cy = 200, 220
    r = 160
    stroke_w = 28

    bg_arc = _arc_path(cx, cy, r, 180, 360)
    frac = score / 100.0
    end_angle = 180 + frac * 180
    fg_arc = _arc_path(cx, cy, r, 180, end_angle)
    color = _score_color(score)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" font-family="system-ui, sans-serif">\n'
        f'  <path d="{bg_arc}" fill="none" stroke="{COLORS["light_grey"]}" '
        f'stroke-width="{stroke_w}" stroke-linecap="round"/>\n'
        f'  <path d="{fg_arc}" fill="none" stroke="{color}" '
        f'stroke-width="{stroke_w}" stroke-linecap="round"/>\n'
        f'  <text x="{cx}" y="{cy - 30}" text-anchor="middle" '
        f'font-size="64" font-weight="700" fill="{color}">{score}</text>\n'
        f'  <text x="{cx}" y="{cy}" text-anchor="middle" '
        f'font-size="16" fill="{COLORS["dark"]}">/ 100</text>\n'
        f'  <text x="{cx}" y="{cy + 28}" text-anchor="middle" '
        f'font-size="14" fill="{COLORS["dark"]}">SEO Health Score</text>\n'
        f"</svg>"
    )


def _arc_path(cx: float, cy: float, r: float, start_deg: float, end_deg: float) -> str:
    """SVG arc path for a semi-circle segment (angles in degrees, 0 = right)."""
    start_rad = math.radians(start_deg)
    end_rad = math.radians(end_deg)
    x1 = cx + r * math.cos(start_rad)
    y1 = cy + r * math.sin(start_rad)
    x2 = cx + r * math.cos(end_rad)
    y2 = cy + r * math.sin(end_rad)
    large = 1 if (end_deg - start_deg) > 180 else 0
    return f"M {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f}"


def category_radar(categories: dict[str, float]) -> str:
    """Radar/spider chart showing scores across audit categories.

    Args:
        categories: mapping of category name → score (0–100).
    """
    w, h = 400, 400
    cx, cy = 200, 200
    r = 150
    n = len(categories)
    if n < 3:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400"><text x="200" y="200" text-anchor="middle">Need 3+ categories</text></svg>'

    names = list(categories.keys())
    values = [max(0, min(100, categories[k])) for k in names]
    angle_step = 2 * math.pi / n

    def _point(index: int, pct: float) -> tuple[float, float]:
        angle = -math.pi / 2 + index * angle_step
        x = cx + r * pct * math.cos(angle)
        y = cy + r * pct * math.sin(angle)
        return x, y

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" font-family="system-ui, sans-serif">',
    ]

    for ring in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{_point(i, ring)[0]:.1f},{_point(i, ring)[1]:.1f}" for i in range(n))
        lines.append(
            f'  <polygon points="{pts}" fill="none" stroke="{COLORS["light_grey"]}" stroke-width="1"/>'
        )

    for i in range(n):
        x, y = _point(i, 1.0)
        lines.append(f'  <line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{COLORS["light_grey"]}" stroke-width="1"/>')

    data_pts = " ".join(f"{_point(i, v / 100)[0]:.1f},{_point(i, v / 100)[1]:.1f}" for i, v in enumerate(values))
    lines.append(
        f'  <polygon points="{data_pts}" fill="{COLORS["blue"]}" fill-opacity="0.25" '
        f'stroke="{COLORS["blue"]}" stroke-width="2"/>'
    )

    for i, v in enumerate(values):
        px, py = _point(i, v / 100)
        lines.append(f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{COLORS["blue"]}"/>')

    for i, name in enumerate(names):
        lx, ly = _point(i, 1.18)
        anchor = "middle"
        if lx < cx - 10:
            anchor = "end"
        elif lx > cx + 10:
            anchor = "start"
        label = name if len(name) <= 14 else name[:12] + "…"
        lines.append(
            f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="11" fill="{COLORS["dark"]}">{label}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def cwv_bars(lcp: float, inp: float, cls: float) -> str:
    """Horizontal bar chart with CWV metrics color-coded by thresholds."""
    w, h = 400, 200
    bar_h = 36
    gap = 20
    label_w = 60
    max_bar_w = w - label_w - 40
    y_start = 30

    metrics = [
        ("lcp", lcp, CWV_THRESHOLDS["lcp"]),
        ("inp", inp, CWV_THRESHOLDS["inp"]),
        ("cls", cls, CWV_THRESHOLDS["cls"]),
    ]

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" font-family="system-ui, sans-serif">',
        f'  <text x="{w / 2}" y="18" text-anchor="middle" font-size="14" '
        f'font-weight="600" fill="{COLORS["dark"]}">Core Web Vitals</text>',
    ]

    for idx, (key, value, thresh) in enumerate(metrics):
        y = y_start + idx * (bar_h + gap)
        color = _cwv_color(value, key)

        max_val = thresh["poor"] * 1.5 if thresh["poor"] > 0 else 1.0
        bar_w = min(max_bar_w, max(20, (value / max_val) * max_bar_w))

        lines.append(
            f'  <rect x="{label_w}" y="{y}" width="{max_bar_w}" height="{bar_h}" '
            f'rx="4" fill="{COLORS["light_grey"]}"/>'
        )

        good_w = (thresh["good"] / max_val) * max_bar_w
        poor_w = (thresh["poor"] / max_val) * max_bar_w
        lines.append(
            f'  <line x1="{label_w + good_w:.1f}" y1="{y}" '
            f'x2="{label_w + good_w:.1f}" y2="{y + bar_h}" '
            f'stroke="{COLORS["green"]}" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.5"/>'
        )
        lines.append(
            f'  <line x1="{label_w + poor_w:.1f}" y1="{y}" '
            f'x2="{label_w + poor_w:.1f}" y2="{y + bar_h}" '
            f'stroke="{COLORS["red"]}" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.5"/>'
        )

        lines.append(
            f'  <rect x="{label_w}" y="{y}" width="{bar_w:.1f}" height="{bar_h}" '
            f'rx="4" fill="{color}"/>'
        )

        lines.append(
            f'  <text x="{label_w - 8}" y="{y + bar_h / 2 + 5}" '
            f'text-anchor="end" font-size="13" font-weight="600" '
            f'fill="{COLORS["dark"]}">{thresh["label"]}</text>'
        )

        display = f'{value}{thresh["unit"]}'
        text_x = label_w + bar_w + 8
        if text_x + 40 > w:
            text_x = label_w + bar_w - 8
            t_anchor = "end"
            t_fill = COLORS["white"]
        else:
            t_anchor = "start"
            t_fill = COLORS["dark"]
        lines.append(
            f'  <text x="{text_x:.1f}" y="{y + bar_h / 2 + 5}" '
            f'text-anchor="{t_anchor}" font-size="13" font-weight="600" '
            f'fill="{t_fill}">{display}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def severity_donut(critical: int, high: int, medium: int, low: int) -> str:
    """Donut chart showing finding distribution by severity."""
    total = critical + high + medium + low
    w, h = 400, 300
    cx, cy = 160, 150
    r = 100
    inner_r = 60

    if total == 0:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" font-family="system-ui, sans-serif">'
            f'<text x="{cx}" y="{cy}" text-anchor="middle" font-size="14" '
            f'fill="{COLORS["dark"]}">No findings</text></svg>'
        )

    segments = [
        ("Critical", critical, SEVERITY_COLORS["critical"]),
        ("High", high, SEVERITY_COLORS["high"]),
        ("Medium", medium, SEVERITY_COLORS["medium"]),
        ("Low", low, SEVERITY_COLORS["low"]),
    ]

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" font-family="system-ui, sans-serif">',
    ]

    angle = -90.0
    for label, count, color in segments:
        if count == 0:
            continue
        sweep = (count / total) * 360
        lines.append(_donut_segment(cx, cy, r, inner_r, angle, sweep, color))
        angle += sweep

    lines.append(
        f'  <text x="{cx}" y="{cy - 6}" text-anchor="middle" '
        f'font-size="32" font-weight="700" fill="{COLORS["dark"]}">{total}</text>'
    )
    lines.append(
        f'  <text x="{cx}" y="{cy + 16}" text-anchor="middle" '
        f'font-size="12" fill="{COLORS["dark"]}">findings</text>'
    )

    legend_x = cx + r + 40
    legend_y = cy - 50
    for label, count, color in segments:
        if count == 0:
            continue
        lines.append(
            f'  <rect x="{legend_x}" y="{legend_y - 10}" width="14" height="14" rx="2" fill="{color}"/>'
        )
        lines.append(
            f'  <text x="{legend_x + 20}" y="{legend_y + 2}" font-size="13" '
            f'fill="{COLORS["dark"]}">{label}: {count}</text>'
        )
        legend_y += 26

    lines.append("</svg>")
    return "\n".join(lines)


def _donut_segment(cx: float, cy: float, outer_r: float, inner_r: float,
                   start_deg: float, sweep_deg: float, color: str) -> str:
    """SVG path for one donut segment."""
    if sweep_deg >= 359.99:
        sweep_deg = 359.99

    s_rad = math.radians(start_deg)
    e_rad = math.radians(start_deg + sweep_deg)
    large = 1 if sweep_deg > 180 else 0

    ox1 = cx + outer_r * math.cos(s_rad)
    oy1 = cy + outer_r * math.sin(s_rad)
    ox2 = cx + outer_r * math.cos(e_rad)
    oy2 = cy + outer_r * math.sin(e_rad)
    ix1 = cx + inner_r * math.cos(e_rad)
    iy1 = cy + inner_r * math.sin(e_rad)
    ix2 = cx + inner_r * math.cos(s_rad)
    iy2 = cy + inner_r * math.sin(s_rad)

    d = (
        f"M {ox1:.1f} {oy1:.1f} "
        f"A {outer_r} {outer_r} 0 {large} 1 {ox2:.1f} {oy2:.1f} "
        f"L {ix1:.1f} {iy1:.1f} "
        f"A {inner_r} {inner_r} 0 {large} 0 {ix2:.1f} {iy2:.1f} Z"
    )
    return f'  <path d="{d}" fill="{color}"/>'
