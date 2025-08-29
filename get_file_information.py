#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# py get_file_information.py VNP14IMG --start 2020-01-17 --end 2020-01-17

from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
import subprocess
import yaml
import argparse


# -----------------------------
# Config
# -----------------------------
INFOR_ROOT = './INFOR'  # where YYYY-MM-DD.csv lives

def date_to_doy(dt):
    return dt.timetuple().tm_yday

# Load config
with open("laddas_root.yaml", "r") as f:
    CFG = yaml.safe_load(f)["products"]

# Load path configuration
with open("config.yaml", "r") as f:
    SETTING = yaml.safe_load(f)

def download_product_file(
    product: str,
    start_date: str,
    end_date: Optional[str] = None,
    outdir: str = SETTING['infor_root'],
    skip_existing: bool = True
    ) -> List[Path]:
    """
    Download product CSV(s) between start_date and end_date (inclusive).
    Dates: 'YYYY-MM-DD'. If end_date is None, only start_date is used.
    Returns list of local Paths.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else start
    if end < start:
        raise ValueError("end_date must be after or equal to start_date")

    results: List[Path] = []
    dt = start
    root = CFG[product]  # e.g., https://.../allData/5200/VNP14IMG/

    while dt <= end:
        year, doy = dt.year, date_to_doy(dt)
        url = f"{root}{year}/{doy:03d}.csv"

        local_dir = Path(outdir) / product / str(year)
        local_dir.mkdir(parents=True, exist_ok=True)
        local_file = local_dir / f"{dt:%Y-%m-%d}.csv"

        if skip_existing and local_file.exists():
            print(f" - Exists, skipping: {local_file}")
            results.append(local_file)
        else:
            cmd = ["wget", "--wait=1", "--execute", "robots=off", "-O", str(local_file), url]
            print("Running:", " ".join(cmd))
            try:
                subprocess.run(cmd, check=True)
                results.append(local_file)
            except subprocess.CalledProcessError:
                print(f" - Failed to download {product} for {dt}")

        dt += timedelta(days=1)

    return results

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
	# files = download_product_file("VJ114IMG", "2020-01-01")                   # single day
	parser = argparse.ArgumentParser(description="Download missing NASA LAADS files")
	parser.add_argument("product", help="Product short name (e.g., VJ103IMG)")
	parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
	parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: same as start)")
	
						
	args = parser.parse_args()
	files = download_product_file(args.product, 
								  start_date=args.start, 
								  end_date=args.end,)       # range
	
	print("Done. Files present:", len(files))










