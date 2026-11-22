# TCGTube — Build Log

Running log of how this gets built, kept live for the accompanying essay. Numbers here are measured, not vibes.

## 2026-11-02 — Day 0: idea, probes, scaffolding

**Origin.** Karpathy's HackerTube tweet (Hack 43M HN comments → 6,454 videos people keep recommending → clean static site, ~2h with Opus 5.5). We're applying the same pattern to two corpora Tom actually cares about: TCG content and product management content.

**Probes (real numbers):**

- Arctic Shift interactive API: works but flaky under load — unquoted body searches 422 ("Timeout. Maybe slow down"), quoted-phrase searches succeeded once then started timing out. **Decision:** the mining pipeline uses the monthly dump files / parquet mirror, not the interactive API.
- HN (Algolia) as a PM corpus: `"product management" + youtube` = **71 comments ever**; `"product manager" + youtube` = **144 ever**. HN is dev-heavy; PM video recs live on Reddit. **Decision:** PM corpus = r/ProductManagement + friends, not HN.
- Karpathy's site exposes his full dataset at `/api/list` (30 per page, `offset` paging). Pulled all **6,454 videos** in 215 requests (~13MB). Content types: talk 1,448 / explainer 1,091 / demo 827 / comedy 567 / commentary 457 / documentary 404 / interview 342 / lecture 317…
- Cross-check of his set against our corpora: only **22 PM-relevant** and **47 TCG/game-adjacent** videos. Confirms both corpora need their own mining; his data is the schema blueprint, not seed content.
- Schema worth stealing wholesale: per-video `summary`, `why_hn` (the human-reason it keeps being recommended), `content_type`, `level`, `shelf_life`, `primary_topic`, `tags`, `score`/`whys` (vouch count).

**Product decisions:**

- One engine, two corpora (TCG first, PM second — second should be a config change, not a rebuild).
- Hosting: existing Cloudflare setup, subdomains `tcg.tmrss.co` / `pm.tmrss.co`. Free, push-to-deploy. A standalone domain can come later without rebuilding. *(Superseded same evening — see Naming below: one domain, vault.tmrss.co.)*
- Each corpus publishes an **RSS feed** (weekly digest of newly-vouched videos) — subscribe in Readwise Reader. Push distribution for a static site, zero ongoing cost.
- Filters: by game/topic, by content type (learning / gameplay / openings), minimum vouch count, no Shorts (<60s via API duration).
- Openings will be the thinnest category by construction — Redditors rarely vouch for opening videos. The ones they do vouch for are the legends. That's fine; it's a feature of "human vouches" as a signal, not a bug.

**Infra decisions:**

- Public repo from day one (github.com/tmrss-qs/tcgtube), MIT, no keys in the repo — YouTube API key via `.env`.
- Build on the Mac mini (M4, 24GB). Watch disk: full Arctic Shift monthly dumps are 50GB+ each — use per-subreddit files / parquet queries, not whole-month downloads.

**Naming (evolved over one evening, kept for the record):** repo briefly `vouchtube` (the signal is human *vouches*), renamed to **tcgtube** on Tom's call — name each thing after what it is. Umbrella product = **The Vault** at `vault.tmrss.co`: one domain, hub page, `/tcg` and `/pm` sections with per-section RSS. Two subdomains died in favor of one door each.

**Design (settled 2 Nov, after sketch rounds):** five variants were sketched (~/.hermes/workspace/tcgtube/sketches/): three invented takes (noir / quiet index / tool dense) — Tom's verdict: "too AI generated UI wise, bit ugly." Lesson recorded: don't invent UI; copy real systems. Rebuilt as two faithful copies — 004-youtube-calm (Karpathy's actual HackerTube CSS: white/#0f0f0f/#ff6600) and 005-macwright-vault (macwright.com's real tokens, Tom's chosen lineage for tmrss.co). Tom's call: **hybrid — layout of 004, color/style of 005.** = 006-hybrid: sticky header, filter text-links (active = madder red #B44240 box), 4-col thumbnail grid, serif underlined titles (red on hover), serif why-blurbs, mono metadata with red vouch counts, square corners, zero shadows/pills/rounded cards. THE target look.

**Next:** stand up the TCG mining against the Reddit dumps → first real vouch counts → then enrichment + site.

## 2026-11-22 — v2 quality pass (branch `v2/quality-pass`)

**Why:** an assessment of v1 scored it 3/10. The site never went live (no DNS record). Every link counted as a vouch, the self-promo discount was a no-op, the "why" was a raw Reddit snippet with URLs, titles rendered in browser blue, thumbnails were clickbait, all 14k cards were in one DOM, and Reddit text went into `innerHTML` unescaped.

**What changed:**
- **Ranking:** the HackerTube rule, ≥3 distinct people in ≥3 distinct months, ranked by distinct months.
  - Stance labels: heuristic now, LLM-pluggable.
  - Removed: bots, self-links and channel promoters, music and memes, Shorts, dead videos.
  - Excluded Tom's channel (COI rule).
  - Per-game normalisation.
- **Taxonomy:** game → format → type → level → rotation-aware shelf life.
- **Data source:** Arctic Shift API instead of torrents (no key; paced because the shared API rate-limits with "Timeout. Maybe slow down a bit"). Coverage is published at /coverage. Games whose subreddits aren't fully re-mined fall back to the v1 counts, marked "first pass".
- **Data hygiene:** the public corpus has IDs, counts and quotes of ≤200 chars with permalinks. No usernames. `site/` is now build output, not committed.
- **Site:**
  - Escaping everywhere, ink-coloured serif titles, and mid-video frames (`hq2.jpg`).
  - Pagination (48 per page), search (`/` focuses it), URL-state filters, a length filter, and a collapsible mobile filter panel.
  - OG tags, per-video pages with a click-to-load youtube-nocookie embed, Shelves (DRAFT), About (method, opt-out, COI), Coverage, and a weekly RSS digest with real dates.
- **Ops:** `make build`/`test`/`refresh`, pytest, and a manual-only GitHub Action. The YouTube key now comes from env (`YOUTUBE_API_KEY`); without one it falls back to oEmbed. The PM corpus is parked.

**Measured:** see `corpus/stats.json` and `/coverage` for counts at build time.
