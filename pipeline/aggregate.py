#!/usr/bin/env python3
"""Rank: raw vouches -> public corpus (corpus/videos.json).

HackerTube rule: a video qualifies when >= min_vouchers distinct people
recommended it in >= min_months distinct calendar months. Ranked by distinct
months (lasting recommendation beats a one-week spike), then distinct people.

Filters: bots, [deleted], self-links (commenter is the channel, or a "channel
promoter" whose links are mostly one channel), jokes/criticism (stance),
music/meme, Shorts, dead videos, deny-list, excluded channels (COI rule).
Per-game normalisation: score / p90(score within game) so FAB/Lorcana tops sit
next to MTG tops in the mixed view.

Public output contains NO usernames and no comment bodies, only quotes
<= 200 chars with permalinks.
"""
import datetime as dt
import glob
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, ROOT, load_config  # noqa: E402
import classify  # noqa: E402
import taxonomy  # noqa: E402

CORPUS = os.path.join(ROOT, "corpus")


def log(*a):
    print(*a, flush=True)


def month_key(ts):
    d = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc)
    return f"{d.year:04d}-{d.month:02d}"


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ------------------------------------------------------------------ loading
def load_vouches(cfg):
    sub_game = {s["name"].lower(): s["game"] for s in cfg["subreddits"]}
    files = sorted(glob.glob(os.path.join(DATA, "vouches_arctic", "*.jsonl")) +
                   glob.glob(os.path.join(DATA, "vouches", "*.jsonl")))
    seen, out = set(), []
    for p in files:
        for line in open(p):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if (r.get("subreddit") or "").lower() not in sub_game:
                continue  # only subreddits in this corpus' config (keeps PM data out of TCG)
            k = (r.get("id"), r["video_id"])
            if k in seen:
                continue
            seen.add(k)
            r.setdefault("body", r.get("context", ""))
            r["created_utc"] = int(r.get("created_utc") or 0)
            r["game"] = sub_game.get((r.get("subreddit") or "").lower())
            out.append(r)
    return out


def coverage(cfg, vouches, until):
    """Per-subreddit mining status + link-comment counts per year."""
    by = defaultdict(Counter)
    for v in vouches:
        by[v.get("subreddit") or "?"][month_key(v["created_utc"])[:4]] += 1
    rows = []
    for s in cfg["subreddits"]:
        name = s["name"]
        d = os.path.join(DATA, "vouches_arctic")
        done = set(open(os.path.join(d, f"{name}.done")).read().split()) if os.path.exists(os.path.join(d, f"{name}.done")) else set()
        failed = set(open(os.path.join(d, f"{name}.failed")).read().split()) if os.path.exists(os.path.join(d, f"{name}.failed")) else set()
        failed -= done
        y, m = map(int, s["start"].split("-"))
        uy, um = map(int, until.split("-"))
        nmonths = (uy - y) * 12 + (um - m) + 1
        step = s.get("step", 1)
        nq = 2  # queries per window: youtu.be + youtube
        expected = math.ceil(nmonths / step) * nq - nq  # current (incomplete) window excluded
        years = {k: v for k, v in sorted(by.get(name, {}).items())}
        rows.append({"subreddit": name, "game": s["game"], "start": s["start"], "windows_done": len(done),
                     "windows_expected": max(expected, 0), "windows_failed": len(failed),
                     "complete": len(done) >= expected and not failed, "links": sum(years.values()), "by_year": years})
    return rows


# ------------------------------------------------------------------ stats
def video_stats(vs, min_v, min_m):
    vs = sorted(vs, key=lambda v: v["created_utc"])
    authors, months, qualified = set(), set(), None
    for v in vs:
        authors.add(v["author"])
        months.add(month_key(v["created_utc"]))
        if qualified is None and len(authors) >= min_v and len(months) >= min_m:
            qualified = v["created_utc"]
    return {"vouchers": len(authors), "months": len(months), "qualified_ts": qualified,
            "first": month_key(vs[0]["created_utc"]) if vs else None,
            "last": month_key(vs[-1]["created_utc"]) if vs else None}


