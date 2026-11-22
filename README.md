# TCGTube

**The YouTube videos the trading-card-game community keeps telling each other to watch.** It's an algorithm-free index mined from Reddit, inspired by Karpathy's [HackerTube](https://hackertube.org/). Magic, Pokémon, Yu-Gi-Oh!, Flesh and Blood, Lorcana and One Piece.

*Name is a placeholder. Target domain `vault.tmrss.co` is not deployed.*

## How a video gets in

1. **Mine** (`pipeline/mine_arctic.py`): finds every Reddit comment linking a YouTube video in the TCG subreddits listed in `config/tcg.yaml`, via the [Arctic Shift](https://arctic-shift.photon-reddit.com) API (no key; paced and resumable). If you have Watchful1 dumps locally, `pipeline/mine.py` does the same job from them.
2. **Classify** (`pipeline/classify.py`): labels each comment's stance: recommend / cite / joke / criticize / self_promo / bot.
   - The heuristic rules work today with no key.
   - Set `TCGTUBE_LLM_PROVIDER=openai|anthropic` plus `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` for LLM labels (cached in `data/classify_cache.jsonl`).
3. **Rank** (`pipeline/aggregate.py`), using the HackerTube rule: **≥3 distinct people in ≥3 distinct months**, ranked by distinct months.
   - Filters out bots, `[deleted]` authors, self-links (the commenter is the channel, or a "channel promoter"), jokes and criticism, music and memes, Shorts, dead videos and the deny-list.
   - Excludes Tom's own channel (conflict-of-interest rule).
   - Normalises per game (score ÷ p90 of that game).
   - Picks a "why" from 2–3 short quotes with permalinks.
4. **Taxonomy** (`pipeline/taxonomy.py`): rules-based game → format → type → level → shelf life. Shelf life is rotation-aware: deck techs, set reviews and finance videos become *dated* after 2 years unless people are still recommending them.
5. **Enrich** (`pipeline/enrich.py`):
   - With `YOUTUBE_API_KEY`: Data API (duration, publish date, views, category).
   - Without a key: YouTube oEmbed (title and channel only, so durations and dates show as "—" for those videos).
6. **Build** (`pipeline/build_site.py`): a static site.
   - Index with filters, search, pagination and URL state.
   - Per-video pages with a click-to-load youtube-nocookie embed, quoted vouches and "also recommended".
   - Shelves, About, Coverage.
   - A weekly "newly qualified" RSS feed with real dates.

## Run it

```sh
make build      # rank (if data/ has raw vouches) + build site/ ; from a fresh clone builds from committed corpus/
make serve      # http://localhost:8000
make test       # pytest
make mine       # full Arctic Shift mine (hours the first time, resumable)
make refresh    # weekly: re-mine last 2 months, rank, build (scripts/refresh.sh)
```

- `.github/workflows/refresh.yml` is **manual-dispatch only**. It never deploys or pushes; it uploads the built site as an artifact.
- Deploying is a human decision (`npx wrangler deploy` with `wrangler.jsonc`).

## What's committed

- `corpus/videos.json`: the public dataset. Video IDs, public YouTube metadata, counts, taxonomy, and up to 3 quotes of ≤200 chars each with Reddit permalinks. **No usernames, no comment bodies.**
- `corpus/coverage.json`, `corpus/stats.json`: what was mined and what was filtered.
- `config/shelves.yaml`: curated shelves (currently DRAFT, auto-seeded picks for Tom to edit).
- Raw vouches (`data/`, which includes usernames for counting distinct people) and the built `site/` are gitignored.

Note: commits before v2 (`c4a75e8` and earlier) contain `site/tcg/data.js` with raw Reddit snippets. History was not rewritten.

## Keys (all optional)

| Env | Effect without it |
|---|---|
| `YOUTUBE_API_KEY` | New videos get oEmbed metadata only: no duration (length filter skips them), no publish date. |
| `TCGTUBE_LLM_PROVIDER` + `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` | Stance labels come from heuristics, so expect more false "cite"s and the occasional joke getting through. |

The PM corpus is parked (`config/pm.yaml.parked`). Build log: [`docs/BUILD-LOG.md`](docs/BUILD-LOG.md).

MIT. See [LICENSE](LICENSE). The data is Reddit users' and YouTube creators'; this project is non-commercial, and the About page has the opt-out.
