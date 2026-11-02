#!/usr/bin/env python3
"""Fetch the HackerTube reference dataset (Karpathy's HN-vouched videos).

His site exposes the full enriched dataset at /api/list, 30 videos per call,
paged with ?offset=. This pulls everything and saves one JSON array.

Used as the schema blueprint for TCGTube's own enrichment format.
"""
import json
import os
import sys
import time
import urllib.request

BASE = "https://hackertube.org/api/list"
PAGE = 30


def fetch_page(offset: int, retries: int = 3, timeout: int = 30) -> list:
    url = f"{BASE}?offset={offset}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vouchtube/0.1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2)
    raise RuntimeError("unreachable")


def fetch_all(out_path: str) -> list:
    videos = {}
    offset = 0
    while True:
        batch = fetch_page(offset)
        if not batch:
            break
        for v in batch:
            videos[v["vid"]] = v
        offset += PAGE
        print(f"  offset {offset}: {len(videos)} unique videos", file=sys.stderr)
        if len(batch) < PAGE:
            break
        time.sleep(0.25)  # be polite
    data = sorted(videos.values(), key=lambda v: -(v.get("score") or 0))
    with open(out_path, "w") as f:
        json.dump(data, f)
    return data


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data/hackertube_full.json"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    data = fetch_all(out)
    print(f"saved {len(data)} videos -> {out} ({os.path.getsize(out) // 1024} KB)")
