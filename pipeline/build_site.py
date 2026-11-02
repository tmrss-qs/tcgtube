#!/usr/bin/env python3
"""Build The Vault static site from enriched data.

Input:  data/enriched.json
Output: site/index.html         (hub)
        site/tcg/index.html     (TCG grid, client-side filters)
        site/tcg/data.js        (embedded video records)
        site/tcg/rss.xml        (weekly-style digest feed)

Design: 006-hybrid — grid layout of the youtube-calm sketch, color/style of
the macwright sketch (#B44240 accent, serif underlined titles, mono meta).
Labels for v1 are rule-based (title keywords + source subreddits); the LLM
classification pass refines later.
"""
import html
import json
import os
import re
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(ROOT, "site")

TOPIC_RULES = [
    ("MTG", re.compile(r"\bmtg\b|magic the gathering|commander|edh|modern |legacy |pioneer |standard |draft|planeswalker|magic: ", re.I)),
    ("Pokemon", re.compile(r"pokemon|pok\u00e9mon|pikachu|charizard|tcg pocket|\bptcgo\b|booster bundle", re.I)),
    ("Yu-Gi-Oh", re.compile(r"yugioh|yu-gi-oh|duel monsters|pot of greed|\bygo\b", re.I)),
    ("Lorcana", re.compile(r"lorcana|illumineer", re.I)),
    ("FAB", re.compile(r"flesh and blood|flesh & blood|leonis|blitz deck|\bfab\b", re.I)),
    ("General", re.compile(r".")),
]
TYPE_RULES = [
    ("learning", re.compile(r"how to|learn|beginner|guide|tutorial|explained|rules|tips|basics|introduction|primer", re.I)),
    ("gameplay", re.compile(r"gameplay|match|v\.? ?\?|vs\.? |versus|matchup|game |round \d|topdeck|combo", re.I)),
    ("review", re.compile(r"review|worth it|unboxing|first look|impressions", re.I)),
    ("talk", re.compile(r"panel|presentation|gdc|keynote|lecture|podcast|interview|seminar", re.I)),
    ("commentary", re.compile(r"commentary|response|thoughts|opinion|discuss", re.I)),
    ("other", re.compile(r".")),
]
MTG_SUBS = {"magicTCG", "EDH", "CompetitiveEDH", "mtgfinance"}


def label(rec):
    text = f"{rec['title']} {rec['channel']}"
    subs = set(rec["subreddits"])
    topic = None
    for name, rx in TOPIC_RULES:
        if rx.search(text):
            topic = name
            break
    if topic == "General":
        if subs & MTG_SUBS and not subs - MTG_SUBS:
            topic = "MTG"
    ctype = None
    for name, rx in TYPE_RULES:
        if rx.search(text):
            ctype = name
            break
    return topic, ctype


def rss(entries, out_path):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    items = []
    for r in entries[:50]:
        link = f"https://www.youtube.com/watch?v={r['video_id']}"
        items.append(
            f"    <item>\n"
            f"      <title>{html.escape(r['title'])}</title>\n"
            f"      <link>{link}</link>\n"
            f"      <guid isPermaLink=\"false\">vault-{r['video_id']}</guid>\n"
            f"      <description>{html.escape(r['why'][:280])}</description>\n"
            f"      <pubDate>{now}</pubDate>\n"
            f"    </item>")
    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>The Vault — TCG</title>
    <link>https://vault.tmrss.co/tcg</link>
    <description>Videos the TCG community actually vouches for. No algorithm, no Shorts.</description>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""
    with open(out_path, "w") as fh:
        fh.write(doc)


