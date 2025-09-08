#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Daily-vs-Month visualization of missing data.

- Compares INFOR (practical expected per day) vs files on disk (actual present),
  and shows the theoretical max (VIIRS 240/day, MODIS 288/day) as an upper bound.
- Outputs a daily CSV and a figure arranged as monthly subplots (e.g., 4x3 for 12 months).

Example:
  python visualize_daily_by_month.py VJ103IMG --start 2020-01-01 --end 2020-12-31 \
      --config config.yaml --output_dir ./REPORTS

Outputs (in output_dir):
  - <PRODUCT>_<START>_<END>_daily_counts.csv
  - <PRODUCT>_<START>_<END>_daily_by_month.png
"""

import os
import re
import math
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import yaml
import pandas as pd
import matplotlib.pyplot as plt

import math
from matplotlib import patches as mpatches
from matplotlib.lines import Line2D



# ---------- cadence (minutes between granules) ----------
# Extend as needed
PRODUCTS_INFO: Dict[str, int] = {
    # VIIRS (6-min cadence => 240/day)
    "VNP14IMG": 6,
    "VJ114IMG": 6,
    "VJ214IMG": 6,
    "VNP03IMG": 6,
    "VJ103IMG": 6,
    # MODIS (5-min cadence => 288/day)
    "MOD14": 5,
    "MYD14": 5,
    "MOD03": 5,
    "MYD03": 5,
}

ALLOWED_EXT = ("nc", "hdf", "hdf5", "h4", "h5")


# ---------------- helpers ----------------
def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r") as f:
        return yaml.safe_load(f) or {}


def date_to_doy(d) -> int:
    return d.timetuple().tm_yday


def theoretical_max(product: str) -> int:
    if product not in PRODUCTS_INFO:
        raise ValueError(f"Unknown product '{product}'. Add its cadence to PRODUCTS_INFO.")
    minutes = PRODUCTS_INFO[product]
    return (24 * 60) // minutes  # 240 for VIIRS, 288 for MODIS


def expected_from_infor(infor_csv: Path) -> int:
    """INFOR rows = practical expected count for that day."""

    if not infor_csv.exists():
        return 0
    try:
        df = pd.read_csv(infor_csv)
        return int(df.shape[0])
    except Exception:
        return 0


def present_from_disk(product: str, d, data_root: Path) -> int:
    """
    Count unique HHMM times present on disk for product/day.
    Matches: <PRODUCT>.AYYYYDDD.HHMM.*.<ext>
    """
    year = d.year
    doy = f"{date_to_doy(d):03d}"
    day_dir = data_root / product / f"{year:04d}" / doy
    if not day_dir.exists():
        return 0

    pat = re.compile(
        rf"{re.escape(product)}\.A{year}{doy}\.(\d{{4}})\..*\.({'|'.join(ALLOWED_EXT)})$",
        re.IGNORECASE,
    )
    hhmm = set()
    for name in os.listdir(day_dir):
        m = pat.match(name)
        if m:
            hhmm.add(m.group(1))
    return len(hhmm)


def iter_days(start_str: str, end_str: Optional[str]):
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime((end_str or start_str), "%Y-%m-%d").date()
    d = start
    one = timedelta(days=1)
    while d <= end:
        yield d
        d += one


# --------------- core ----------------
def build_daily_table(product: str, start: str, end: Optional[str], infor_root: Path, data_root: Path) -> pd.DataFrame:
    rows = []
    theo = theoretical_max(product)

    for d in iter_days(start, end):
        year = d.year
        infor_csv = infor_root / product / f"{year:04d}" / f"{d:%Y-%m-%d}.csv"
        infor_cnt = expected_from_infor(infor_csv)
        present_cnt = present_from_disk(product, d, data_root)

        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "yyyy_mm": f"{d:%Y-%m}",
            "day": d.day,
            "product": product,
            "theory": theo,
            "infor": infor_cnt,
            "present": present_cnt,
            "missing_vs_theory": max(theo - present_cnt, 0),
            "missing_vs_infor":  max(infor_cnt - present_cnt, 0),
        })

    df = pd.DataFrame(rows)
    return df


def plot_daily_by_month(df: pd.DataFrame, product: str, out_png: Path, highlight_basis: str = "infor"):
    """
    Create subplots organized by month. Each subplot shows one month's daily series:
      - bars: present (actual) — colored red if missing (present < basis)
      - step/line: infor (practical expected)
      - line: theory (upper bound; constant)
    highlight_basis: 'infor' (default) or 'theory'
    """
    if df.empty:
        print("No data to plot.")
        return

    df = df.sort_values(["yyyy_mm", "day"])
    months = sorted(df["yyyy_mm"].unique().tolist())
    n = len(months)

    # Grid: 3 columns; rows as needed (e.g., 4x3 for 12 months)
    cols = 3
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 6, rows * 3.5), squeeze=False)

    legend_infor_handle = None
    legend_theory_handle = None

    for idx, month in enumerate(months):
        r = idx // cols
        c = idx % cols
        ax = axes[r][c]

        sub = df[df["yyyy_mm"] == month].copy()
        x = sub["day"].to_numpy()
        present = sub["present"].to_numpy()
        infor = sub["infor"].to_numpy()
        theory = sub["theory"].to_numpy()

        # Choose basis for "missing" highlight
        if highlight_basis == "theory":
            basis = theory
        else:
            basis = infor

        # Color bars red where present < basis, else blue
        missing_mask = present < basis
        bar_colors = ["red" if m else "tab:blue" for m in missing_mask]

        # Bars: present (no label here; we add custom legend patches later)
        ax.bar(x, present, color=bar_colors, label="_nolegend_", alpha=0.9)

        # INFOR (step)
        step_lines = ax.step(x, infor, where="mid", linewidth=1.5, label="INFOR expected")
        if legend_infor_handle is None:
            legend_infor_handle = step_lines[0]

        # Theory (line)
        theory_line = ax.plot(x, theory, linewidth=1.2, label="Theory max")[0]
        if legend_theory_handle is None:
            legend_theory_handle = theory_line

        ax.set_title(f"{product} — {month}")
        ax.set_xlabel("Day")
        ax.set_ylabel("# granules")
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.set_xticks(x)

    # Hide any unused subplots
    total_axes = rows * cols
    for j in range(n, total_axes):
        r = j // cols
        c = j % cols
        axes[r][c].axis("off")

    # Build a single legend for all subplots
    present_ok = mpatches.Patch(color="tab:blue", label="Present (OK)")
    present_missing = mpatches.Patch(color="red", label=f"Present (missing vs {highlight_basis})")
    handles = [present_ok, present_missing]
    if legend_infor_handle is not None:
        handles.append(legend_infor_handle)
    if legend_theory_handle is not None:
        handles.append(legend_theory_handle)

    fig.legend(handles, [h.get_label() if hasattr(h, "get_label") else h.get_text() for h in handles],
               loc="upper center", ncol=4)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    print(f" - Plot saved to {out_png}")



# --------------- CLI ----------------
def main():
    ap = argparse.ArgumentParser(description="Visualize daily coverage by month (INFOR vs Disk vs Theory).")
    ap.add_argument("product", help="Product short name (e.g., VJ103IMG, MOD14)")
    ap.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: same as start)")
    ap.add_argument("--config", default="config.yaml", help="YAML with infor_root and data_root")
    ap.add_argument("--infor_root", default=None, help="Override INFOR root dir")
    ap.add_argument("--data_root", default=None, help="Override DATA root dir")
    ap.add_argument("--output_dir", default="./REPORTS", help="Where to write CSV/PNG (default: ./REPORTS)")
    ap.add_argument("--highlight_basis", choices=["infor", "theory"], default="infor",
                help="Color days red when present < basis (default: infor)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    infor_root = Path(args.infor_root or cfg.get("infor_root", "./INFOR"))
    data_root  = Path(args.data_root  or cfg.get("data_root",  "./DATA"))
    out_dir    = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.product not in PRODUCTS_INFO:
        raise SystemExit(f"Unknown product '{args.product}'. Available: {', '.join(PRODUCTS_INFO.keys())}")

    # Build daily table (by day)
    daily = build_daily_table(args.product, args.start, args.end, infor_root, data_root)

    # Save daily CSV
    csv_name = f"{args.product}_{args.start}" + (f"_{args.end}" if args.end else "") + "_daily_counts.csv"
    out_csv = out_dir / csv_name
    daily.to_csv(out_csv, index=False)
    print(f" - Daily counts CSV written to {out_csv}")

    # Plot subplots arranged by month
    png_name = f"{args.product}_{args.start}" + (f"_{args.end}" if args.end else "") + "_daily_by_month.png"
    out_png = out_dir / png_name
    plot_daily_by_month(daily, args.product, out_png, highlight_basis=args.highlight_basis)


if __name__ == "__main__":
    main()
