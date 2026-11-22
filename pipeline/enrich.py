#!/usr/bin/env python3
"""Fetch public YouTube metadata for candidate videos into data/meta_cache.json.

- YOUTUBE_API_KEY set  -> YouTube Data API videos.list (title, channel, handle-less
  channelId, duration, published, views, category). 1 quota unit / 50 ids.
- no key               -> YouTube oEmbed (no key): title + channel + channel URL
  only. Duration/publish date stay unknown (shown as "—"; Shorts can only be
  caught by /shorts/ links). Dead/private videos 401/404 -> status 'dead'.

The mini's personal OAuth script is no longer used.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from common import DATA

API = "https://www.googleapis.com/youtube/v3/videos"
OEMBED = "https://www.youtube.com/oembed"


def iso8601_to_s(d):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return None
    return int(m[1] or 0) * 86400 + int(m[2] or 0) * 3600 + int(m[3] or 0) * 60 + int(m[4] or 0)


def load_cache():
    p = os.path.join(DATA, "meta_cache.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def save_cache(cache):
    p = os.path.join(DATA, "meta_cache.json")
    tmp = p + ".tmp"
    json.dump(cache, open(tmp, "w"))
    os.replace(tmp, p)


def via_api(ids, key, cache):
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        q = urllib.parse.urlencode({"part": "snippet,contentDetails,statistics,status", "id": ",".join(batch), "key": key})
        with urllib.request.urlopen(API + "?" + q, timeout=30) as r:
            items = {it["id"]: it for it in json.loads(r.read().decode()).get("items", [])}
        for vid in batch:
            it = items.get(vid)
            if not it or it["status"].get("privacyStatus") != "public":
                cache[vid] = {"status": "dead", "src": "yt-api"}
                continue
            cache[vid] = {"title": it["snippet"]["title"], "channel": it["snippet"]["channelTitle"],
                          "channel_id": it["snippet"].get("channelId"),
                          "duration_s": iso8601_to_s(it["contentDetails"].get("duration")),
                          "published": it["snippet"]["publishedAt"][:10],
                          "views": int(it["statistics"].get("viewCount", 0)),
                          "category": it["snippet"].get("categoryId"), "src": "yt-api", "status": "ok"}
        time.sleep(0.2)


def via_oembed(ids, cache, log=print):
    for n, vid in enumerate(ids):
        url = OEMBED + "?" + urllib.parse.urlencode({"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=20) as r:
                    d = json.loads(r.read().decode())
                cache[vid] = {"title": d.get("title", ""), "channel": d.get("author_name", ""),
                              "channel_url": d.get("author_url", ""), "duration_s": None, "published": None,
                              "views": None, "src": "oembed", "status": "ok"}
                break
            except urllib.error.HTTPError as e:
                if e.code in (400, 401, 403, 404):
                    cache[vid] = {"status": "dead", "src": "oembed"}
                    break
                time.sleep(3 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(3 * (attempt + 1))
        if n % 200 == 0:
            log(f"  oembed {n:,}/{len(ids):,}")
            save_cache(cache)
        time.sleep(0.15)


def enrich(ids, log=print):
    cache = load_cache()
    key = os.environ.get("YOUTUBE_API_KEY")
    todo = [v for v in ids if v not in cache or (key and cache[v].get("src") == "oembed")]
    if todo:
        log(f"enrich: {len(todo):,} videos via {'YouTube Data API' if key else 'oEmbed (no key: no durations/dates)'}")
        (via_api(todo, key, cache) if key else via_oembed(todo, cache, log))
        save_cache(cache)
    return cache


if __name__ == "__main__":
    import sys
    enrich(sys.argv[1:])
