#!/usr/bin/env python3
"""Build the static TCGTube site from corpus/*.json (no network, no secrets).

Output (gitignored): site/
  index.html            index: filters, search, pagination, URL state (web/app.js)
  data/videos.json      slim records for the client
  v/<id>/index.html     per-video page: click-to-load youtube-nocookie embed,
                        quoted vouches with permalinks, also-vouched
  shelves/              curated shelves from config/shelves.yaml
  about/  coverage/     method, data policy, conflict of interest, mining coverage
  rss.xml               weekly "newly qualified" digest with real dates
Every string from data is HTML-escaped here; the client escapes again.
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, load_config  # noqa: E402

import yaml  # noqa: E402

OUT = os.environ.get("TCGTUBE_OUT", os.path.join(ROOT, "site"))
WEB = os.path.join(ROOT, "web")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
GAME_LABEL = {"MTG": "Magic", "Pokemon": "Pokémon", "Yu-Gi-Oh": "Yu-Gi-Oh!", "FAB": "Flesh and Blood",
              "Lorcana": "Lorcana", "One Piece": "One Piece", "General": "Cross-game"}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def e(s):
    return html.escape("" if s is None else str(s), quote=True)


def safe_url(u):
    return u if isinstance(u, str) and u.startswith("https://www.reddit.com/r/") and '"' not in u and "<" not in u else None


def dur(d):
    if d is None:
        return ""
    h, m, s = d // 3600, d % 3600 // 60, d % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def ym(s):
    if not s:
        return ""
    y, m = s.split("-")[:2]
    return f"{MONTHS[int(m) - 1]} {y}"


def page(cfg, title, body, *, active="", desc="", og_image=None, path="/", extra_head=""):
    base = cfg["base_url"].rstrip("/")
    full_title = f"{title} — {cfg['name']}" if title != cfg["name"] else cfg["name"]
    nav = [("/", "Index", "index"), ("/shelves/", "Shelves", "shelves"), ("/about/", "About", "about"),
           ("/coverage/", "Coverage", "coverage"), ("/rss.xml", "RSS", "rss")]
    navh = "".join(f'<a href="{h}"{" class=on" if k == active else ""}>{t}</a>' for h, t, k in nav)
    og = (f'<meta property="og:type" content="website"><meta property="og:site_name" content="{e(cfg["name"])}">'
          f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">'
          f'<meta property="og:url" content="{e(base + path)}"><link rel="canonical" href="{e(base + path)}">'
          + (f'<meta property="og:image" content="{e(og_image)}"><meta name="twitter:card" content="summary_large_image">' if og_image
             else '<meta name="twitter:card" content="summary">'))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title><meta name="description" content="{e(desc)}">
{og}
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/style.css">
<link rel="alternate" type="application/rss+xml" title="{e(cfg['name'])}: newly qualified this week" href="/rss.xml">
{extra_head}</head><body>
<header class="mast"><div class="wrap"><a class="brand" href="/">{e(cfg['name'])}</a><span class="tag">{e(cfg['tagline'])}</span><nav>{navh}</nav></div></header>
<main><div class="wrap">{body}</div></main>
<footer><div class="wrap">{e(cfg['name'])} · community-vouched, algorithm-free, non-commercial · <a href="/about/">how it works &amp; opt-out</a> · <a href="https://github.com/tmrss-qs/tcgtube">source</a></div></footer>
</body></html>"""


def thumb(vid, cls="thumb", d=None):
    return (f'<div class="{cls}"><img loading="lazy" alt="" src="https://i.ytimg.com/vi/{vid}/hq2.jpg" '
            f'onerror="this.onerror=null;this.src=\'https://i.ytimg.com/vi/{vid}/mqdefault.jpg\'">'
            + (f'<span class="dur">{e(dur(d))}</span>' if d is not None else "") + "</div>")


def card_html(v):
    meta = f'<b>{e(v["vouchers"])} people</b>' + (f' · {e(v["months"])} months' if v["months"] else " · first pass") + \
           f' · {e(GAME_LABEL.get(v["game"], v["game"]))}' + (f' · {e(v["format"])}' if v["format"] else "") + f' · {e(v["type"])}'
    why = f'<div class="why">“{e(v["quotes"][0]["q"])}”</div>' if v["quotes"] else ""
    year = f' · {e(v["published"][:4])}' if v.get("published") else ""
    return (f'<a class="card" href="/v/{v["id"]}/">{thumb(v["id"], d=v["duration_s"])}<div class="t">{e(v["title"])}</div>'
            f'<div class="ch">{e(v["channel"])}{year}</div>{why}<div class="m">{meta}</div></a>')


