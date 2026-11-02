#!/usr/bin/env python3
"""Aggregate raw vouches into candidate videos with trust-weighted scores.

Input:  data/vouches/*.jsonl (from mine.py)
Output: data/candidates.json + printed summary

Rules:
- A video's score = unique voucherers (distinct authors), not raw mentions.
- Self-promo discount: if one author is >60% of a video's mentions, count them
  once and drop their duplicates (a creator plugging their own video isn't a vouch).
- A candidate needs >= 2 unique voucherers to qualify for enrichment.
"""
import glob
import json
import os
from collections import defaultdict


def main():
    vouch_dir = os.path.join(os.path.dirname(__file__), "..", "data", "vouches")
    files = sorted(glob.glob(os.path.join(vouch_dir, "*.jsonl")))
    if not files:
        raise SystemExit(f"no vouch files in {vouch_dir} — run mine.py first")

    mentions = defaultdict(int)
    by_author = defaultdict(set)      # video_id -> set(authors)
    by_sub = defaultdict(set)         # video_id -> set(subreddits)
    best_ctx = {}                     # video_id -> (score, context)
    first_seen, last_seen = {}, {}

    for path in files:
        with open(path) as fh:
            for line in fh:
                rec = json.loads(line)
                vid = rec["video_id"]
                mentions[vid] += 1
                by_author[vid].add(rec["author"])
                by_sub[vid].add(rec["subreddit"])
                ts = rec.get("created_utc") or 0
                if vid not in first_seen or ts < first_seen[vid]:
                    first_seen[vid] = ts
                if vid not in last_seen or ts > last_seen[vid]:
                    last_seen[vid] = ts
                cur = best_ctx.get(vid)
                if cur is None or (rec.get("score") or 0) > cur[0]:
                    best_ctx[vid] = (rec.get("score") or 0, rec["context"])

    out = []
    for vid in mentions:
        authors = by_author[vid]
        n_authors = len(authors)
        # self-promo: dominant author share of raw mentions
        dominant_share = 0.0
        for _ in ():
            pass
        # (we don't track per-author counts here; approximation: n_authors vs mentions)
        qualifies = n_authors >= 2
        out.append({
            "video_id": vid,
            "mentions": mentions[vid],
            "vouchers": n_authors,
            "subreddits": sorted(by_sub[vid]),
            "first_seen": first_seen[vid],
            "last_seen": last_seen[vid],
            "why": best_ctx[vid][1],
            "qualifies": qualifies,
        })

    out.sort(key=lambda r: (-r["vouchers"], -r["mentions"]))
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "candidates.json")
    with open(out_path, "w") as fh:
        json.dump(out, fh)

    total = len(out)
    qualified = [r for r in out if r["qualifies"]]
    print(f"total unique videos mentioned: {total:,}")
    print(f"candidates (>=2 unique voucherers): {len(qualified):,}")
    print(f"output -> {out_path}\n")
    print("top 20 by unique voucherers:")
    for r in qualified[:20]:
        subs = ",".join(s[:6] for s in r["subreddits"][:3])
        print(f"  {r['vouchers']:>4} vouchers / {r['mentions']:>4} mentions | {subs:<24} | {r['why'][:80]}")


if __name__ == "__main__":
    main()
