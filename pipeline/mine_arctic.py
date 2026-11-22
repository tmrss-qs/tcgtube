#!/usr/bin/env python3
"""Mine YouTube vouches from the Arctic Shift API (no key needed).

Output: data/vouches_arctic/<sub>.jsonl (gitignored; contains authors for
unique-voucher counting; NEVER commit). Resumable: finished windows are
recorded in data/vouches_arctic/<sub>.done.

The API is shared and rate-limits under load ("Timeout. Maybe slow down a bit"),
so requests are paced, retried with backoff, and slow windows are split in half.

Usage: python3 pipeline/mine_arctic.py [--subs FAB,...] [--until 2026-11]
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, load_config, extract_ids  # noqa: E402

API = "https://arctic-shift.photon-reddit.com/api/comments/search"
QUERIES = os.environ.get("ARCTIC_QUERIES", "youtu.be,youtube").split(",")  # youtu.be first: most links per call
FIELDS = "id,author,created_utc,body,link_id,score,subreddit"
PACE = float(os.environ.get("ARCTIC_PACE", "6"))


def ts(y, m):
    return int(dt.datetime(y, m, 1, tzinfo=dt.timezone.utc).timestamp())


def months(start, until):
    y, m = map(int, start.split("-"))
    uy, um = map(int, until.split("-"))
    while (y, m) <= (uy, um):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


SPLIT = "split"


def get(params, log):
    """Rows, None (gave up) or SPLIT (server query timeout: window too big).
    The API has a ~10s query budget: a slow 'Timeout' means the window is too
    expensive (split it); a fast one means we're being throttled (back off)."""
    url = API + "?" + urllib.parse.urlencode(params)
    delay = PACE
    for attempt in range(int(os.environ.get("ARCTIC_ATTEMPTS", "5"))):
        time.sleep(delay if attempt else PACE)
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tcgtube-miner/0.2 (research, non-commercial)"})
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read().decode())
            if d.get("error"):
                raise RuntimeError(d["error"])
            return d.get("data") or []
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, TimeoutError, OSError, json.JSONDecodeError) as e:
            if time.time() - t0 > 7 and before_after_span(params) > 6 * 3600:
                return SPLIT
            delay = min(120, max(10, delay * 2))
            log(f"   retry {attempt+1} in {delay:.0f}s: {str(e)[:80]}")
    return None  # give up on this window (caller may split)


def before_after_span(params):
    return int(params["before"]) - int(params["after"])


def fetch_window(sub, q, after, before, log, depth=0):
    """All comments matching q in [after, before). Returns list or None."""
    out, cursor = [], after
    while True:
        rows = get({"subreddit": sub, "body": q, "limit": 100, "sort": "asc",
                    "after": cursor, "before": before, "fields": FIELDS}, log)
        if rows is SPLIT or rows is None:
            if depth < 7 and before - cursor > 6 * 3600:
                mid = (cursor + before) // 2
                log(f"   split window depth {depth+1}")
                a = fetch_window(sub, q, cursor, mid, log, depth + 1)
                b = fetch_window(sub, q, mid, before, log, depth + 1)
                if a is None or b is None:
                    return None
                return out + a + b
            return None
        out.extend(rows)
        if len(rows) < 100:
            return out
        last = max(int(r["created_utc"]) for r in rows)
        cursor = last if last > cursor else cursor + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subs", default="")
    ap.add_argument("--until", default=dt.date.today().strftime("%Y-%m"))
    ap.add_argument("--step", type=int, default=0, help="months per window (0 = config step or 1)")
    ap.add_argument("--outdir", default=os.path.join(ROOT, "data", "vouches_arctic"))
    ap.add_argument("--refresh-recent", type=int, default=0,
                    help="re-fetch windows starting in the last N months even if done (weekly refresh)")
    args = ap.parse_args()
    cfg = load_config()
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    want = set(filter(None, args.subs.split(",")))

    def log(msg):
        print(time.strftime("%H:%M:%S"), msg, flush=True)

    for s in cfg["subreddits"]:
        sub = s["name"]
        if want and sub not in want:
            continue
        done_path = os.path.join(outdir, f"{sub}.done")
        done = set(open(done_path).read().split()) if os.path.exists(done_path) else set()
        step = args.step or s.get("step", 1)
        ms = list(months(s["start"], args.until))
        log(f"== r/{sub}: {len(ms)} months, step {step}, {len(done)} windows done")
        with open(os.path.join(outdir, f"{sub}.jsonl"), "a") as out, open(done_path, "a") as dfh, \
                open(os.path.join(outdir, f"{sub}.failed"), "a") as ffh:
            for i in range(0, len(ms), step):
                y, m = ms[i]
                ly, lm = ms[min(i + step, len(ms)) - 1]
                ey, em = (ly + 1, 1) if lm == 12 else (ly, lm + 1)
                for q in QUERIES:
                    key = f"{y:04d}-{m:02d}:{step}:{q}"
                    recent = (dt.date.today().year * 12 + dt.date.today().month) - (y * 12 + m) < args.refresh_recent + step
                    if key in done and not (args.refresh_recent and recent):
                        continue
                    rows = fetch_window(sub, q, ts(y, m), ts(ey, em), log)
                    if rows is None:
                        log(f"   FAILED {key}")
                        ffh.write(key + "\n"); ffh.flush()
                        continue
                    n = 0
                    for r in rows:
                        body = r.get("body") or ""
                        for vid in extract_ids(body):
                            out.write(json.dumps({
                                "video_id": vid, "kind": "comment", "author": r.get("author") or "",
                                "created_utc": int(r.get("created_utc") or 0), "score": r.get("score") or 0,
                                "id": r.get("id"), "link_id": r.get("link_id") or "",
                                "subreddit": r.get("subreddit") or sub, "body": body[:1500],
                            }, ensure_ascii=False) + "\n")
                            n += 1
                    out.flush()
                    if ts(ey, em) < time.time() - 2 * 86400:  # only complete windows count as done
                        dfh.write(key + "\n"); dfh.flush()
                    log(f"   {sub} {key}: {len(rows)} comments -> {n} links")
    log("mining pass complete")


if __name__ == "__main__":
    main()