def slim(v):
    return {"i": v["id"], "t": v["title"], "c": v["channel"], "d": v["duration_s"],
            "y": (v.get("published") or "")[:4] or None, "g": v["game"], "f": v["format"], "k": v["type"],
            "l": v["level"], "s": v["shelf_life"], "v": v["vouchers"], "m": v["months"], "z": v["last"],
            "q": v["qualified"], "w": v["quotes"][0]["q"] if v["quotes"] else None, "n": v["norm"],
            "x": 1 if v["legacy"] else 0}


def build_index(cfg, videos, stats):
    first = [v for v in videos if v["shelf_life"] != "dated"][:48]
    body = f"""
<div class="controls">
 <span class="k">Search</span><div class="search"><input id="q" type="search" placeholder="commander deckbuilding, how to draft, grading…" aria-label="Search videos"></div>
</div>
<details class="filters" id="filters" open><summary id="fsum">Filters</summary><div class="controls">
 <span class="k">Game</span><div class="opts" id="o-game"></div>
 <span class="k" id="c-format">Format</span><div class="opts" id="o-format"></div>
 <span class="k">Type</span><div class="opts" id="o-type"></div>
 <span class="k">Length</span><div class="opts" id="o-len"></div>
 <span class="k">Order</span><div class="opts" id="o-sort"></div>
</div></details>
<div class="meta-line"><span id="count">{len(videos):,} videos</span><span>qualify: {e(stats.get('rule', ''))} · ranked by distinct months</span></div>
<div class="grid" id="grid">{''.join(card_html(v) for v in first)}</div>
<div class="pager" id="pager"></div>
<script src="/app.js" defer></script>"""
    return page(cfg, cfg["name"], body, active="index", path="/",
                desc=f"{len(videos):,} trading card game videos the community keeps recommending on Reddit — Magic, Pokémon, Yu-Gi-Oh!, Flesh and Blood, Lorcana, One Piece. No algorithm, no Shorts.",
                og_image=f"https://i.ytimg.com/vi/{videos[0]['id']}/hqdefault.jpg" if videos else None)


