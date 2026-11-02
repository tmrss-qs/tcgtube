# TCGTube

**Community-vouched video recommendations** — an algorithm-free index of videos that people actually recommend to each other.

YouTube's recommendation system optimizes for engagement. This project instead mines two decades of human recommendations (Reddit, HN) for YouTube links, counts which videos keep getting vouched for, filters and classifies them with an agent (LLM), and publishes a plain static site with an RSS feed. No logins, no tracking, no Shorts, no A/B-tested thumbnails — a representative frame from the middle of the video instead.

Inspired by Andrej Karpathy's [HackerTube](https://hackertube.org/). He built the HN version in a weekend and published the underlying data; his enrichment schema (`why` it gets recommended, `content_type`, `level`, `shelf_life`, tags) is this project's blueprint.

## Corpora

| Corpus | Source subreddits | Status |
|---|---|---|
| **TCG** — tcg.tmrss.co | r/magicTCG, r/EDH, r/mtgfinance, r/PokemonTCG, r/yugioh, r/lorcana, … | building |
| **PM** — pm.tmrss.co | r/ProductManagement + friends | next (same engine, different config) |

Measured reality (2026-11 probes): HN alone is too thin for PM content (~70 relevant comments ever) and for TCG (only ~47 of HackerTube's 6,454 videos are game-adjacent) — so both corpora need their own Reddit mining. Karpathy's dataset is the schema reference, not the content.

## Pipeline

1. **`pipeline/fetch_hackertube.py`** — pull the reference dataset (6,454 videos, its schema is our target format)
2. **`pipeline/mine.py`** — extract YouTube links + their vouches from Reddit dumps (Arctic Shift monthly files; the interactive API is flaky under load)
3. **`pipeline/enrich.py`** — YouTube Data API: title, channel, duration, mid-video frame (anything under 60s is dropped)
4. **`pipeline/classify.py`** — LLM classification: game/topic (MTG / Pokémon / YGO / Lorcana / FAB …), content type (learning / gameplay / opening / review / talk), level
5. **`pipeline/build_site.py`** — static site + `/rss.xml` weekly digest (subscribe in Readwise Reader or any RSS app)

## Status

Building now. The live build log — decisions, dead ends, numbers — is in [`docs/BUILD-LOG.md`](docs/BUILD-LOG.md).

## License

MIT — see [LICENSE](LICENSE).
