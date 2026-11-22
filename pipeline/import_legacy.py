#!/usr/bin/env python3
"""Import the 2 Nov 2026 first-pass corpus (site/tcg/data.js @ c4a75e8) as
(a) a metadata cache (title/channel/duration/published/views: public YouTube
metadata, no Reddit text) and (b) legacy vouch counts used only as a fallback
for games whose subreddits haven't been fully re-mined yet.

Reddit snippets in the old file are NOT carried over.
Output: data/legacy.json, seeds data/meta_cache.json
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, ROOT  # noqa: E402

REV = "c4a75e8"


def main():
    src = subprocess.check_output(["git", "-C", ROOT, "show", f"{REV}:site/tcg/data.js"]).decode()
    recs = json.loads(src[src.index("["):src.rindex("]") + 1])
    os.makedirs(DATA, exist_ok=True)
    legacy = [{"video_id": r["video_id"], "vouchers": r["vouchers"], "mentions": r["mentions"]} for r in recs]
    json.dump(legacy, open(os.path.join(DATA, "legacy.json"), "w"))
    cache_path = os.path.join(DATA, "meta_cache.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    for r in recs:
        cache.setdefault(r["video_id"], {"title": r["title"], "channel": r["channel"], "duration_s": r["duration_s"],
                                         "published": r["published"], "views": r["views"], "src": "yt-api-2026-11-02",
                                         "status": "ok"})
    json.dump(cache, open(cache_path, "w"))
    print(f"legacy: {len(legacy):,} videos -> data/legacy.json; meta cache now {len(cache):,}")


if __name__ == "__main__":
    main()