def build_video(cfg, v, index):
    vid = v["id"]
    g = GAME_LABEL.get(v["game"], v["game"])
    metas = [v["channel"], dur(v["duration_s"]) or None, (v.get("published") or "")[:4] or None, g, v["format"], v["type"],
             v["level"] if v["level"] != "all" else None, v["shelf_life"]]
    meta = "".join(f"<span>{e(x)}</span>" for x in metas if x)
    if v["legacy"]:
        stat = (f'<p class="stat">Linked by <b>{e(v["vouchers"])} different people</b> in the first-pass mine (2 Nov 2026). '
                f'Month spread and quotes arrive when its subreddits finish re-mining.</p>')
    else:
        span = f'{ym(v["first"])} to {ym(v["last"])}' if v["first"] != v["last"] else ym(v["first"])
        stat = (f'<p class="stat">Recommended by <b>{e(v["vouchers"])} people</b> across <b>{e(v["months"])} different months</b>, '
                f'{e(span)}.</p>')
    quotes = ""
    for q in v["quotes"]:
        u = safe_url(q.get("url"))
        where = f'r/{e(q["sub"])}' + (f', {e(ym(q["ym"]))}' if q.get("ym") else "")
        link = f' — <a href="{e(u)}" rel="nofollow noopener" target="_blank">thread ↗</a>' if u else ""
        quotes += f'<blockquote><p>“{e(q["q"])}”</p><cite>{where}{link}</cite></blockquote>'
    if not quotes:
        quotes = '<p class="empty">No quotable comment yet.</p>'
    also = ""
    for o in v.get("also", []):
        ov = index.get(o)
        if ov and ID_RE.match(o):
            also += (f'<a class="mini" href="/v/{o}/">{thumb(o, d=ov["duration_s"])}<div><div class="t">{e(ov["title"])}</div>'
                     f'<div class="m"><b>{e(ov["vouchers"])} people</b> · {e(ov["channel"])}</div></div></a>')
    crumb = f'<div class="crumb"><a href="/">Index</a> / <a href="/?g={e(v["game"])}">{e(g)}</a>' + \
            (f' / <a href="/?g={e(v["game"])}&amp;f={e(v["format"])}">{e(v["format"])}</a>' if v["format"] else "") + "</div>"
    body = f"""{crumb}<div class="v-layout"><div>
<div class="v-head"><h1>{e(v['title'])}</h1></div><div class="v-meta">{meta}</div>
<div class="player" id="player"><button type="button" aria-label="Play video (loads YouTube)" data-id="{vid}">
<img alt="" src="https://i.ytimg.com/vi/{vid}/hq2.jpg" onerror="this.onerror=null;this.src='https://i.ytimg.com/vi/{vid}/hqdefault.jpg'"><span class="play">▶ Play</span></button></div>
<div class="under"><span>Nothing loads from YouTube until you press play (youtube-nocookie).</span><a href="https://www.youtube.com/watch?v={vid}" rel="noopener" target="_blank">Watch on YouTube ↗</a></div>
{stat}
{quotes}
</div><aside class="side"><h3>People who recommended this also recommended</h3>{also or '<p class="m">—</p>'}</aside></div>
<script>document.querySelector('#player button').addEventListener('click',function(){{var id=this.getAttribute('data-id');if(!/^[A-Za-z0-9_-]{{11}}$/.test(id))return;var f=document.createElement('iframe');f.src='https://www.youtube-nocookie.com/embed/'+id+'?autoplay=1&rel=0';f.allow='autoplay; encrypted-media; picture-in-picture; fullscreen';f.allowFullscreen=true;f.title='YouTube video';var p=document.getElementById('player');p.textContent='';p.appendChild(f);}});</script>"""
    desc = v["quotes"][0]["q"] if v["quotes"] else f'Recommended by {v["vouchers"]} people in the TCG community.'
    return page(cfg, v["title"], body, path=f"/v/{vid}/", desc=desc, og_image=f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg")


def build_shelves(cfg, index):
    path = os.path.join(ROOT, cfg.get("shelf_file", "config/shelves.yaml"))
    doc = yaml.safe_load(open(path)) if os.path.exists(path) else {"shelves": []}
    parts, missing = [], []
    for s in doc.get("shelves", []):
        items = ""
        for it in s.get("videos", []):
            vid = it["id"] if isinstance(it, dict) else it
            note = it.get("note") if isinstance(it, dict) else None
            v = index.get(vid)
            if not v or not ID_RE.match(vid):
                missing.append(vid)
                continue
            items += (f'<li><a href="/v/{vid}/">{thumb(vid, d=v["duration_s"])}</a><div><a class="card" href="/v/{vid}/"><div class="t">{e(v["title"])}</div></a>'
                      f'<div class="ch">{e(v["channel"])}</div>' + (f'<div class="note">{e(note)}</div>' if note else "")
                      + f'<div class="m"><b>{e(v["vouchers"])} people</b>' + (f' · {e(v["months"])} months' if v["months"] else "") + "</div></div></li>")
        draft = '<div class="draft">DRAFT PICKS — auto-seeded from the rankings for Tom to edit in config/shelves.yaml</div>' if s.get("draft") else ""
        parts.append(f'<section class="shelf" id="{e(s["slug"])}"><h2>{e(s["title"])}</h2>{draft}<p class="intro">{e(s.get("intro", ""))}</p><ol>{items}</ol></section>')
    body = '<div class="prose"><h1>Shelves</h1><p>Short, ordered lists for when you don’t want to browse. Each pick is a video the community has kept recommending; the order and the notes are editorial.</p></div>' + "".join(parts)
    return page(cfg, "Shelves", body, active="shelves", path="/shelves/", desc="Curated shelves of community-vouched TCG videos."), missing


def build_about(cfg, stats):
    a = cfg["ranking"]
    body = f"""<div class="prose">
<h1>About</h1>
<p>{e(cfg['name'])} lists YouTube videos that people in trading card game communities keep recommending to each other on Reddit. There is no algorithm optimising for your attention: a video is here because different people, years apart, pointed someone to it.</p>
<h2>How a video gets in</h2>
<ul>
<li>We collect Reddit comments that link a YouTube video, from the subreddits listed on <a href="/coverage/">Coverage</a>.</li>
<li>Each comment is labelled: recommendation, neutral citation, joke, criticism, self-promotion or bot. Only recommendations and citations count. Labels are currently rule-based; an AI pass can replace them.</li>
<li>A video qualifies when at least <b>{a['min_vouchers']} different people</b> vouched for it in at least <b>{a['min_months']} different months</b>. It is ranked by how many distinct months it was recommended in, so a classic that keeps coming up beats a one-week spike.</li>
<li>Rankings are normalised per game, so the best Flesh and Blood or Lorcana videos sit next to the best Magic ones instead of under them.</li>
<li>Dropped: bots, people linking their own channel, music and memes, Shorts, deleted or private videos.</li>
<li>Deck techs, set reviews and price videos are marked <i>dated</i> once they are a couple of years old and hidden by default.</li>
</ul>
<h2>Data and privacy</h2>
<ul>
<li>Reddit data comes from the Arctic Shift archive (and, for first-pass counts, the Pushshift dumps). We publish video IDs, counts, and short quotes (200 characters at most) that link back to the original thread. We never publish usernames.</li>
<li>Quotes from comments that were deleted or removed are never shown.</li>
<li><b>Opt-out:</b> if you wrote a quoted comment or made a listed video and want it removed, open an issue at <a href="https://github.com/tmrss-qs/tcgtube/issues">github.com/tmrss-qs/tcgtube</a> [DRAFT: Tom to add a contact email] and it will be removed in the next build.</li>
<li>Non-commercial: no ads, no affiliate links, no tracking cookies. Videos play from youtube-nocookie and nothing loads from YouTube until you press play.</li>
</ul>
<h2>Who makes this</h2>
<div class="draft">DRAFT WORDING — Tom to confirm before launch</div>
<p>{e(cfg['name'])} is a side project by Tom Ross, a product manager in Melbourne who plays Magic, Pokémon and Flesh and Blood and makes TCG videos as <b>@tmrss</b>. To avoid any conflict of interest, <b>his own channel is excluded from the index by rule</b> and never ranked or featured.</p>
<p>He is not the Magic pro player Tom Ross. Coverage featuring that Tom Ross appears only when the community recommended it.</p>
<h2>Numbers</h2>
<p>{stats.get('videos', 0):,} videos listed. {stats.get('videos', 0) - stats.get('legacy_fallback', 0):,} qualified on re-mined data ({stats.get('raw_link_comments', 0):,} link-comments so far); {stats.get('legacy_fallback', 0):,} are carried over from the first-pass counts (Pushshift dumps, 2 Nov 2026) until their subreddits finish re-mining (see <a href="/coverage/">Coverage</a>). Built {e(stats.get('built', ''))}. Comment labels: <code>{e(stats.get('stance_source', 'heuristic'))}</code>.</p>
</div>"""
    return page(cfg, "About", body, active="about", path="/about/", desc="How TCGTube picks videos, data policy, opt-out and conflict of interest.")


def build_coverage(cfg, cov, stats):
    years = sorted({y for c in cov for y in c["by_year"]})
    rows = ""
    for c in cov:
        mx = max(c["by_year"].values(), default=1) or 1
        bars = "".join(f'<i style="height:{max(1, round(14 * c["by_year"].get(y, 0) / mx))}px" title="{e(y)}: {c["by_year"].get(y, 0)}"></i>' for y in years)
        status = "complete" if c["complete"] else f'partial ({c["windows_done"]}/{c["windows_expected"]} windows' + (f', {c["windows_failed"]} failed' if c["windows_failed"] else "") + ")"
        rows += (f'<tr><td>r/{e(c["subreddit"])}</td><td>{e(GAME_LABEL.get(c["game"], c["game"]))}</td><td>{e(c["start"])}</td>'
                 f'<td>{e(status)}</td><td class="num">{c["links"]:,}</td><td class="bars">{bars}</td></tr>')
    by_game = "".join(f'<tr><td>{e(GAME_LABEL.get(g, g))}</td><td class="num">{n:,}</td></tr>' for g, n in stats.get("by_game", {}).items())
    drops = "".join(f'<tr><td>{e(k.replace("_", " "))}</td><td class="num">{n:,}</td></tr>' for k, n in stats.get("drops", {}).items())
    body = f"""<div class="prose"><h1>Coverage</h1>
<p>What has been mined, so you can judge the gaps. Counts are Reddit comments linking a YouTube video (before filtering). Years shown {e(years[0] if years else '')}–{e(years[-1] if years else '')}.</p>
<p>Games whose subreddits are not fully re-mined fall back to the first-pass counts from 2 Nov 2026, marked “first pass” in the index: {stats.get('legacy_fallback', 0):,} videos right now.</p></div>
<table><thead><tr><th>Subreddit</th><th>Game</th><th>From</th><th>Status</th><th>Link-comments</th><th>By year</th></tr></thead><tbody>{rows}</tbody></table>
<div class="prose"><h2>Qualified videos by game</h2></div><table style="max-width:420px"><tbody>{by_game}</tbody></table>
<div class="prose"><h2>Filtered out</h2></div><table style="max-width:420px"><tbody>{drops}</tbody></table>"""
    return page(cfg, "Coverage", body, active="coverage", path="/coverage/", desc="Which subreddits and years TCGTube has mined.")


def build_rss(cfg, videos, today):
    """One item per week (last 8 weeks): the videos that newly crossed the bar that week."""
    base = cfg["base_url"].rstrip("/")
    weeks = defaultdict(list)
    horizon = today - dt.timedelta(weeks=8)
    for v in videos:
        if v["qualified"]:
            d = dt.date.fromisoformat(v["qualified"])
            if d > horizon:
                monday = d - dt.timedelta(days=d.weekday())
                weeks[monday].append(v)
    items = []
    for monday in sorted(weeks, reverse=True):
        end = min(monday + dt.timedelta(days=6), today)
        vs = sorted(weeks[monday], key=lambda v: -v["norm"])
        lis = "".join(f'<li><a href="{base}/v/{v["id"]}/">{e(v["title"])}</a> — {e(v["channel"])} '
                      f'({e(GAME_LABEL.get(v["game"], v["game"]))}, {v["vouchers"]} people)'
                      + (f'<br><i>“{e(v["quotes"][0]["q"])}”</i>' if v["quotes"] else "") + "</li>" for v in vs)
        pub = dt.datetime.combine(end, dt.time(9, 0), dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        iso = monday.isocalendar()
        items.append(f"""  <item>
    <title>{e(f"New this week ({monday:%d %b} – {end:%d %b %Y}): {len(vs)} video" + ("s" if len(vs) != 1 else ""))}</title>
    <link>{base}/?sort=new</link>
    <guid isPermaLink="false">tcgtube-week-{iso[0]}-W{iso[1]:02d}</guid>
    <pubDate>{pub}</pubDate>
    <description>{e("<ul>" + lis + "</ul>")}</description>
  </item>""")
    now = dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>{e(cfg['name'])}: newly qualified this week</title>
  <link>{base}/</link>
  <description>Each week, the videos that just crossed the bar: {e(cfg['ranking']['min_vouchers'])}+ different people recommending them in {e(cfg['ranking']['min_months'])}+ different months.</description>
  <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
</channel></rss>
"""


FAVICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect x="7" y="3" width="18" height="26" fill="#fff" stroke="#111" stroke-width="2"/><rect x="11" y="9" width="10" height="8" fill="#B44240"/></svg>'


def main():
    cfg = load_config()
    videos = json.load(open(os.path.join(ROOT, "corpus", "videos.json")))
    stats = json.load(open(os.path.join(ROOT, "corpus", "stats.json")))
    cov = json.load(open(os.path.join(ROOT, "corpus", "coverage.json")))
    videos = [v for v in videos if ID_RE.match(v["id"])]
    index = {v["id"]: v for v in videos}
    today = dt.date.fromisoformat(stats["built"]) if stats.get("built") else dt.date.today()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "data"))
    for f in ("style.css", "app.js"):
        shutil.copy(os.path.join(WEB, f), os.path.join(OUT, f))
    open(os.path.join(OUT, "favicon.svg"), "w").write(FAVICON)
    json.dump([slim(v) for v in videos], open(os.path.join(OUT, "data", "videos.json"), "w"), ensure_ascii=False, separators=(",", ":"))

    def write(rel, s):
        p = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(s)

    write("index.html", build_index(cfg, videos, stats))
    for v in videos:
        write(f"v/{v['id']}/index.html", build_video(cfg, v, index))
    shelves, missing = build_shelves(cfg, index)
    write("shelves/index.html", shelves)
    write("about/index.html", build_about(cfg, stats))
    write("coverage/index.html", build_coverage(cfg, cov, stats))
    write("rss.xml", build_rss(cfg, videos, today))
    write("404.html", page(cfg, "Not found", '<div class="prose"><h1>Not here.</h1><p><a href="/">Back to the index</a>.</p></div>', desc="Not found"))
    print(f"site -> {OUT}: {len(videos):,} videos, {len(videos):,} video pages" + (f"; shelf ids not in corpus: {missing}" if missing else ""))


if __name__ == "__main__":
    main()
