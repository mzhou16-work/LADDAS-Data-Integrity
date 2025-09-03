import os
import re
import csv
import argparse
from datetime import datetime, timedelta
from pathlib import Path

DATA_ROOT = "/Dedicated/jwang-data2/shared_satData/OPNL_FILDA/DATA/LEV1B"

# Define the products and their expected overpass intervals (in minutes)
PRODUCTS_INFO = {
    "VNP14IMG": {"interval": 6},  # VIIRS fire product
    "VJ114IMG": {"interval": 6},  # 
    "VJ214IMG": {"interval": 6},  #
    "VNP03IMG": {"interval": 6},  # VIIRS geolocation product
    "VJ103IMG": {"interval": 6},  # 
    "VJ103IMG": {"interval": 6},  #    
    "MOD14": {"interval": 5},  # MODIS fire product
    "MYD14": {"interval": 5},  #
    "MOD03": {"interval": 5},  # MODIS geolocation product
    "MYD03": {"interval": 5}   #  
}

OUTPUT_CSV = "missing_file_report.csv"


def generate_expected_times(interval_minutes):
    return [f"{h:02d}{m:02d}" for h in range(24) for m in range(0, 60, interval_minutes)]

def get_doy(dt):
    return dt.timetuple().tm_yday

def list_times_for_date(product, date):
    year = date.year
    doy = f"{get_doy(date):03d}"
    path = Path(DATA_ROOT) / product / f"{year}" / doy
    if not path.exists():
        return []

    filenames = os.listdir(path)
    pattern = re.compile(rf"{product}\.A{year}{doy}\.(\d{{4}})\..*\.(nc|hdf|hdf5|h4|h5)$", re.IGNORECASE)
    times = []
    for f in filenames:
        match = pattern.match(f)
        if match:
            times.append(match.group(1))
    return sorted(set(times))

def check_files(product, start_date, end_date):
    results = []
    interval = PRODUCTS_INFO[product]["interval"]
    expected_times = generate_expected_times(interval)

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date or start_date, "%Y-%m-%d").date()
    delta = timedelta(days=1)

    while start <= end:
        present_times = list_times_for_date(product, start)
        missing_times = sorted(set(expected_times) - set(present_times))

        results.append({
            "date": start.strftime("%Y-%m-%d"),
            "product": product,
            "interval_min": interval,
            "num_files": len(present_times),
            "num_missing": len(missing_times),
            "missing_overpasses": " ".join(missing_times)
        })
        start += delta

    return results

def save_to_csv(rows, output_file):
    if not rows:
        print("No data to save.")
        return

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

    args = parser.parse_args()

    if args.product not in PRODUCTS_INFO:
        print(f" - Unknown product: {args.product}")
        print("Available products:", ", ".join(PRODUCTS_INFO.keys()))
        exit(1)

    DATA_ROOT = args.data_root  # override if passed

    # Determine output file name if not explicitly provided
    if args.output:
        output_file = args.output
    else:
        if args.end:
            output_file = f"{args.product}_{args.start}_{args.end}_missing.csv"
        else:
            output_file = f"{args.product}_{args.start}_missing.csv"

    results = check_files(args.product, args.start, args.end)
    save_to_csv(results, output_file)
