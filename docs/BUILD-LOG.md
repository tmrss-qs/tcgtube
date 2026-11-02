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
- Hosting: existing Cloudflare setup, subdomains `tcg.tmrss.co` / `pm.tmrss.co`. Free, push-to-deploy. A standalone domain can come later without rebuilding.
- Each corpus publishes an **RSS feed** (weekly digest of newly-vouched videos) — subscribe in Readwise Reader. Push distribution for a static site, zero ongoing cost.
- Filters: by game/topic, by content type (learning / gameplay / openings), minimum vouch count, no Shorts (<60s via API duration).
- Openings will be the thinnest category by construction — Redditors rarely vouch for opening videos. The ones they do vouch for are the legends. That's fine; it's a feature of "human vouches" as a signal, not a bug.

**Infra decisions:**

- Public repo from day one (github.com/tmrss-qs/tcgtube), MIT, no keys in the repo — YouTube API key via `.env`.
- Build on the Mac mini (M4, 24GB). Watch disk: full Arctic Shift monthly dumps are 50GB+ each — use per-subreddit files / parquet queries, not whole-month downloads.

**Naming (evolved over one evening, kept for the record):** repo briefly `vouchtube` (the signal is human *vouches*), renamed to **tcgtube** on Tom's call — name each thing after what it is. Umbrella product = **The Vault** at `vault.tmrss.co`: one domain, hub page, `/tcg` and `/pm` sections with per-section RSS. Two subdomains died in favor of one door each.

**Next:** stand up the TCG mining against the Reddit dumps → first real vouch counts → then enrichment + site.
