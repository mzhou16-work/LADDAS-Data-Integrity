# LAADS Data Integration

Utilities to index, verify, download, compare, and visualize NASA LAADS DAAC products using daily metadata (“INFOR” CSVs). Includes integrity checks and daily-by-month coverage plots.

---

## Repository Structure

```
├── README.md
├── config.yaml                   # User config (infor_root, data_root, token, verify)
├── laddas_root.yaml              # Product → root URL mapping (per collection)
├── get_file_information.py       # Generate INFOR/<product>/<YYYY>/<YYYY-MM-DD>.csv
├── download_missing.py           # Download missing/corrupted files (wget + token; supports --output_dir)
├── compare_infor_vs_data.py      # Compare INFOR vs local files; list missing (with downloadsLink)
├── check_missing_overpasses.py   # Check missing HHMM granules per day (VIIRS 6-min / MODIS 5-min)
└── visualize_monthly_missing.py  # Daily bars arranged by month; highlight missing days
```

---

## 🔧 Installation

Create a minimal environment:

```bash
conda create -n laads python=3.10 pandas pyyaml matplotlib
conda activate laads
# or: pip install pandas pyyaml matplotlib
```

Python 3.7+ is supported; 3.10+ recommended.

---

## ⚙️ Configuration

### `config.yaml`

Defines global defaults so command lines stay simple:

```yaml
infor_root: "./INFOR"         # where per-day YYYY-MM-DD.csv metadata live
data_root: "/path/to/DATA"    # where product files are stored as <product>/<YYYY>/<DOY>/
token: "YOUR_EARTHDATA_TOKEN"
verify: "auto"                # 'auto' | 'md5' | 'size' | 'none'
```

- `token`: Create at https://urs.earthdata.nasa.gov  
  You can also set it via environment variable `NASA_EARTHDATA_TOKEN`.
- `verify` options:
  - `md5`: strict (slowest, most accurate)
  - `size`: fast size-only check
  - `auto`: use md5 if available, else size (default)
  - `none`: skip all integrity checks

🔒 **Security Tip:** Prefer setting `NASA_EARTHDATA_TOKEN` as an environment variable over storing in plain text.

---

## 🚀 Usage

### 1. Generate daily metadata (INFOR CSVs)

```bash
python get_file_information.py VJ103IMG --start 2020-07-01 --end 2020-07-10
```

Output:  
Creates `INFOR/VJ103IMG/2020/2020-07-01.csv` etc., each listing file `name`, `size`, `md5sum`, and `downloadsLink`.

---

### 2. Download missing or corrupted files

```bash
python download_missing.py VJ103IMG --start 2020-07-01 --end 2020-07-10 --verify auto
```

Optional: Download into a clean staging directory instead of overwriting DATA_ROOT:

```bash
python download_missing.py VJ103IMG --start 2020-07-01 --end 2020-07-10 --verify auto --output_dir ./STAGING
```

---

### 3. Compare INFOR vs data_root and list missing files

```bash
python compare_infor_vs_data.py VJ103IMG --start 2020-07-01 --end 2020-07-10
```

Outputs:
- Per-day CSVs in `missing/`
- Summary CSV in `missing_summary.csv`
- Missing files include full `downloadsLink`

Optional output directory:

```bash
python compare_infor_vs_data.py VJ103IMG --start 2020-07-01 --end 2020-07-10 --output_dir ./REPORTS
```

---

### 4. Check theoretical missing overpasses (based on HHMM)

```bash
python check_missing_overpasses.py VJ103IMG --start 2020-07-01 --end 2020-07-10
```

For VIIRS (6-min granules) → max 240/day  
For MODIS (5-min granules) → max 288/day

Customize data_root and output name:

```bash
python check_missing_overpasses.py VJ103IMG --start 2020-07-01 --end 2020-07-10 \
  --data_root /my/data/path --output my_viirs_report.csv
```

---

### 5. Visualize monthly missing bars

```bash
python visualize_monthly_missing.py --product VJ103IMG --start 2020-01-01 --end 2020-12-31
```

Generates a `VJ103IMG_2020_missing_coverage.png` plot:

- X-axis: days
- Y-axis: file counts
- Red bars = incomplete days
- 4x3 subplots (1 per month)

Optional output path:

```bash
python visualize_monthly_missing.py --product VJ103IMG --start 2020-01-01 --end 2020-12-31 --output_dir ./plots
```

---

## 📌 Notes

- You can safely rerun download/check scripts; integrity will be verified before re-download.
- INFOR CSVs are required for downloading and comparison.
- `missing/` folder stores per-day missing summaries.

---

## 📁 Example INFOR CSV (header)

```csv
name,size,md5sum,downloadsLink
VJ103IMG.A2020183.0000.001.nc,4052840,a7df3...,https://...
VJ103IMG.A2020183.0006.001.nc,4038291,b421c...,https://...
...
```

---

## 📬 Contact

Maintained by Meng Zhou (mzhou16@umbc.edu)

```

## License

MIT License

---

## Acknowledgments

- NASA LAADS DAAC for data access  
- Earthdata Login for authentication

