#!/usr/bin/env python
# backend/scripts/download_geo_data.py
# Downloads GeoJSON files listed in config/geo_sources.yml into data/admin/.
# Idempotent: skips files that already exist.
#
# Usage (from backend/):
#   python scripts/download_geo_data.py

from __future__ import annotations

import sys
from pathlib import Path

import requests
import yaml

# Resolve paths relative to the backend/ directory
BACKEND_DIR = Path(__file__).resolve().parents[1]
CONFIG_FILE = BACKEND_DIR / "config" / "geo_sources.yml"
DATA_DIR = BACKEND_DIR / "data" / "admin"


def load_sources(config_file: Path) -> list[dict]:
    """Loads the list of GeoJSON sources from the YAML config.

    Args:
        config_file (Path): Path to geo_sources.yml.

    Returns:
        list[dict]: List of source definitions (dest, url, country, level).
    """
    with config_file.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("sources", [])


def download_file(url: str, dest: Path) -> None:
    """Downloads a file from a URL and writes it to disk.

    Args:
        url (str): Source URL.
        dest (Path): Destination file path.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)


def main() -> None:
    """Downloads all GeoJSON files listed in geo_sources.yml (idempotent)."""
    if not CONFIG_FILE.exists():
        print(f"[ERROR] Config file not found: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    sources = load_sources(CONFIG_FILE)
    if not sources:
        print("[WARN] No sources found in config.")
        return

    for source in sources:
        dest_rel = source["dest"]
        url = source["url"]
        dest_path = DATA_DIR / dest_rel

        if dest_path.exists():
            print(f"[SKIP] {dest_rel} already exists")
            continue

        print(f"[DOWN] {dest_rel} ← {url}")
        try:
            download_file(url, dest_path)
            size_kb = dest_path.stat().st_size // 1024
            print(f"[OK]   {dest_rel} ({size_kb} KB)")
        except Exception as exc:
            print(f"[ERROR] Failed to download {dest_rel}: {exc}", file=sys.stderr)
            sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
