#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare local data_root vs. INFOR CSVs and list missing files (with downloadsLink).

Usage (single consolidated CSV into an output directory):
  python compare_infor_vs_data.py VJ103IMG --start 2020-07-01 --end 2020-07-10 --output_dir ./REPORTS

Optional per-day CSVs (kept under output_dir/<product>/<YYYY>/):
  python compare_infor_vs_data.py VJ114IMG --start 2020-06-01 --end 2020-06-03 --output_dir ./REPORTS --per_day

Config:
  Expects config.yaml with at least:
    infor_root: "/path/to/INFOR"
    data_root:  "/path/to/DATA"
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import List
import argparse
import pandas as pd
import yaml
import sys

# ------------- helpers -------------
def load_config(path: str) -> dict:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with open(cfg_path, "r") as f:
        return yaml.safe_load(f) or {}

def date_to_doy(dt) -> int:
    return dt.timetuple().tm_yday

def _norm_cols(df: pd.DataFrame) -> dict:
    """Map lowercased column names to original for robust access."""
    return {c.lower(): c for c in df.columns}

def _required(df: pd.DataFrame, choices: List[str]) -> str:
    """
    Return the actual column name (original case) for one of the expected choices (case-insensitive).
    Raises if none found.
    """
    colmap = _norm_cols(df)
    for want in choices:
        if want.lower() in colmap:
            return colmap[want.lower()]
    raise KeyError(f"Missing required column; looked for one of: {choices}")

def missing_for_date(product: str, day: datetime.date, data_root: Path, infor_root: Path) -> pd.DataFrame:
    """
    For one date, read the INFOR CSV and compare to local files. Return a DataFrame of missing rows.
    """
    year = day.year
    doy = f"{date_to_doy(day):03d}"

    infor_csv = infor_root / product / f"{year:04d}" / f"{day:%Y-%m-%d}.csv"
    data_dir  = data_root  / product / f"{year:04d}" / doy

    if not infor_csv.exists():
        print(f" - INFOR CSV missing: {infor_csv}", file=sys.stderr)
        return pd.DataFrame(columns=["date","product","name","size","md5sum","downloadsLink","local_path"])

    try:
        df = pd.read_csv(infor_csv)
    except Exception as e:
        print(f" - Failed to read {infor_csv}: {e}", file=sys.stderr)
        return pd.DataFrame(columns=["date","product","name","size","md5sum","downloadsLink","local_path"])

    # Flexible column access
    name_col = _required(df, ["name"])
    size_col = _required(df, ["size"])
    md5_col  = _required(df, ["md5sum"])
    link_col = _required(df, ["downloadsLink", "downloadslink"])

    # Files present locally (exact filename match)
    present = set()
    if data_dir.exists():
        present = {p.name for p in data_dir.iterdir() if p.is_file()}
    # else: directory missing -> everything in CSV is considered missing

    # Rows where file is NOT present locally
    missing_mask = ~df[name_col].astype(str).isin(present)
    missing = df.loc[missing_mask, [name_col, size_col, md5_col, link_col]].copy()
    missing.rename(columns={
        name_col: "name",
        size_col: "size",
        md5_col:  "md5sum",
        link_col: "downloadsLink",
    }, inplace=True)

    # Add metadata columns
    missing.insert(0, "date", f"{day:%Y-%m-%d}")
    missing.insert(1, "product", product)
    missing["local_path"] = str(data_dir)

    return missing

# ------------- main -------------
def main():
    ap = argparse.ArgumentParser(description="Compare data_root vs. INFOR CSV; list missing files with downloadsLink.")
    ap.add_argument("product", help="Product short name (e.g., VJ103IMG)")
    ap.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: same as start)")
    ap.add_argument("--config", default="config.yaml", help="Path to YAML config (default: config.yaml)")
    ap.add_argument("--output", default=None, help="Output CSV filename (optional; if omitted, auto-name is used)")
    ap.add_argument("--output_dir", default=None, help="Directory to write outputs (keeps repo root clean)")
    ap.add_argument("--per_day", action="store_true", help="Also write per-day missing CSVs under output_dir/<product>/<YYYY>/")
    args = ap.parse_args()

    cfg = load_config(args.config)
    infor_root = Path(cfg.get("infor_root", "./INFOR"))
    data_root  = Path(cfg.get("data_root", "./DATA"))

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end   = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else start

    # Prepare output directory
    out_dir = Path(args.output_dir) if args.output_dir else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Default consolidated output name
    if args.output:
        out_csv = out_dir / args.output
    else:
        base = f"{args.product}_{start:%Y-%m-%d}" + (f"_{end:%Y-%m-%d}" if end != start else "")
        out_csv = out_dir / f"{base}_missing_urls.csv"

    # Loop dates and accumulate
    day = start
    frames = []
    while day <= end:
        miss = missing_for_date(args.product, day, data_root, infor_root)
        if args.per_day:
            # per-day CSV under output_dir/<product>/<YYYY>/
            per_day_dir = out_dir / args.product / f"{day.year:04d}"
            per_day_dir.mkdir(parents=True, exist_ok=True)
            per_day_csv = per_day_dir / f"{args.product}_{day:%Y-%m-%d}_missing_urls.csv"
            (miss if not miss.empty else pd.DataFrame(
                columns=["date","product","name","size","md5sum","downloadsLink","local_path"])
            ).to_csv(per_day_csv, index=False)
        if not miss.empty:
            frames.append(miss)
        day += timedelta(days=1)

    # Consolidated CSV
    if frames:
        result = pd.concat(frames, ignore_index=True)
    else:
        result = pd.DataFrame(columns=["date","product","name","size","md5sum","downloadsLink","local_path"])
    result.to_csv(out_csv, index=False)

    # Summary
    total_missing = len(result)
    print(f" - Wrote consolidated report to: {out_csv}")
    print(f"Total missing entries: {total_missing}")
    if total_missing > 0:
        by_date = result.groupby("date")["name"].count().sort_index()
        print("Missing counts by date:")
        for d, n in by_date.items():
            print(f"  {d}: {n}")
    if args.per_day:
        print(f"Per-day CSVs written under: {out_dir / args.product}")

if __name__ == "__main__":
    main()
