#!/usr/bin/env python3
"""Enrich candidate videos with YouTube Data API metadata.

Input:  data/candidates.json (from aggregate.py — uses qualified candidates)
Output: data/enriched.json — candidates merged with YouTube metadata,
        with dead videos and Shorts (<60s) removed.

Auth: reuses the mini's existing Google OAuth via ~/.hermes/scripts/yt_token.py.
videos.list costs 1 quota unit per 50-ID call; ~370 calls for 18k videos is
trivial against the 10k/day default quota.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
YT_TOKEN = "/Users/tomross/.hermes/scripts/yt_token.py"
API = "https://www.googleapis.com/youtube/v3/videos"
MIN_DURATION_S = 60  # Shorts die here
BATCH = 50


def get_token():
    return subprocess.check_output(["python3", YT_TOKEN]).decode().strip()


def call(token, ids):
    q = urllib.parse.urlencode({"part": "snippet,contentDetails,statistics,status",
                                "id": ",".join(ids), "maxResults": 50})
    req = urllib.request.Request(API + "?" + q,
                                 headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def iso8601_to_s(d):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    return int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0)


def main():
    with open(os.path.join(DATA, "candidates.json")) as fh:
        cands = [c for c in json.load(fh) if c["qualifies"]]
    print(f"enriching {len(cands):,} qualified candidates", flush=True)

    token = get_token()
    enriched, dead, shorts, private = [], 0, 0, 0
    by_id = {c["video_id"]: c for c in cands}
    ids = [c["video_id"] for c in cands]

    for i in range(0, len(ids), BATCH):
        batch = ids[i:i + BATCH]
        res = None
        for attempt in range(3):
            try:
                res = call(token, batch)
                break
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 0:
                    token = get_token()
                    continue
                if e.code in (403, 429) and attempt < 2:
                    time.sleep(30 * (attempt + 1))
                    continue
                raise
        if res is None:
            raise RuntimeError(f"API failed for batch at {i} after retries")
        found = {it["id"]: it for it in res.get("items", [])}
        dead += len(batch) - len(found)
        for vid, it in found.items():
            secs = iso8601_to_s(it["contentDetails"].get("duration"))
            privacy = it["status"].get("privacyStatus", "public")
            if secs < MIN_DURATION_S:
                shorts += 1
                continue
            if privacy != "public":
                private += 1
                continue
            c = by_id[vid]
            enriched.append({
                "video_id": vid,
                "title": it["snippet"]["title"],
                "channel": it["snippet"]["channelTitle"],
                "published": it["snippet"]["publishedAt"][:10],
                "duration_s": secs,
                "views": int(it["statistics"].get("viewCount", 0)),
                "category": it["snippet"].get("categoryId", ""),
                "vouchers": c["vouchers"],
                "mentions": c["mentions"],
                "subreddits": c["subreddits"],
                "first_seen": c["first_seen"],
                "last_seen": c["last_seen"],
                "why": c["why"],
            })
        if i % (BATCH * 10) == 0:
            print(f"  {i:,}/{len(ids):,} processed | {len(enriched):,} enriched | "
                  f"{dead:,} dead | {shorts:,} shorts | {private:,} private", flush=True)
        time.sleep(0.35)

    enriched.sort(key=lambda r: (-r["vouchers"], -r["mentions"]))
    out = os.path.join(DATA, "enriched.json")
    with open(out, "w") as fh:
        json.dump(enriched, fh)
    print(f"\ndone: {len(enriched):,} enriched -> {out}")
    print(f"dropped: {dead:,} dead/unavailable, {shorts:,} shorts (<{MIN_DURATION_S}s), {private:,} not public")
    print("\ntop 10 after enrichment:")
    for r in enriched[:10]:
        print(f"  {r['vouchers']:>4} vouchers | {r['channel'][:20]:<20} | {r['title'][:60]}")


if __name__ == "__main__":
    main()
