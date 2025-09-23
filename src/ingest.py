#!/usr/bin/env python3
"""
Ingest NZ energy data into data/raw/
- Downloads MBIE Electricity Statistics (quarterly XLSX)
- (Optional) Grabs a few EMI Generation_MD monthly CSVs

Run:
  python src/ingest.py
"""

import os
import re
import sys
import time
import pathlib
from typing import List
from urllib.parse import urlsplit
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---- Data sources ----
MBIE_ELECTRICITY_XLSX = "https://www.mbie.govt.nz/assets/Data-Files/Energy/nz-energy-quarterly-and-energy-in-nz/electricity-june-2025-q2.xlsx"  # Data tables for electricity (quarterly)
EMI_GENERATION_MD_INDEX = "https://www.emi.ea.govt.nz/Wholesale/Datasets/Generation/Generation_MD"  # Page lists monthly CSVs

HEADERS = {
    "User-Agent": "nz-energy-dashboard/1.0 (+https://github.com/yourname/nz-energy-dashboard)"
}

def download_file(url: str, out_dir: pathlib.Path) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = os.path.basename(urlsplit(url).path) or "download"
    out_path = out_dir / name
    print(f"→ Downloading {url} -> {out_path}")
    with requests.get(url, headers=HEADERS, timeout=60, stream=True) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    return out_path

def ingest_mbie_electricity():
    print("\n=== MBIE: Electricity statistics (quarterly tables) ===")
    try:
        p = download_file(MBIE_ELECTRICITY_XLSX, RAW_DIR)
        print(f"✓ Saved: {p}")
    except Exception as e:
        print(f"✗ MBIE download failed: {e}", file=sys.stderr)

def parse_emi_links(html: str) -> List[str]:
    # Find file names like 201107_Generation_MD.csv
    pattern = re.compile(r'href="([^"]+?_Generation_MD\.csv)"')
    rels = pattern.findall(html)
    # Make absolute
    abs_urls = []
    base = "https://www.emi.ea.govt.nz"
    for r in rels:
        abs_urls.append(r if r.startswith("http") else base + r)
    # De-duplicate and keep a handful (latest on the page are higher years)
    uniq = list(dict.fromkeys(abs_urls))
    return uniq[:5]  # grab a few samples to keep it light

def ingest_emi_generation_md():
    print("\n=== EMI: Generation_MD (monthly generation by trading period) ===")
    try:
        resp = requests.get(EMI_GENERATION_MD_INDEX, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        links = parse_emi_links(resp.text)
        if not links:
            print("No CSV links found on EMI page.")
            return
        for url in links:
            try:
                time.sleep(0.5)  # be polite
                p = download_file(url, RAW_DIR)
                print(f"✓ Saved: {p.name}")
            except Exception as e:
                print(f"  ⚠ Skipped {url}: {e}")
    except Exception as e:
        print(f"✗ EMI listing fetch failed: {e}", file=sys.stderr)

def main():
    ingest_mbie_electricity()
    ingest_emi_generation_md()
    print("\nDone.")

if __name__ == "__main__":
    main()
