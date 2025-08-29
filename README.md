# LAADS File Downloader

This package automates downloading missing or corrupted files from **NASA LAADS DAAC**, using daily metadata files ('INFOR' CSVs) and integrity checks ('md5sum' or 'size'). It supports single-day and date-range downloads, with configuration via YAML.

---

## Repository Structure

```
├── config.yaml             # User configuration (token, data directories, verify mode)
├── laddas_root.yaml        # Root URLs for products (per collection/product mapping)
├── download_missing.py     # Main downloader script (uses INFOR CSV + wget)
├── get_file_information.py # Script to query LAADS and generate INFOR CSV metadata
└── README.md               # This file
```

---

## Installation

Create a minimal environment:

'''bash
conda create -n laads python=3.10 pandas pyyaml
conda activate laads
# optional: pip install requests
'''

You can also use `pip install pandas pyyaml` in an existing environment.

---

## Configuration

### `config.yaml`

Defines global defaults so command lines can stay simple:

```yaml
infor_root: "./INFOR"      # where YYYY-MM-DD.csv metadata lives
data_root: "/path/to/DATA" # where product files will be downloaded
token: "YOUR_EARTHDATA_TOKEN"
verify: "auto"             # 'auto' | 'md5' | 'size' | 'none'
```

#### `token`

- NASA Earthdata Bearer token (create at [https://urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov))
- Can also be set via environment variable `NASA_EARTHDATA_TOKEN`

#### `verify` (integrity check mode)

- `md5` → strict check with MD5 hash (**slowest, most accurate**)
- `size` → fast check using file size only (**less strict**)
- `auto` → use MD5 if available, else size (**default**)
- `none` → skip integrity checks

> **Security tip**: Prefer using the `NASA_EARTHDATA_TOKEN` environment variable over storing tokens in plain text.

---

### `laddas_root.yaml`

Defines product → root URL mapping (per collection). Example:

'''yaml
products:
  VNP14IMG: "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5000/VNP14IMG/"
  VJ103IMG: "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VJ103IMG/"
'''

---

## Usage

### 1. Generate daily metadata (INFOR CSVs)

Create per-day CSV inventories (file names, sizes, md5, download links):

```bash
python get_file_information.py VJ103IMG --start 2020-07-01 --end 2020-07-10
```

This will create files like:

```
INFOR/VJ103IMG/2020/2020-07-01.csv
INFOR/VJ103IMG/2020/2020-07-02.csv
...
```

Each CSV includes columns such as:

```
name, last_modified, size, mtime, cksum, md5sum, resourceType, downloadsLink
```

---

### 2. Download missing or corrupted files

The downloader reads each day’s INFOR CSV, checks your local files, and fetches any missing/bad ones:

```bash
python download_missing.py VJ103IMG --start 2020-07-01 --end 2020-07-10
```

Files are saved by **year/DOY** under `data_root`, for example:

'''
/path/to/DATA/VJ103IMG/2020/183/   # for 2020-07-01 (DOY=183)
/path/to/DATA/VJ103IMG/2020/184/   # for 2020-07-02
'''

Override integrity checking mode at the CLI if desired:

'''bash
# Fast, size-only check
python download_missing.py VJ103IMG --start 2020-07-01 --end 2020-07-10 --verify size

# Strict MD5 verification
python download_missing.py VJ103IMG --start 2020-07-01 --end 2020-07-10 --verify md5
'''

---

## Command-Line Options

Typical arguments supported by the scripts:

'''
get_file_information.py  PRODUCT  --start YYYY-MM-DD  [--end YYYY-MM-DD]  [--config config.yaml]

download_missing.py      PRODUCT  --start YYYY-MM-DD  [--end YYYY-MM-DD]
                         [--config config.yaml]
                         [--verify auto|md5|size|none]
                         [--infor_root PATH] [--data_root PATH]
                         [--token TOKEN]
'''

**Precedence (lowest → highest):** 'config.yaml' < environment variables < command-line flags

---

## Example Workflow

'''bash
# Step 1: fetch metadata (INFOR CSVs)
python get_file_information.py VNP14IMG --start 2020-01-01 --end 2020-01-05

# Step 2: download missing files (size check only for speed)
python download_missing.py VNP14IMG --start 2020-01-01 --end 2020-01-05 --verify size
'''

---

## License

MIT License (or add your preferred license)

---

## Acknowledgments

- NASA LAADS DAAC for data access  
- Earthdata Login for authentication
