#!/usr/bin/env python3
"""/pm: hand-curated product management shelves (config/pm_shelves.yaml).

  python3 pipeline/pm.py verify    re-check every id via YouTube oEmbed (no key),
                                   refresh cached title/channel, flag dead ones
  python3 pipeline/pm.py suggest   mine PM subreddits (Arctic Shift) into
                                   data/pm_vouches/, rank with the same rule, and
                                   write data/pm_suggestions.md FOR TOM'S REVIEW.
                                   Never written to the site or to pm_shelves.yaml.
The site build (build_site.py) reads only pm_shelves.yaml.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, ROOT  # noqa: E402
import yaml  # noqa: E402

SHELF_PATH = os.path.join(ROOT, "config", "pm_shelves.yaml")
PM_SUBS = "ProductManagement,prodmgmt,ProductMgmt,startups"


def load_shelves(path=SHELF_PATH):
    return yaml.safe_load(open(path)) if os.path.exists(path) else {"shelves": []}


def oembed(vid):
    u = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
    try:
        with urllib.request.urlopen(u, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403, 404):
            return None
        raise


def verify():
    raw = open(SHELF_PATH).read()
    header = "".join(line for line in raw.splitlines(True) if line.startswith("#"))
    doc = load_shelves()
    bad = []
    for s in doc["shelves"]:
        for v in s["videos"]:
            d = oembed(v["id"])
            if not d:
                v["dead"] = True
                bad.append(v["id"])
            else:
                v["title"], v["channel"] = d["title"], d["author_name"]
                v.pop("dead", None)
    open(SHELF_PATH, "w").write(header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=140))
    print(f"verified {sum(len(s['videos']) for s in doc['shelves'])} picks; dead: {bad or 'none'}")


def suggest():
    """Mine PM subs to a separate dir and produce a review list. Slow (shared API)."""
    cfg = os.path.join(ROOT, "config", "pm.yaml")
    if not os.path.exists(cfg):
        cfg = os.path.join(ROOT, "config", "pm.yaml.parked")
    out = os.path.join(DATA, "pm_vouches")
    subprocess.check_call([sys.executable, os.path.join(ROOT, "pipeline", "mine_arctic.py"), "--outdir", out],
                          env={**os.environ, "TCGTUBE_CONFIG": cfg})
    import aggregate
    import classify
    vs = []
    for f in os.listdir(out):
        if f.endswith(".jsonl"):
            vs += [json.loads(line) for line in open(os.path.join(out, f))]
    vs = [v for v in vs if v.get("author") not in ("[deleted]", "")]
    classify.label_vouches(vs, ["AutoModerator"], log=lambda *a: None)
    by = defaultdict(list)
    for v in vs:
        if v["stance"] in ("recommend", "cite"):
            by[v["video_id"]].append(v)
    have = {v["id"] for s in load_shelves()["shelves"] for v in s["videos"]}
    rows = []
    for vid, x in by.items():
        st = aggregate.video_stats(x, 3, 3)
        if st["qualified_ts"] and vid not in have:
            rows.append((st["months"], st["vouchers"], vid, classify.pick_quotes(x, vid, 2)))
    rows.sort(reverse=True)
    p = os.path.join(DATA, "pm_suggestions.md")
    with open(p, "w") as fh:
        fh.write("# PM suggestions — FOR REVIEW ONLY (not published)\n\nCopy any you like into config/pm_shelves.yaml.\n\n")
        for months, people, vid, qs in rows[:200]:
            fh.write(f"- https://www.youtube.com/watch?v={vid} — {people} people, {months} months\n")
            for q in qs:
                fh.write(f"  > {q['q']} ({q['url']})\n")
    print(f"{len(rows)} suggestions -> {p}")


if __name__ == "__main__":
    {"verify": verify, "suggest": suggest}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
