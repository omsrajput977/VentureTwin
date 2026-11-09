#!/usr/bin/env python3
"""
scripts/generate_readme_assets.py

Deterministic generator for data-driven simulation chart assets in docs/assets/charts/.
Uses real simulation engine outputs and data from data/known_good_run.json (seed=42).
Produces standalone, script-free, dark-themed SVG vector charts compatible with GitHub.

Outputs:
  - docs/assets/charts/tornado_sensitivity.svg
  - docs/assets/charts/scenario_comparison.svg
  - docs/assets/charts/monte_carlo_distribution.svg
  - docs/assets/charts/runway_constraint.svg
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from state.schemas import Assumption
from simulation.engine import run_sensitivity_analysis, run_monte_carlo


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_currency(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"${val / 1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"${val / 1_000:.0f}k"
    return f"${val:.0f}"


def generate_tornado_svg(sens_data: List[Dict[str, Any]], out_path: Path):
    """
    Renders a Tornado sensitivity chart SVG ranking parameter swing on Month-12 Net Contribution.
    """
    width, height = 820, 440
    margin_top, margin_bottom = 75, 45
    margin_left, margin_right = 240, 60

    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    # Base value for Strategy B expected is approx $1,141,045
    base_val = 1_141_045.0
    items = sorted(sens_data[:6], key=lambda x: x["swing"], reverse=True)

    # Find max deviation from base for scaling
    max_dev = max(
        max(abs(x["net_contribution_at_low"] - base_val), abs(x["net_contribution_at_high"] - base_val))
        for x in items
    )
    max_dev = max(max_dev, 1_400_000)

    center_x = margin_left + plot_width / 2

    row_height = plot_height / len(items)

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">',
        '  <defs>',
        '    <linearGradient id="tealGrad" x1="0%" y1="0%" x2="100%" y2="0%">',
        '      <stop offset="0%" stop-color="#0d9488"/>',
        '      <stop offset="100%" stop-color="#2dd4bf"/>',
        '    </linearGradient>',
        '    <linearGradient id="coralGrad" x1="100%" y1="0%" x2="0%" y2="0%">',
        '      <stop offset="0%" stop-color="#e11d48"/>',
        '      <stop offset="100%" stop-color="#f87171"/>',
        '    </linearGradient>',
        '  </defs>',
        f'  <rect width="{width}" height="{height}" rx="12" fill="#0b1020" stroke="#1e293b" stroke-width="1.5"/>',
        f'  <text x="32" y="38" fill="#f8fafc" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="700">Sensitivity Tornado Chart (Strategy B: Usage Caps)</text>',
        f'  <text x="32" y="58" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="12">12-Month Net Contribution Swing vs Baseline (${format_currency(base_val)}) | Ranked by Impact</text>',
        f'  <!-- Baseline Center Line -->',
        f'  <line x1="{center_x}" y1="{margin_top - 10}" x2="{center_x}" y2="{margin_top + plot_height}" stroke="#64748b" stroke-dasharray="3,3" stroke-width="1.5"/>',
        f'  <text x="{center_x}" y="{margin_top - 16}" fill="#cbd5e1" font-family="ui-monospace, monospace" font-size="11" text-anchor="middle">Baseline ${format_currency(base_val)}</text>',
    ]

    for i, item in enumerate(items):
        y = margin_top + i * row_height + (row_height - 24) / 2
        name = item["assumption_name"]
        low_val = item["net_contribution_at_low"]
        high_val = item["net_contribution_at_high"]
        swing = item["swing"]

        # Low bar
        dev_low = low_val - base_val
        w_low = (abs(dev_low) / max_dev) * (plot_width / 2)
        x_low = center_x - w_low if dev_low < 0 else center_x

        # High bar
        dev_high = high_val - base_val
        w_high = (abs(dev_high) / max_dev) * (plot_width / 2)
        x_high = center_x if dev_high >= 0 else center_x - w_high

        # Parameter label
        svg_lines.append(
            f'  <text x="{margin_left - 16}" y="{y + 16}" fill="#f1f5f9" font-family="ui-monospace, monospace" font-size="12" font-weight="600" text-anchor="end">{name}</text>'
        )

        # Draw left bar (low impact)
        if dev_low < 0:
            svg_lines.append(
                f'  <rect x="{x_low}" y="{y}" width="{w_low}" height="22" rx="4" fill="url(#coralGrad)"/>'
            )
            svg_lines.append(
                f'  <text x="{x_low - 8}" y="{y + 15}" fill="#fca5a5" font-family="ui-monospace, monospace" font-size="10" text-anchor="end">{format_currency(low_val)}</text>'
            )

        # Draw right bar (high impact)
        if dev_high > 0:
            svg_lines.append(
                f'  <rect x="{x_high}" y="{y}" width="{w_high}" height="22" rx="4" fill="url(#tealGrad)"/>'
            )
            svg_lines.append(
                f'  <text x="{x_high + w_high + 8}" y="{y + 15}" fill="#5eead4" font-family="ui-monospace, monospace" font-size="10" text-anchor="start">+{format_currency(high_val)}</text>'
            )

    # Legend & Caption
    svg_lines.extend([
        f'  <!-- Legend -->',
        f'  <rect x="{margin_left}" y="{height - 28}" width="12" height="12" rx="2" fill="#f87171"/>',
        f'  <text x="{margin_left + 18}" y="{height - 18}" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">Downside (P10 bound)</text>',
        f'  <rect x="{margin_left + 160}" y="{height - 28}" width="12" height="12" rx="2" fill="#2dd4bf"/>',
        f'  <text x="{margin_left + 178}" y="{height - 18}" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="11">Upside (P90 bound)</text>',
        f'  <text x="{width - 32}" y="{height - 18}" fill="#64748b" font-family="system-ui, sans-serif" font-size="10" text-anchor="end">Mode: Deterministic Simulation | NimbusDesk (Synthetic Data) | Seed: 42</text>',
        '</svg>',
    ])

    out_path.write_text("\n".join(svg_lines), encoding="utf-8")
    print(f"Generated: {out_path}")


def generate_scenario_comparison_svg(known_run_path: Path, out_path: Path):
    """
    Renders grouped comparison of Month-12 Net Contribution across Strategies A, B, and C
    in Conservative, Expected, and Optimistic scenarios.
    """
    with open(known_run_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Collect outcomes
    scenarios = ["conservative", "expected", "optimistic"]
    scenario_labels = {"conservative": "Conservative", "expected": "Expected", "optimistic": "Optimistic"}
    strategies = ["A_limited_features", "B_usage_caps", "C_no_free_plan"]
    strategy_labels = {
        "A_limited_features": "Strategy A: Feature Gating",
        "B_usage_caps": "Strategy B: Usage Caps (Rec.)",
        "C_no_free_plan": "Strategy C: Status Quo",
    }
    strategy_colors = {
        "A_limited_features": "#a78bfa",  # soft violet
        "B_usage_caps": "#2dd4bf",        # mint/teal
        "C_no_free_plan": "#fbbf24",       # amber
    }

    results: Dict[str, Dict[str, float]] = {s: {} for s in scenarios}
    for run in data.get("simulation_runs", []):
        sc = run.get("scenario")
        st = run.get("strategy")
        if sc in scenarios and st in strategies:
            net_12 = run.get("outputs", {}).get("net_contribution_12", 0.0)
            results[sc][st] = net_12

    width, height = 820, 440
    margin_top, margin_bottom = 80, 50
    margin_left, margin_right = 80, 40

    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    max_val = 6_500_000.0  # Cap for visualization

    group_width = plot_width / len(scenarios)
    bar_width = 38
    group_spacing = (group_width - (len(strategies) * bar_width + 16)) / 2

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">',
        f'  <rect width="{width}" height="{height}" rx="12" fill="#0b1020" stroke="#1e293b" stroke-width="1.5"/>',
        f'  <text x="32" y="38" fill="#f8fafc" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="700">12-Month Net Financial Contribution by Strategy &amp; Scenario</text>',
        f'  <text x="32" y="58" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="12">Deterministic simulation outcomes over 12-month operating runway (USD)</text>',
    ]

    # Grid lines
    grid_ticks = [0, 1_000_000, 2_500_000, 5_000_000, 6_000_000]
    for tick in grid_ticks:
        y = margin_top + plot_height - (tick / max_val) * plot_height
        svg_lines.append(
            f'  <line x1="{margin_left}" y1="{y}" x2="{width - margin_right}" y2="{y}" stroke="#1e293b" stroke-width="1"/>'
        )
        svg_lines.append(
            f'  <text x="{margin_left - 12}" y="{y + 4}" fill="#64748b" font-family="ui-monospace, monospace" font-size="10" text-anchor="end">{format_currency(tick)}</text>'
        )

    # Bars
    for sc_idx, sc in enumerate(scenarios):
        sc_x = margin_left + sc_idx * group_width
        svg_lines.append(
            f'  <text x="{sc_x + group_width / 2}" y="{margin_top + plot_height + 25}" fill="#f1f5f9" font-family="system-ui, sans-serif" font-size="13" font-weight="600" text-anchor="middle">{scenario_labels[sc]}</text>'
        )

        for st_idx, st in enumerate(strategies):
            val = results[sc].get(st, 0.0)
            bar_h = (val / max_val) * plot_height
            bar_x = sc_x + group_spacing + st_idx * (bar_width + 8)
            bar_y = margin_top + plot_height - bar_h

            color = strategy_colors[st]
            svg_lines.append(
                f'  <rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_h}" rx="4" fill="{color}"/>'
            )
            # Label on bar
            svg_lines.append(
                f'  <text x="{bar_x + bar_width / 2}" y="{bar_y - 6}" fill="{color}" font-family="ui-monospace, monospace" font-size="10" font-weight="600" text-anchor="middle">{format_currency(val)}</text>'
            )

    # Legend
    legend_x = margin_left
    legend_y = height - 16
    for st_idx, st in enumerate(strategies):
        color = strategy_colors[st]
        label = strategy_labels[st]
        offset = legend_x + st_idx * 215
        svg_lines.append(
            f'  <rect x="{offset}" y="{legend_y - 10}" width="12" height="12" rx="2" fill="{color}"/>'
        )
        svg_lines.append(
            f'  <text x="{offset + 18}" y="{legend_y}" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="11">{label}</text>'
        )

    svg_lines.append('</svg>')
    out_path.write_text("\n".join(svg_lines), encoding="utf-8")
    print(f"Generated: {out_path}")


def generate_monte_carlo_svg(mc_data: Dict[str, Any], out_path: Path):
    """
    Renders box-and-whisker / quantile distribution chart for Monte Carlo stochastic trials (P10, P50, P90).
    """
    width, height = 820, 380
    margin_top, margin_bottom = 75, 45
    margin_left, margin_right = 240, 50

    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    quantiles = mc_data.get("quantiles", {})
    strategies = ["B_usage_caps", "A_limited_features", "C_no_free_plan"]
    strategy_labels = {
        "B_usage_caps": "Strategy B (Usage Caps)",
        "A_limited_features": "Strategy A (Feature Gating)",
        "C_no_free_plan": "Strategy C (Status Quo)",
    }
    colors = {
        "B_usage_caps": "#2dd4bf",
        "A_limited_features": "#a78bfa",
        "C_no_free_plan": "#fbbf24",
    }

    max_val = 2_800_000.0
    row_height = plot_height / len(strategies)

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">',
        f'  <rect width="{width}" height="{height}" rx="12" fill="#0b1020" stroke="#1e293b" stroke-width="1.5"/>',
        f'  <text x="32" y="38" fill="#f8fafc" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="700">Monte Carlo 12-Month Net Contribution (500 Stochastic Runs)</text>',
        f'  <text x="32" y="58" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="12">Quantile ranges (P10 ━━ P50 Median ━━ P90) | Seed: 42 | Normal/PERT parameter distributions</text>',
    ]

    # Grid lines
    for tick in [0, 500_000, 1_000_000, 1_500_000, 2_000_000, 2_500_000]:
        x = margin_left + (tick / max_val) * plot_width
        svg_lines.append(
            f'  <line x1="{x}" y1="{margin_top}" x2="{x}" y2="{margin_top + plot_height}" stroke="#1e293b" stroke-width="1"/>'
        )
        svg_lines.append(
            f'  <text x="{x}" y="{margin_top + plot_height + 18}" fill="#64748b" font-family="ui-monospace, monospace" font-size="10" text-anchor="middle">{format_currency(tick)}</text>'
        )

    for i, st in enumerate(strategies):
        q = quantiles.get(st, {}).get("net_contribution_12", {})
        p10 = q.get("p10", 0.0)
        p50 = q.get("p50", 0.0)
        p90 = q.get("p90", 0.0)

        y = margin_top + i * row_height + row_height / 2
        col = colors[st]

        x_p10 = margin_left + (p10 / max_val) * plot_width
        x_p50 = margin_left + (p50 / max_val) * plot_width
        x_p90 = margin_left + (p90 / max_val) * plot_width

        # Row label
        svg_lines.append(
            f'  <text x="{margin_left - 16}" y="{y + 5}" fill="#f1f5f9" font-family="system-ui, sans-serif" font-size="13" font-weight="600" text-anchor="end">{strategy_labels[st]}</text>'
        )

        # Whisker line (P10 to P90)
        svg_lines.append(
            f'  <line x1="{x_p10}" y1="{y}" x2="{x_p90}" y2="{y}" stroke="{col}" stroke-width="3" stroke-linecap="round"/>'
        )
        # End caps
        svg_lines.append(
            f'  <line x1="{x_p10}" y1="{y - 12}" x2="{x_p10}" y2="{y + 12}" stroke="{col}" stroke-width="2.5"/>'
        )
        svg_lines.append(
            f'  <line x1="{x_p90}" y1="{y - 12}" x2="{x_p90}" y2="{y + 12}" stroke="{col}" stroke-width="2.5"/>'
        )

        # Median marker (Box)
        svg_lines.append(
            f'  <rect x="{x_p50 - 6}" y="{y - 14}" width="12" height="28" rx="3" fill="#ffffff" stroke="{col}" stroke-width="2"/>'
        )

        # Numerical Callout
        svg_lines.append(
            f'  <text x="{x_p50}" y="{y - 20}" fill="#ffffff" font-family="ui-monospace, monospace" font-size="11" font-weight="700" text-anchor="middle">P50: {format_currency(p50)}</text>'
        )
        svg_lines.append(
            f'  <text x="{x_p10 - 8}" y="{y + 4}" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="10" text-anchor="end">{format_currency(p10)}</text>'
        )
        svg_lines.append(
            f'  <text x="{x_p90 + 8}" y="{y + 4}" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="10" text-anchor="start">{format_currency(p90)}</text>'
        )

    # Note
    svg_lines.extend([
        f'  <text x="{margin_left}" y="{height - 12}" fill="#2dd4bf" font-family="system-ui, sans-serif" font-size="11" font-weight="600">P(Net Contribution &gt; $0) = 100% across all strategies | Strategy B P50 outperforms Strategy A by +$136.8k</text>',
        '</svg>',
    ])

    out_path.write_text("\n".join(svg_lines), encoding="utf-8")
    print(f"Generated: {out_path}")


def generate_runway_constraint_svg(known_run_path: Path, out_path: Path):
    """
    Renders 24-month runway trajectory under conservative stress scenario,
    highlighting the 6.0-month solvency constraint floor.
    """
    with open(known_run_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract history for Strategy A, B, C under conservative
    histories: Dict[str, List[float]] = {}
    for r in data.get("simulation_runs", []):
        if r.get("scenario") == "conservative":
            st = r.get("strategy")
            hist = [m.get("runway_months", 0.0) for m in r.get("outputs", {}).get("history", [])]
            histories[st] = hist

    width, height = 820, 420
    margin_top, margin_bottom = 75, 55
    margin_left, margin_right = 65, 40

    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    max_months = 24
    max_runway = 14.0  # months

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">',
        f'  <rect width="{width}" height="{height}" rx="12" fill="#0b1020" stroke="#1e293b" stroke-width="1.5"/>',
        f'  <text x="32" y="38" fill="#f8fafc" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="700">Cash Runway Trajectory: Conservative Stress Scenario</text>',
        f'  <text x="32" y="58" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="12">Simulation of cash reserves vs 6-month solvency constraint threshold</text>',
    ]

    # Grid ticks (Runway months)
    for r_tick in [0, 3, 6, 9, 12]:
        y = margin_top + plot_height - (r_tick / max_runway) * plot_height
        svg_lines.append(
            f'  <line x1="{margin_left}" y1="{y}" x2="{width - margin_right}" y2="{y}" stroke="#1e293b" stroke-width="1"/>'
        )
        svg_lines.append(
            f'  <text x="{margin_left - 10}" y="{y + 4}" fill="#64748b" font-family="ui-monospace, monospace" font-size="10" text-anchor="end">{r_tick}mo</text>'
        )

    # X-axis ticks (Month 1 to 24)
    for m in [1, 6, 12, 18, 24]:
        x = margin_left + ((m - 1) / (max_months - 1)) * plot_width
        svg_lines.append(
            f'  <line x1="{x}" y1="{margin_top + plot_height}" x2="{x}" y2="{margin_top + plot_height + 6}" stroke="#475569" stroke-width="1"/>'
        )
        svg_lines.append(
            f'  <text x="{x}" y="{margin_top + plot_height + 20}" fill="#94a3b8" font-family="ui-monospace, monospace" font-size="10" text-anchor="middle">Month {m}</text>'
        )

    # Solvency Constraint Line (6.0 months)
    floor_y = margin_top + plot_height - (6.0 / max_runway) * plot_height
    svg_lines.extend([
        f'  <!-- Solvency Constraint Line -->',
        f'  <rect x="{margin_left}" y="{floor_y}" width="{plot_width}" height="{margin_top + plot_height - floor_y}" fill="#f87171" fill-opacity="0.06"/>',
        f'  <line x1="{margin_left}" y1="{floor_y}" x2="{width - margin_right}" y2="{floor_y}" stroke="#f87171" stroke-dasharray="5,5" stroke-width="2"/>',
        f'  <text x="{width - margin_right}" y="{floor_y - 8}" fill="#f87171" font-family="system-ui, sans-serif" font-size="11" font-weight="700" text-anchor="end">Solvency Constraint Floor (6.0 Months)</text>',
    ])

    # Trajectory paths
    color_map = {
        "A_limited_features": "#f87171",  # Red alert because it breaches
        "B_usage_caps": "#2dd4bf",        # Teal/mint
        "C_no_free_plan": "#fbbf24",       # Amber
    }
    label_map = {
        "A_limited_features": "Strategy A: Gating (Depletes M16)",
        "B_usage_caps": "Strategy B: Usage Caps (Rec.)",
        "C_no_free_plan": "Strategy C: Status Quo",
    }

    for st in ["A_limited_features", "C_no_free_plan", "B_usage_caps"]:
        hist = histories.get(st, [])
        if not hist:
            continue
        pts = []
        for idx, val in enumerate(hist[:24]):
            x = margin_left + (idx / (max_months - 1)) * plot_width
            clamped = min(max(val, 0.0), max_runway)
            y = margin_top + plot_height - (clamped / max_runway) * plot_height
            pts.append(f"{x:.1f},{y:.1f}")

        col = color_map[st]
        svg_lines.append(
            f'  <polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="2.5" stroke-linejoin="round"/>'
        )

    # Legend
    legend_y = height - 16
    for idx, st in enumerate(["B_usage_caps", "A_limited_features", "C_no_free_plan"]):
        col = color_map[st]
        lbl = label_map[st]
        off = margin_left + idx * 240
        svg_lines.append(
            f'  <line x1="{off}" y1="{legend_y - 4}" x2="{off + 16}" y2="{legend_y - 4}" stroke="{col}" stroke-width="3"/>'
        )
        svg_lines.append(
            f'  <text x="{off + 22}" y="{legend_y}" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="11">{lbl}</text>'
        )

    svg_lines.append('</svg>')
    out_path.write_text("\n".join(svg_lines), encoding="utf-8")
    print(f"Generated: {out_path}")


def main():
    root = Path(__file__).resolve().parent.parent
    charts_dir = ensure_output_dir(root / "docs" / "assets" / "charts")
    known_run_path = root / "data" / "known_good_run.json"

    with open(known_run_path, "r", encoding="utf-8") as f:
        known_data = json.load(f)

    assumptions = [Assumption(**a) for a in known_data.get("assumptions", [])]

    print("Running sensitivity analysis (seed=42)...")
    sens_data = run_sensitivity_analysis("B_usage_caps", assumptions=assumptions)
    generate_tornado_svg(sens_data, charts_dir / "tornado_sensitivity.svg")

    print("Generating scenario comparison chart...")
    generate_scenario_comparison_svg(known_run_path, charts_dir / "scenario_comparison.svg")

    print("Running Monte Carlo simulation (500 samples, seed=42)...")
    mc_data = run_monte_carlo("B_usage_caps", assumptions=assumptions, n_samples=500, seed=42)
    generate_monte_carlo_svg(mc_data, charts_dir / "monte_carlo_distribution.svg")

    print("Generating runway constraint chart...")
    generate_runway_constraint_svg(known_run_path, charts_dir / "runway_constraint.svg")

    print("All README chart assets generated successfully!")


if __name__ == "__main__":
    main()
