#!/usr/bin/env python3
"""Vouch stance classification + 'why' quote selection.

Every comment that links a video gets a stance:
  recommend | cite | joke | criticize | self_promo | bot
Only stances in config ranking.count_stances (default recommend, cite) count.

Providers (pluggable via env):
  TCGTUBE_LLM_PROVIDER=openai     + OPENAI_API_KEY     (+ TCGTUBE_LLM_MODEL, default gpt-4o-mini)
  TCGTUBE_LLM_PROVIDER=anthropic  + ANTHROPIC_API_KEY  (+ TCGTUBE_LLM_MODEL, default claude-3-5-haiku-latest)
  unset / no key                  -> heuristic (works today, no network)

LLM results are cached in data/classify_cache.jsonl (keyed by comment id +
video id), so re-runs only pay for new comments.
"""
import json
import os
import re
import urllib.request

from common import DATA

STANCES = ["recommend", "cite", "joke", "criticize", "self_promo", "bot"]

# ---------------------------------------------------------------- heuristics
SELF_RX = re.compile(r"\b(?:my|our) (?:new |latest |first |own )?(?:video|channel|vid|episode|podcast|stream|series)\b|"
                     r"\bi (?:just )?(?:made|uploaded|posted|recorded|filmed|created|put together) (?:a|this|my|an)\b|"
                     r"\bsubscribe\b|\bcheck out my\b|\bshameless(?:ly)? plug\b|\bself[- ]promo", re.I)
BOT_RX = re.compile(r"\bi am a bot\b|\bi'm a bot\b|beep boop|\^\(?this is a bot|action was performed automatically|"
                    r"\|\[\d+\]\(https?://(?:www\.)?reddit\.com", re.I)
JOKE_RX = re.compile(r"rick ?roll|never gonna give|\bnice try\b|obligatory|\bthis is you\b|\brelevant:?\s*$|"
                     r"\b(?:lol|lmao|rofl|haha+)\b.*$|\bmandatory\b", re.I)
CRIT_RX = re.compile(r"\bclickbait\b|\bdon'?t watch\b|\bmisinformation\b|\bterrible (?:video|advice)\b|\bwrong\b.*\bvideo\b|"
                     r"\bawful\b|\bcringe\b|\bworst video\b|\bdisagree with (?:this|the) video\b|\bgarbage\b|\bdebunk", re.I)
REC_RX = re.compile(r"\b(?:check (?:out|this)|watch (?:this|it)|must[- ]watch|recommend|highly recommend|great (?:video|guide|explanation|watch)|"
                    r"(?:really|super) (?:good|helpful)|helped me|explains?|explanation|best (?:video|guide|explanation|one)|"
                    r"definitely watch|go watch|worth (?:a )?watch|learned|taught me|primer|tutorial|guide|"
                    r"this video|favou?rite|classic|legendary|amazing|excellent|fantastic|brilliant|essential|still holds up|"
                    r"start (?:here|with)|if you want to (?:learn|understand)|good (?:intro|introduction|video|resource))\b", re.I)


def heuristic_stance(body, author="", bot_authors=()):
    a = (author or "").lower()
    if a in {b.lower() for b in bot_authors} or (a.endswith("bot") and len(a) > 4) or a.endswith("_bot"):
        return "bot"
    t = body or ""
    if BOT_RX.search(t):
        return "bot"
    if SELF_RX.search(t):
        return "self_promo"
    if CRIT_RX.search(t):
        return "criticize"
    if JOKE_RX.search(t) and not REC_RX.search(t):
        return "joke"
    if REC_RX.search(t):
        return "recommend"
    # a bare link dropped into a discussion is a weak vouch: someone thought it answered the question
    return "cite"


# ---------------------------------------------------------------- quotes
MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
URL = re.compile(r"https?://\S+|www\.\S+|\b(?:youtu\.be|youtube\.com)/\S+")
USER = re.compile(r"(?:^|(?<=\W))/?u/[A-Za-z0-9_-]+|@[A-Za-z0-9_.-]{2,}")
SUBR = re.compile(r"(?:^|(?<=\W))/?r/[A-Za-z0-9_]+")
NOISE = re.compile(r"[*_`>#~|^]+|&gt;|&amp;|&lt;|&#x200B;|&nbsp;")


SLASHY = re.compile(r"\S*[/=?]\S*")  # leftover URL fragments (be/abc123, watch?v=...)
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“(])")


def clean_quote(body, max_len=200):
    """Short, username-free quote. Returns '' if nothing useful remains.
    Cleans the whole comment, then keeps the sentences most like a recommendation."""
    if not body:
        return ""
    t = MD_LINK.sub(lambda m: m.group(1) if not URL.match(m.group(1) or "") else "", body)
    t = URL.sub("", t)
    t = SLASHY.sub(lambda m: m.group(0) if re.fullmatch(r"\w+/\w+", m.group(0)) and len(m.group(0)) < 8 else "", t)
    t = USER.sub("someone", t)
    t = SUBR.sub(lambda m: m.group(0).lstrip("/"), t)
    t = NOISE.sub(" ", t)
    t = re.sub(r"\(\s*\)|\[\s*\]", "", t)
    t = re.sub(r"\s+", " ", t).strip(" -:;,.")
    if len(re.sub(r"[^A-Za-z]", "", t)) < 12:
        return ""
    if len(t) > max_len:
        sents = [x.strip() for x in SENT.split(t) if x.strip()]
        if len(sents) > 1:
            best = max(range(len(sents)), key=lambda i: (bool(REC_RX.search(sents[i])), -i))
            out = sents[best]
            j = best + 1
            while j < len(sents) and len(out) + 1 + len(sents[j]) <= max_len:
                out += " " + sents[j]
                j += 1
            t = out
        cut = t[:max_len]
        sp = cut.rfind(" ")
        t = (cut[:sp] if sp > max_len * 0.6 else cut).rstrip(" ,;:-") + "…"
    return t


