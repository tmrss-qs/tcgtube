#!/usr/bin/env python3
"""Mine vouches: extract every YouTube recommendation from subreddit dump files.

Input:  Watchful1/Arctic Shift per-subreddit dumps (.zst NDJSON) in data/reddit/
Output: data/vouches/<subreddit>.jsonl — one record per YouTube link occurrence:
        {video_id, kind: comment|submission, author, created_utc, score, id,
         link_id, subreddit, context}

A "vouch" is any human mentioning a YouTube video. Aggregation (unique vouchers,
self-promo discounting, thresholds) happens later — this stage just captures
the raw signal.
"""
import argparse
import json
import os
import re
import sys
import zstandard as zstd

# YouTube link patterns -> extract 11-char video id
YT_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/(?:watch\?[^ \]\)>]*v=|live/|embed/|shorts/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)

BAD_ID_PREFIXES = ("GOLD", "SILV")  # improbable; kept for future junk filters


def extract_ids(text: str):
    if not text or "yout" not in text:
        return []
    ids = []
    for m in YT_RE.finditer(text):
        ids.append(m.group(1))
    return ids


def context_around(text: str, start: int, end: int, width: int = 120) -> str:
    lo = max(0, start - width)
    hi = min(len(text), end + width)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()


def iter_lines(path: str):
    with open(path, "rb") as fh:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(fh) as reader:
            buf = b""
            while True:
                chunk = reader.read(1 << 20)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        yield line


def mine_file(path: str, kind: str, out_fh, stats: dict) -> None:
    for line in iter_lines(path):
        stats["lines"] += 1
        # cheap pre-filter before JSON parse
        if b"yout" not in line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            stats["badjson"] += 1
            continue
        if kind == "comment":
            text = rec.get("body") or ""
            author = rec.get("author") or ""
            score = rec.get("score") or 0
            link_id = rec.get("link_id") or ""
            rid = rec.get("id") or ""
        else:
            text = " ".join(filter(None, [rec.get("title") or "",
                                          rec.get("selftext") or "",
                                          rec.get("url") or ""]))
            author = rec.get("author") or ""
            score = rec.get("score") or 0
            link_id = ""
            rid = rec.get("id") or ""
        for m in YT_RE.finditer(text):
            ctx = context_around(text, m.start(), m.end())
            out = {
                "video_id": m.group(1),
                "kind": kind,
                "author": author,
                "created_utc": rec.get("created_utc"),
                "score": score,
                "id": rid,
                "link_id": link_id,
                "subreddit": rec.get("subreddit") or "",
                "context": ctx,
            }
            out_fh.write(json.dumps(out, ensure_ascii=False) + "\n")
            stats["vouches"] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump_dir", help="dir containing <Sub>_{comments,submissions}.zst")
    ap.add_argument("out_dir", help="dir to write <sub>.jsonl vouch files")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    for fname in sorted(os.listdir(args.dump_dir)):
        if not fname.endswith(".zst"):
            continue
        sub = fname.split("_")[0]
        kind = "comment" if "_comments" in fname else "submission"
        out_path = os.path.join(args.out_dir, f"{sub}_{kind}.jsonl")
        if os.path.exists(out_path):
            print(f"skip (exists): {out_path}", file=sys.stderr)
            continue
        stats = {"lines": 0, "vouches": 0, "badjson": 0}
        with open(out_path, "w") as out:
            mine_file(os.path.join(args.dump_dir, fname), kind, out, stats)
        print(f"{fname}: {stats['lines']:,} lines -> {stats['vouches']:,} vouches "
              f"({stats['badjson']} bad json) -> {out_path}")


if __name__ == "__main__":
    main()