def p90(xs):
    xs = sorted(xs)
    if not xs:
        return 1.0
    return max(1.0, xs[min(len(xs) - 1, int(0.9 * (len(xs) - 1)))])


def main(argv=None):
    cfg = load_config()
    rk = cfg["ranking"]
    min_v, min_m = rk["min_vouchers"], rk["min_months"]
    count_st = set(rk["count_stances"])
    deny = set(cfg.get("deny_video_ids", []))
    bots = cfg.get("bot_authors", [])
    excl_names = {norm_name(n) for n in cfg["exclude_channels"].get("names", [])}
    excl_handles = {h.lower() for h in cfg["exclude_channels"].get("handles", [])}
    today = dt.date.today()
    until = today.strftime("%Y-%m")

    vouches = load_vouches(cfg)
    log(f"loaded {len(vouches):,} raw link-comments")
    cov = coverage(cfg, vouches, until)
    vouches = [v for v in vouches if v["video_id"] not in deny and v.get("author") not in ("[deleted]", "", None)]
    classify.label_vouches(vouches, bots, log=log)
    st = Counter(v["stance"] for v in vouches)
    log("stances:", dict(st))

    by_vid = defaultdict(list)
    shorts_hint = Counter()
    for v in vouches:
        if f"shorts/{v['video_id']}" in (v.get("body") or ""):
            shorts_hint[v["video_id"]] += 1
        if v["stance"] in count_st:
            by_vid[v["video_id"]].append(v)
    all_by_vid = defaultdict(list)
    for v in vouches:
        all_by_vid[v["video_id"]].append(v)

    # pre-qualify before spending enrichment calls
    pre = [vid for vid, vs in by_vid.items() if video_stats(vs, min_v, min_m)["qualified_ts"]]
    log(f"pre-qualified (>= {min_v} people, >= {min_m} months): {len(pre):,} of {len(by_vid):,} vouched videos")

    # legacy fallback for games not fully re-mined
    complete_games = {g for g in {s["game"] for s in cfg["subreddits"]}
                      if all(c["complete"] for c in cov if c["game"] == g)}
    legacy_path = os.path.join(DATA, "legacy.json")
    legacy = {r["video_id"]: r for r in json.load(open(legacy_path))} if os.path.exists(legacy_path) else {}

    import enrich
    if os.environ.get("TCGTUBE_OFFLINE") == "1":
        meta = enrich.load_cache()
    else:
        meta = enrich.enrich(pre, log=log)

    # channel-promoter detection: author whose counted links are mostly one channel
    author_ch = defaultdict(Counter)
    for vid in pre:
        ch = norm_name((meta.get(vid) or {}).get("channel"))
        for v in by_vid[vid]:
            author_ch[v["author"]][ch] += 1
    promoters = set()
    for a, c in author_ch.items():
        ch, n = c.most_common(1)[0]
        if ch and n >= 3 and n / sum(c.values()) >= 0.5:
            promoters.add((a, ch))

    def excluded_channel(m):
        if norm_name(m.get("channel")) in excl_names:
            return True
        cu = (m.get("channel_url") or "").lower()
        return any(cu.endswith("/" + h) for h in excl_handles)

    videos, drops = [], Counter()
    for vid in set(pre) | set(legacy):
        m = meta.get(vid)
        if not m or m.get("status") != "ok":
            drops["no_meta_or_dead"] += 1
            continue
        if excluded_channel(m):
            drops["coi_excluded_channel"] += 1
            continue
        if (m.get("duration_s") is not None and m["duration_s"] < 60) or shorts_hint[vid] * 2 > len(all_by_vid.get(vid, [])) > 0:
            drops["shorts"] += 1
            continue
        ch = norm_name(m.get("channel"))
        vs = [v for v in by_vid.get(vid, [])
              if not (ch and (norm_name(v["author"]) == ch or (len(norm_name(v["author"])) >= 5 and
                                                                  (norm_name(v["author"]) in ch or ch in norm_name(v["author"])))))
              and (v["author"], ch) not in promoters]
        s = video_stats(vs, min_v, min_m) if vs else None
        sub_games = [v["game"] for v in vs if v.get("game")]
        pub_year = int(m["published"][:4]) if m.get("published") else None
        last_year = int(s["last"][:4]) if s and s["last"] else None
        tax = taxonomy.classify(m["title"], m["channel"], sub_games, pub_year, last_year, today.year, rk["dated_after_years"])
        if tax["type"] == "music":
            drops["music_meme"] += 1
            continue
        is_legacy = False
        if s and s["qualified_ts"]:
            score = s["months"] * 10 + min(s["vouchers"], 99) / 10
        elif vid in legacy and tax["game"] not in complete_games and tax["game"] != "General" and legacy[vid]["vouchers"] >= min_v:
            is_legacy = True
            lv = legacy[vid]["vouchers"]
            s = {"vouchers": lv, "months": None, "qualified_ts": None, "first": None, "last": None}
            score = 0.5 * lv * 10  # conservative proxy until re-mined (no month data)
        else:
            drops["not_qualified" if vid in pre else "legacy_below_bar_or_game_remined"] += 1
            continue
        videos.append({
            "id": vid, "title": m["title"], "channel": m["channel"], "duration_s": m.get("duration_s"),
            "published": m.get("published"), **tax,
            "vouchers": s["vouchers"], "months": s["months"], "first": s["first"], "last": s["last"],
            "qualified": dt.datetime.fromtimestamp(s["qualified_ts"], dt.timezone.utc).strftime("%Y-%m-%d") if s["qualified_ts"] else None,
            "subs": sorted({v["subreddit"] for v in vs}),
            "score": round(score, 2), "legacy": is_legacy, "meta_src": m.get("src"),
            "quotes": [{"q": q["q"], "url": q["url"], "sub": q["sub"], "ym": month_key(q["ts"]) if q["ts"] else None}
                       for q in classify.pick_quotes(vs, vid, 3)],
        })

    # per-game normalisation
    by_game = defaultdict(list)
    for v in videos:
        by_game[v["game"]].append(v["score"])
    den = {g: p90(xs) for g, xs in by_game.items()}
    for v in videos:
        v["norm"] = round(min(1.5, v["score"] / den[v["game"]]), 4)

    # also-vouched (co-vouch graph over distinct people; usernames never leave this process)
    ids = {v["id"] for v in videos}
    a2v = defaultdict(set)
    for vid in ids:
        for x in by_vid.get(vid, []):
            a2v[x["author"]].add(vid)
    vindex = {v["id"]: v for v in videos}
    for v in videos:
        c = Counter()
        for x in by_vid.get(v["id"], []):
            for o in a2v[x["author"]]:
                if o != v["id"]:
                    c[o] += 1
        also = [o for o, n in c.most_common(12) if n >= 2][:6]
        if len(also) < 6:  # fill from the same game/format/type
            pool = sorted((o for o in videos if o["id"] != v["id"] and o["id"] not in also and o["game"] == v["game"]
                           and (o["format"] == v["format"] or o["type"] == v["type"])), key=lambda o: -o["norm"])
            also += [o["id"] for o in pool[:6 - len(also)]]
        v["also"] = also

    videos.sort(key=lambda v: (-v["norm"], -v["score"]))
    os.makedirs(CORPUS, exist_ok=True)
    json.dump(videos, open(os.path.join(CORPUS, "videos.json"), "w"), ensure_ascii=False, indent=0)
    games = Counter(v["game"] for v in videos)
    stats = {"built": today.isoformat(), "videos": len(videos), "by_game": dict(games.most_common()),
             "legacy_fallback": sum(v["legacy"] for v in videos), "complete_games": sorted(complete_games),
             "raw_link_comments": len(vouches), "stances": dict(st), "drops": dict(drops),
             "stance_source": "llm" if classify.provider_available() else "heuristic",
             "meta_sources": dict(Counter(v["meta_src"] for v in videos)),
             "rule": f">= {min_v} distinct people in >= {min_m} distinct months"}
    json.dump(stats, open(os.path.join(CORPUS, "stats.json"), "w"), indent=1)
    json.dump(cov, open(os.path.join(CORPUS, "coverage.json"), "w"), indent=1)
    log(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