def quote_window(body, video_id, width=700):
    """The part of a long comment that's about this video, cut on paragraph/line boundaries."""
    if not body:
        return ""
    if len(body) <= width:
        return body
    i = body.find(video_id)
    if i < 0:
        return body[:width]
    paras = re.split(r"\n\s*\n|\n(?=\s*(?:[-*]|\d+[.)]|\|))", body)
    pos = 0
    for para in paras:
        if pos <= i < pos + len(para) + 2:
            return para[:width] if len(para) > 30 else body[max(0, i - width // 2):i + width // 2]
        pos += len(para) + 2
    return body[max(0, i - width // 2):i + width // 2]


def permalink(sub, link_id, cid):
    post = (link_id or "").split("_")[-1]
    if not (sub and post and cid):
        return None
    return f"https://www.reddit.com/r/{sub}/comments/{post}/_/{cid}/"


def pick_quotes(vouches, video_id, n=3):
    """2–3 short quotes, preferring recommend stance, higher score, distinct authors and years."""
    ranked = sorted(vouches, key=lambda v: (v.get("stance") != "recommend", -(v.get("score") or 0)))
    out, seen_auth, seen_text = [], set(), set()
    for v in ranked:
        if v.get("author") in seen_auth:
            continue
        q = clean_quote(quote_window(v.get("body") or "", video_id))
        if not q or q.lower()[:60] in seen_text:
            continue
        seen_auth.add(v.get("author"))
        seen_text.add(q.lower()[:60])
        out.append({"q": q, "url": permalink(v.get("subreddit"), v.get("link_id"), v.get("id")),
                    "sub": v.get("subreddit"), "ts": v.get("created_utc")})
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- LLM providers
PROMPT = """You label Reddit comments that link a YouTube video, for a site that lists videos the trading-card-game community genuinely recommends.
For each item return its stance toward the linked video, one of:
recommend (endorses/suggests watching), cite (neutral reference/evidence/clip), joke (meme/gag/rickroll),
criticize (negative about the video), self_promo (the commenter made it or is plugging their channel), bot (automated).
Reply with JSON only: {"labels": [{"k": "<key>", "stance": "<stance>"}]}.
Items:
"""


def _post(url, headers, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def _llm_batch(items):
    prov = os.environ.get("TCGTUBE_LLM_PROVIDER", "").lower()
    text = PROMPT + "\n".join(json.dumps({"k": k, "comment": b[:600]}, ensure_ascii=False) for k, b in items)
    if prov == "openai":
        d = _post("https://api.openai.com/v1/chat/completions",
                  {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"},
                  {"model": os.environ.get("TCGTUBE_LLM_MODEL", "gpt-4o-mini"), "temperature": 0,
                   "response_format": {"type": "json_object"},
                   "messages": [{"role": "user", "content": text}]})
        content = d["choices"][0]["message"]["content"]
    elif prov == "anthropic":
        d = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                   "content-type": "application/json"},
                  {"model": os.environ.get("TCGTUBE_LLM_MODEL", "claude-3-5-haiku-latest"), "max_tokens": 4000,
                   "messages": [{"role": "user", "content": text}]})
        content = d["content"][0]["text"]
    else:
        raise RuntimeError("no LLM provider")
    content = content[content.find("{"):content.rfind("}") + 1]
    return {x["k"]: x["stance"] for x in json.loads(content).get("labels", []) if x.get("stance") in STANCES}


def provider_available():
    prov = os.environ.get("TCGTUBE_LLM_PROVIDER", "").lower()
    return (prov == "openai" and bool(os.environ.get("OPENAI_API_KEY"))) or \
           (prov == "anthropic" and bool(os.environ.get("ANTHROPIC_API_KEY")))


def label_vouches(vouches, bot_authors=(), batch_size=40, log=print):
    """Sets v['stance'] and v['stance_src'] in place. Heuristic first (bots/self-promo
    are cheap to spot); LLM refines the rest when a provider is configured."""
    cache_path = os.path.join(DATA, "classify_cache.jsonl")
    cache = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                r = json.loads(line)
                cache[r["k"]] = r["stance"]
            except (ValueError, KeyError):
                pass
    todo = []
    for v in vouches:
        k = f"{v.get('id')}:{v['video_id']}"
        h = heuristic_stance(v.get("body", ""), v.get("author", ""), bot_authors)
        if k in cache:
            v["stance"], v["stance_src"] = cache[k], "llm"
        elif h == "bot":
            v["stance"], v["stance_src"] = h, "heuristic"
        else:
            v["stance"], v["stance_src"] = h, "heuristic"
            todo.append((k, v))
    if not provider_available() or not todo:
        if todo:
            log(f"classify: heuristic stance for {len(todo):,} vouches (set TCGTUBE_LLM_PROVIDER + key for LLM)")
        return
    log(f"classify: LLM labelling {len(todo):,} vouches via {os.environ['TCGTUBE_LLM_PROVIDER']}")
    os.makedirs(DATA, exist_ok=True)
    with open(cache_path, "a") as fh:
        for i in range(0, len(todo), batch_size):
            chunk = todo[i:i + batch_size]
            try:
                labels = _llm_batch([(k, quote_window(v.get("body", ""), v["video_id"], 600)) for k, v in chunk])
            except Exception as e:  # keep heuristic labels on failure
                log(f"  batch {i} failed: {e}")
                continue
            for k, v in chunk:
                if k in labels:
                    v["stance"], v["stance_src"] = labels[k], "llm"
                    fh.write(json.dumps({"k": k, "stance": labels[k]}) + "\n")
