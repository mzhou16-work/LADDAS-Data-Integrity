#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# py download_missing.py VJ114IMG --start 2020-01-01 --end 2020-12-31

from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
import subprocess
import hashlib
import pandas as pd
import numpy as np
import os
import time
import copy
import argparse
import yaml

# -----------------------------
# Config
# -----------------------------

# Load path configuration
with open("config.yaml", "r") as f:
    SETTING = yaml.safe_load(f)

INFOR_ROOT = SETTING['infor_root']  # where YYYY-MM-DD.csv lives
DATA_ROOT  = SETTING['data_root']
token      = SETTING['token']

# Prefer pulling token from env var; fall back to the constant token if not set.
TOKEN = os.getenv("NASA_EARTHDATA_TOKEN") or (token)

# -----------------------------
# Helpers
# -----------------------------

def date_to_doy(dt):
    return dt.timetuple().tm_yday

def md5sum(filename: str, blocksize: int = 65536) -> str:
    md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(blocksize), b""):
            md5.update(chunk)
    return md5.hexdigest()

def _run_wget(url: str, dest: Path, token: str, wait_s: float = 1.0) -> int:
    """Run wget with Authorization header; return exit code."""
    cmd = [
        "wget",
        "--no-check-certificate",
        "-e", "robots=off",
        "-m", "-np",
        "-R", ".html,.tmp",
        "-nH",
        "--cut-dirs=3",
        url,
        "--header", f"Authorization: Bearer {token}",
        "-O", str(dest)
    ]
    print("Running:", " ".join(cmd))
    rc = subprocess.run(cmd).returncode
    time.sleep(wait_s)
    return rc

def _is_nan(x) -> bool:
    try:
        # pandas may give np.nan or NaN-like strings
        return pd.isna(x) or (isinstance(x, str) and x.strip().lower() in ("nan", "none", ""))
    except Exception:
        return False

def _file_ok(path: Path,
             expected_size: Optional[int],
             expected_md5: Optional[str],
             verify: str = "auto") -> bool:
    """
    verify: 'auto' | 'md5' | 'size' | 'none'
    """
    if not path.exists():
        return False

    if verify == "none":
        return True

    if verify == "md5":
        if expected_md5 and not _is_nan(expected_md5):
            try:
                return md5sum(str(path)) == str(expected_md5).strip()
            except Exception:
                return False
        # If no md5 available in metadata, fail back to size if present
        verify = "size"

    if verify == "auto":
        if expected_md5 and not _is_nan(expected_md5):
            try:
                return md5sum(str(path)) == str(expected_md5).strip()
            except Exception:
                return False
        # else fall through to size

    if verify == "size":
        if expected_size is not None and not _is_nan(expected_size):
            try:
                return path.stat().st_size == int(expected_size)
            except Exception:
                return False
        # If size unavailable, last resort: accept existence
        return True

    # Unknown mode → be conservative
    return False
    

def _download_with_retries(url: str, dest: Path, token: str,
                           expected_size: Optional[int],
                           expected_md5: Optional[str],
                           prefer_md5: bool = True,
                           retries: int = 2) -> bool:
    """Download a file with retries; verify after each attempt."""
    for attempt in range(retries + 1):
        rc = _run_wget(url, dest, token)
        if rc == 0 and _file_ok(dest, expected_size, expected_md5, verify=verify):
            return True
        print(f" - Integrity check failed (attempt {attempt+1}/{retries+1}); retrying...")
    return False

# -----------------------------
# Core
# -----------------------------
def download_product_file(product: str,
                          start_date: str,
                          end_date: str,
                          infor_root: str,
                          data_root: str,
                          token: str,
                          verify: str = "auto") -> List[Path]:
    """
    Download missing/corrupted files between start_date and end_date (inclusive).

    Parameters
    ----------
    product : str
    start_date : 'YYYY-MM-DD'
    end_date : 'YYYY-MM-DD' or None (uses start_date)
    infor_root : path to INFOR/<product>/<year>/YYYY-MM-DD.csv
    data_root  : path to save data under <product>/<YYYY>/<DOY>/
    token      : Bearer token string (or set NASA_EARTHDATA_TOKEN env)
    verify     : 'auto' | 'md5' | 'size' | 'none'

    Returns: List[Path] of files that are present and passed checks (or skipped if verify='none')
    """
    token = token or os.getenv("NASA_EARTHDATA_TOKEN")
    if not token:
        raise RuntimeError("No NASA EARTHDATA token provided. Set NASA_EARTHDATA_TOKEN or pass token=...")

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else start
    if end < start:
        raise ValueError("end_date must be after or equal to start_date")

    results: List[Path] = []
    dt = start

    while dt <= end:
        year, doy = dt.year, date_to_doy(dt)
        infor_file = Path(infor_root) / product / f"{year:04d}" / f"{dt:%Y-%m-%d}.csv"
        data_dir   = Path(data_root)  / product / f"{year:04d}" / f"{doy:03d}"
        data_dir.mkdir(parents=True, exist_ok=True)

        if not infor_file.exists():
            print(f" - INFOR CSV missing for {dt}: {infor_file}")
            dt += timedelta(days=1); continue

        try:
            df = pd.read_csv(infor_file)
        except Exception as e:
            print(f" - Failed to read INFOR CSV {infor_file}: {e}")
            dt += timedelta(days=1); continue

        cols = {c.lower(): c for c in df.columns}
        name_col = cols.get("name","name")
        size_col = cols.get("size","size")
        md5_col  = cols.get("md5sum","md5sum")
        link_col = cols.get("downloadslink","downloadsLink")

        if not all(c in df.columns for c in [name_col, size_col, md5_col, link_col]):
            print(f" - INFOR CSV missing required columns in {infor_file}")
            dt += timedelta(days=1); continue
        print(f' - Checking date {dt} for {len(os.listdir(data_dir))}/{df.shape[0]} files...')
        
        for _, row in df.iterrows():
            fname = str(row[name_col])
            url   = str(row[link_col]).strip()

            expected_size = None
            try:
                expected_size = int(row[size_col]) if not _is_nan(row[size_col]) else None
            except Exception:
                expected_size = None

            expected_md5 = None if _is_nan(row[md5_col]) else str(row[md5_col]).strip()

            dest = data_dir / fname
            if _file_ok(dest, expected_size, expected_md5, verify=verify):
                results.append(dest)
                continue

            print(f" - Missing or bad file for {dt}: {fname}")
            success = _download_with_retries(url, dest, token, expected_size, expected_md5, verify=verify)
            if success:
                results.append(dest)
            else:
                print(f" - Failed after retries: {fname}")

        dt += timedelta(days=1)

    return results

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Download missing NASA LAADS files")
	parser.add_argument("product", help="Product short name (e.g., VJ103IMG)")
	parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
	parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: same as start)")
	parser.add_argument("--verify", choices=["auto","md5","size","none"], default="size",
						help="Integrity check method")
						
	args = parser.parse_args()
	# Single day (set end_date = start_date for single-day)
	files = download_product_file(args.product, 
								  start_date=args.start, 
								  end_date=args.end,
								  infor_root=INFOR_ROOT,
								  data_root=DATA_ROOT,
								  token=TOKEN,
								  verify=args.verify)
	print("Done. Files present:", len(files))
