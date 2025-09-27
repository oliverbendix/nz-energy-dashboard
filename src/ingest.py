#!/usr/bin/env python3
"""
Ingest NZ energy data and stage to S3.

- Downloads:
    * MBIE Electricity statistics (quarterly XLSX)
    * A handful of EMI Generation_MD monthly CSVs (plant-level)
- Saves to: data/raw/
- Uploads to: s3://<bucket>/raw/

Run:
  # with an AWS profile configured via `aws configure --profile nz-energy`
  AWS_PROFILE=nz-energy python src/ingest.py

Deps:
  pip install requests boto3
"""

import os
import re
import sys
import time
import pathlib
import mimetypes
from typing import List, Optional
from urllib.parse import urlsplit

import requests
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
# -----------------------
# Config
# -----------------------
load_dotenv()  # automatically loads .env into environment

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Data sources (update if they change upstream)
MBIE_ELECTRICITY_XLSX = (
    "https://www.mbie.govt.nz/assets/Data-Files/Energy/nz-energy-quarterly-and-energy-in-nz/electricity-june-2025-q2.xlsx"
)
EMI_GENERATION_MD_INDEX = (
    "https://www.emi.ea.govt.nz/Wholesale/Datasets/Generation/Generation_MD"
)



# AWS
S3_BUCKET = os.getenv("S3_BUCKET", "YOUR_S3_BUCKET_NAME_HERE")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
AWS_PROFILE = os.getenv("AWS_PROFILE")  # e.g. "nz-energy"

HEADERS = {
    "User-Agent": "nz-energy-dashboard/1.0 (learning project; contact: you@example.com)"
}


# -----------------------
# Helpers
# -----------------------
def _session_and_s3():
    """Create a boto3 session/client, preferring profile if provided."""
    try:
        if AWS_PROFILE:
            session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        else:
            session = boto3.Session(region_name=AWS_REGION)
        s3 = session.client("s3")
        return session, s3
    except Exception as e:
        print(f"⚠ Failed to create AWS session: {e}", file=sys.stderr)
        # Fallback to env/default
        return None, boto3.client("s3", region_name=AWS_REGION)


def ensure_bucket(s3, bucket: str, region: str) -> None:
    """Create bucket if it doesn't exist (no-op if it does)."""
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"✓ Using existing bucket: s3://{bucket}")
        return
    except ClientError as e:
        code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code == 404:
            print(f"→ Creating bucket s3://{bucket} in {region} ...")
            if region == "us-east-1":
                s3.create_bucket(Bucket=bucket)
            else:
                s3.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
            return
        # If forbidden or other error, surface it
        raise


def download_file(url: str, out_dir: pathlib.Path) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = os.path.basename(urlsplit(url).path) or "download"
    out_path = out_dir / name
    print(f"↓ Downloading {url} -> {out_path}")
    with requests.get(url, headers=HEADERS, timeout=90, stream=True) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 18):
                if chunk:
                    f.write(chunk)
    return out_path


def upload_to_s3(s3, local_path: pathlib.Path, key_prefix: str = "raw/") -> str:
    key = f"{key_prefix}{local_path.name}"
    ctype, _ = mimetypes.guess_type(local_path.name)
    extra = {"ContentType": ctype} if ctype else None
    print(f"⇪ Uploading {local_path} -> s3://{S3_BUCKET}/{key}")
    if extra:
        s3.upload_file(str(local_path), S3_BUCKET, key, ExtraArgs=extra)
    else:
        s3.upload_file(str(local_path), S3_BUCKET, key)
    return key


def parse_emi_links(html: str) -> List[str]:
    """
    Find EMI 'Generation_MD' monthly CSV links on the listing page.
    Expected patterns like: href="/Wholesale/Datasets/Generation/Generation_MD/201107_Generation_MD.csv"
    """
    pattern = re.compile(r'href="([^"]+?_Generation_MD\.csv)"', re.IGNORECASE)
    rels = pattern.findall(html)
    base = "https://www.emi.ea.govt.nz"
    abs_urls = []
    for r in rels:
        abs_urls.append(r if r.startswith("http") else base + r)
    # Keep unique order and take a small sample (latest tend to appear near the top)
    uniq = list(dict.fromkeys(abs_urls))
    return uniq[:5]


# -----------------------
# Ingestion tasks
# -----------------------
def ingest_mbie(s3):
    print("\n=== MBIE: Electricity statistics (quarterly XLSX) ===")
    try:
        p = download_file(MBIE_ELECTRICITY_XLSX, RAW_DIR)
        upload_to_s3(s3, p, key_prefix="raw/")
        print(f"✓ MBIE saved locally and uploaded: {p.name}")
    except Exception as e:
        print(f"✗ MBIE download/upload failed: {e}", file=sys.stderr)


def ingest_emi_generation_md(s3):
    print("\n=== EMI: Generation_MD (monthly CSVs, sample) ===")
    try:
        resp = requests.get(EMI_GENERATION_MD_INDEX, headers=HEADERS, timeout=90)
        resp.raise_for_status()
        links = parse_emi_links(resp.text)
        if not links:
            print("⚠ No CSV links found on EMI page (layout may have changed).")
            return
        for url in links:
            try:
                time.sleep(0.5)  # be polite
                p = download_file(url, RAW_DIR)
                upload_to_s3(s3, p, key_prefix="raw/")
                print(f"✓ EMI saved & uploaded: {p.name}")
            except Exception as e:
                print(f"  ⚠ Skipped {url}: {e}")
    except Exception as e:
        print(f"✗ EMI listing fetch failed: {e}", file=sys.stderr)


def main():
    # AWS init
    _, s3 = _session_and_s3()
    if not S3_BUCKET or "YOUR_S3_BUCKET_NAME_HERE" in S3_BUCKET:
        print("✗ Please set S3_BUCKET env var or edit S3_BUCKET in this script.", file=sys.stderr)
        sys.exit(1)

    # Ensure bucket exists (requires permission)
    try:
        ensure_bucket(s3, S3_BUCKET, AWS_REGION)
    except ClientError as e:
        print(f"✗ Cannot access/create bucket '{S3_BUCKET}': {e}", file=sys.stderr)
        sys.exit(2)

    # Ingest sources
    ingest_mbie(s3)
    ingest_emi_generation_md(s3)
    print("\nDone. Raw files are in data/raw/ (gitignored) and uploaded to S3 under 'raw/'.\n")


if __name__ == "__main__":
    main()