def main():
    with open(os.path.join(ROOT, "data", "enriched.json")) as fh:
        recs = json.load(fh)
    for r in recs:
        t, c = label(r)
        r["topic"], r["content_type"] = t, c
    topics = sorted({r["topic"] for r in recs})
    types = sorted({r["content_type"] for r in recs})

    os.makedirs(os.path.join(OUT, "tcg"), exist_ok=True)

    # data.js
    slim = [{k: r[k] for k in ("video_id", "title", "channel", "duration_s",
                               "views", "vouchers", "mentions", "published",
                               "why", "topic", "content_type")}
            for r in recs]
    with open(os.path.join(OUT, "tcg", "data.js"), "w") as fh:
        fh.write("const DATA = " + json.dumps(slim, ensure_ascii=False) + ";\n")

    # TCG page (006-hybrid)
    page = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Vault — TCG</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--mono:"Berkeley Mono","JetBrains Mono","SF Mono",Monaco,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,"avenir next",avenir,helvetica,arial,sans-serif;--serif:Georgia,serif;--bg:#fff;--text:#111;--dim:#555;--accent:#B44240;--line:#eee}
body{background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.5;font-size:16px;-webkit-font-smoothing:antialiased}
.top{border-bottom:2px solid var(--text);padding:26px 0 14px;position:sticky;top:0;background:var(--bg);z-index:5}
.topin{max-width:1096px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:8px}
.brand{font-weight:700;font-size:22px}
.brand small{font-family:var(--serif);color:var(--dim);font-weight:400;font-size:.85rem;margin-left:12px}
nav a{color:var(--text);text-decoration:underline;text-decoration-skip-ink:auto;font-size:.9rem;margin-left:16px}
nav a.on{font-weight:700}
.main{max-width:1096px;margin:0 auto;padding:14px 24px 70px}
.filters{margin:10px 0 4px;font-size:.9rem}
.filters a{color:var(--text);text-decoration:underline;text-decoration-skip-ink:auto;margin-right:13px;cursor:pointer}
.filters a.on{font-weight:700;text-decoration:none;background:var(--accent);color:#fff;padding:1px 6px}
.count{font-family:var(--mono);font-size:.75rem;color:var(--dim);margin:10px 0 22px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(236px,1fr));gap:30px 20px}
.v{cursor:pointer}
.thumb{position:relative;aspect-ratio:16/9;border:1px solid var(--line)}
.thumb img{width:100%;height:100%;object-fit:cover;display:block;background:var(--line)}
.dur{position:absolute;right:5px;bottom:5px;background:rgba(17,17,17,.85);color:#fff;font-family:var(--mono);font-size:.68rem;padding:1px 5px}
.t{font-family:var(--serif);font-size:1.02rem;line-height:1.35;margin-top:10px;text-decoration:underline;text-decoration-skip-ink:auto;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.v:hover .t{background:var(--accent);color:#fff}
.why{font-family:var(--serif);font-size:.86rem;color:var(--dim);margin-top:5px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.m{font-family:var(--mono);font-size:.72rem;color:var(--dim);margin-top:7px}
.m b{color:var(--accent);font-weight:400}
.foot{margin-top:52px;font-family:var(--mono);font-size:.75rem;color:var(--dim);border-top:1px solid var(--line);padding-top:14px}
@media(max-width:640px){.main{padding:10px 14px 60px}.topin{padding:0 14px}.grid{grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:22px 12px}}
</style></head><body>
<div class="top"><div class="topin"><div class="brand">The Vault <small>videos people actually vouch for — no algorithm, no Shorts</small></div><nav><a class="on" href="/tcg/">TCG</a><a href="/pm/">Product</a><a href="/tcg/rss.xml">RSS</a></nav></div></div>
<div class="main">
<div class="filters" id="chips"></div>
<div class="count" id="meta"></div>
<div class="grid" id="grid"></div>
<div class="foot">The Vault — community-vouched TCG videos, mined from 20 years of Reddit (2005–2025). vault.tmrss.co</div>
</div>
<script src="data.js"></script>
<script>
const TOPICS=__TOPICS__,TYPES=__TYPES__;
let actT=new Set(),actC=new Set(),minV=0,q='';
const chips=document.getElementById('chips'),grid=document.getElementById('grid'),meta=document.getElementById('meta');
function mk(label,on,fn,group){const b=document.createElement('a');b.className=on?'on':'';b.textContent=label;b.onclick=()=>{fn();render()};return b}
function render(){
 chips.innerHTML='';
 chips.appendChild(mk('everything',actT.size===0,()=>{actT.clear()}));
 TOPICS.forEach(t=>chips.appendChild(mk(t,actT.has(t),()=>{actT.has(t)?actT.delete(t):actT.add(t)})));
 chips.appendChild(mk('||',false,()=>{}));
 TYPES.forEach(t=>chips.appendChild(mk(t,actC.has(t),()=>{actC.has(t)?actC.delete(t):actC.add(t)})));
 const rows=DATA.filter(c=>(actT.size===0||actT.has(c.topic))&&(actC.size===0||actC.has(c.content_type))&&c.vouchers>=minV);
 meta.textContent=rows.length+' / '+DATA.length+' videos · sorted by vouches · Shorts excluded';
 grid.innerHTML=rows.map(c=>{const m=Math.floor(c.duration_s/60),s=String(c.duration_s%60).padStart(2,'0');return `<div class="v"><div class="thumb"><img loading="lazy" src="https://i.ytimg.com/vi/${c.video_id}/mqdefault.jpg"><span class="dur">${m}:${s}</span></div><a class="t" href="https://www.youtube.com/watch?v=${c.video_id}" target="_blank" rel="noopener">${c.title}</a><div class="why">${c.why}</div><div class="m"><b>${c.vouchers} vouches</b> · ${c.channel} · ${c.topic} · ${c.content_type}</div></div>`}).join('');
}
render();
</script></body></html>"""
    page = page.replace("__TOPICS__", json.dumps(topics)).replace("__TYPES__", json.dumps(types))
    with open(os.path.join(OUT, "tcg", "index.html"), "w") as fh:
        fh.write(page)

    # hub
    hub = """<!doctype html><html><head><meta charset="utf-8"><title>The Vault</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--serif:Georgia,serif;--sans:-apple-system,BlinkMacSystemFont,avenir,helvetica,arial,sans-serif;--text:#111;--dim:#555;--accent:#B44240}
body{font-family:var(--sans);color:var(--text);background:#fff;line-height:1.6}
.page{max-width:680px;margin:0 auto;padding:80px 24px}
h1{font-size:2.6rem;font-family:var(--serif)}
.tag{font-family:var(--serif);color:var(--dim);font-size:1.15rem;margin:10px 0 40px}
.doors{border-top:2px solid var(--text)}
.door{display:block;padding:26px 0;border-bottom:1px solid #eee;text-decoration:none;color:var(--text)}
.door:hover h2{background:var(--accent);color:#fff}
h2{font-family:var(--serif);font-size:1.5rem;text-decoration:underline;display:inline}
.door p{color:var(--dim);margin-top:6px;font-size:.95rem}
.foot{margin-top:60px;font-family:ui-monospace,monospace;font-size:.75rem;color:var(--dim)}
</style></head><body><div class="page">
<h1>The Vault</h1>
<div class="tag">Videos people actually vouch for, mined from two decades of human recommendations. No algorithm, no Shorts, no logins.</div>
<div class="doors">
<a class="door" href="/tcg/"><h2>TCG</h2><p>__TCGCOUNT__ community-vouched videos across Magic, Pokémon, Yu-Gi-Oh, Lorcana, Flesh and Blood.</p></a>
<a class="door" href="/pm/"><h2>Product</h2><p>Product management, coming soon.</p></a>
</div>
<div class="foot">vault.tmrss.co · built by an agent and a person · github.com/tmrss-qs/tcgtube</div>
</div></body></html>"""
    hub = hub.replace("__TCGCOUNT__", f"{len(recs):,}")
    with open(os.path.join(OUT, "index.html"), "w") as fh:
        fh.write(hub)

    rss(recs, os.path.join(OUT, "tcg", "rss.xml"))
    print(f"site built -> {OUT}")
    print(f"  hub: index.html | tcg: tcg/index.html ({len(recs):,} videos, {len(topics)} topics, {len(types)} types) | rss: tcg/rss.xml")


if __name__ == "__main__":
    main()
