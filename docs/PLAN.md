# VouchTube — Plan

## Target output (per corpus)

A static site at `tcg.tmrss.co` (TCG) / `pm.tmrss.co` (PM):

- Grid of videos, each with: title, channel, duration, representative mid-video thumbnail, vouch count, `why` blurb, topic + content-type tags, link out to YouTube.
- Filters: topic (MTG / Pokémon / YGO / Lorcana / FAB / …), content type (learning / gameplay / opening / review / talk / podcast), level, duration bucket, minimum vouches, recency.
- No logins; likes/history state stays in `localStorage` if we add it at all.
- `/rss.xml`: weekly digest of newly-vouched videos (title + why-blurb + link).

## Pipeline stages

1. **Mine** (`pipeline/mine.py`)
   - Input: Arctic Shift monthly dump files (per-subreddit), NDJSON `.zst`.
   - Extract every YouTube link (watch / youtu.be / live / embed / shorts) from comments + posts.
   - Record a *vouch*: (video_id, subreddit, timestamp, post/comment id, score, surrounding text).
   - Dedupe self-promotion spam: same video posted repeatedly by the same author, or low-score isolated mentions, get discounted. A video needs ≥2 independent vouchers to be a candidate.
2. **Enrich** (`pipeline/enrich.py`)
   - YouTube Data API (key via env): title, channel, duration, view count, category.
   - Drop: <60s (Shorts), deleted/private (API 404s), music videos (category 10) unless vouched as educational.
3. **Classify** (`pipeline/classify.py`)
   - LLM over title + channel + first vouch context: topic, content type, level, one-line `why` written from the vouching comments (Karpathy's `why_hn` pattern — quote the humans, don't invent).
4. **Build** (`pipeline/build_site.py`)
   - Static HTML/JS + JSON index. No framework needed for v0; the data is small (hundreds, not millions, of videos).
   - Emit `/rss.xml` per corpus.

## Corpus configs

```yaml
tcg:
  subreddits: [magicTCG, EDH, mtgfinance, PokemonTCG, yugioh, lorcana, fleshandbloodtcg]
  topics: [MTG, Pokémon, Yu-Gi-Oh, Lorcana, FAB, other]
  content_types: [learning, gameplay, opening, review, talk, news]
pm:
  subreddits: [ProductManagement, productmanagement,ExperiencedDevs, SaaS]
  content_types: [talk, explainer, case-study, interview, course]
```

## Out of scope (for now)

- Live/streaming recs, anything requiring logins, user accounts, backend server.
- Comments on the site itself.

## Open questions

- How far back to mine (2015→ now vs. full archive)? Older vouches for evergreen content are still valid; openings/price content decays. Probably: mine everything, but weight recent vouches higher in "new" feeds.
- Minimum vouch threshold per corpus size — needs real counts first.
