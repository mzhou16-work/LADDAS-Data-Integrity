#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import csv
import argparse
from typing import Optional, List
from datetime import datetime, timedelta
from pathlib import Path

# Default data root (can be overridden with --data_root)
DATA_ROOT = "/Dedicated/jwang-data2/shared_satData/OPNL_FILDA/DATA/LEV1B"

# Products and their expected overpass intervals (minutes)
PRODUCTS_INFO = {
    "VNP14IMG": {"interval": 6},  # VIIRS fire product
    "VJ114IMG": {"interval": 6},
    "VJ214IMG": {"interval": 6},
    "VNP03IMG": {"interval": 6},  # VIIRS geolocation product
    "VJ103IMG": {"interval": 6},
    "MOD14":    {"interval": 5},  # MODIS fire product
    "MYD14":    {"interval": 5},
    "MOD03":    {"interval": 5},  # MODIS geolocation product
    "MYD03":    {"interval": 5},
}

def generate_expected_times(interval_minutes: int) -> List[str]:
    return [f"{h:02d}{m:02d}" for h in range(24) for m in range(0, 60, interval_minutes)]

def get_doy(dt) -> int:
    return dt.timetuple().tm_yday

def list_times_for_date(product: str, date, data_root: Path) -> List[str]:
    year = date.year
    doy = f"{get_doy(date):03d}"
    path = Path(data_root) / product / f"{year}" / doy
    if not path.exists():
        return []

    filenames = os.listdir(path)
    # Match: <PRODUCT>.AYYYYDOY.HHMM.*.<ext> for common HDF/NetCDF endings
    pattern = re.compile(
        rf"{re.escape(product)}\.A{year}{doy}\.(\d{{4}})\..*\.(nc|hdf|hdf5|h4|h5)$",
        re.IGNORECASE,
    )
    times = []
    for f in filenames:
        m = pattern.match(f)
        if m:
            times.append(m.group(1))
    return sorted(set(times))

def check_files(product: str, start_date: str, end_date: Optional[str], data_root: Path) -> List[dict]:
    results: List[dict] = []
    interval = PRODUCTS_INFO[product]["interval"]
    expected_times = generate_expected_times(interval)

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date or start_date, "%Y-%m-%d").date()
    delta = timedelta(days=1)

    d = start
    while d <= end:
        present_times = list_times_for_date(product, d, data_root)
        missing_times = sorted(set(expected_times) - set(present_times))
        results.append({
            "date": d.strftime("%Y-%m-%d"),
            "product": product,
            "interval_min": interval,
            "num_files": len(present_times),
            "num_missing": len(missing_times),
            "missing_overpasses": " ".join(missing_times),
        })
        d += delta

    return results

def save_to_csv(rows: List[dict], output_file: Path) -> None:
    if not rows:
        print("No data to save.")
        return
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f" - Report saved to {output_file}")

# -----------------------------------
# CLI
# -----------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check missing overpasses for LAADS products")
    parser.add_argument("product", help="Product short name (e.g., VJ103IMG)")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: same as start)")
    parser.add_argument("--data_root", default=DATA_ROOT, help="Base directory where files are stored")
    parser.add_argument("--output", default=None, help="Output CSV file name (optional)")
    parser.add_argument("--output_dir", default=None, help="Directory to place the report (keeps root clean)")
    args = parser.parse_args()

    if args.product not in PRODUCTS_INFO:
        print(f" - Unknown product: {args.product}")
        print("Available products:", ", ".join(PRODUCTS_INFO.keys()))
        raise SystemExit(1)

    data_root = Path(args.data_root)
    out_dir = Path(args.output_dir) if args.output_dir else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine output file name/path
    if args.output:
        output_file = out_dir / args.output
    else:
        base = f"{args.product}_{args.start}" + (f"_{args.end}" if args.end else "")
        output_file = out_dir / f"{base}_missing.csv"

    results = check_files(args.product, args.start, args.end, data_root)
    save_to_csv(results, output_file)
