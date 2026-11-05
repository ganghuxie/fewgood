# Long Echo · HN × YouTube

Phase 1: discover YouTube videos repeatedly linked by independent Hacker News users over time. Views and likes are stored in the metadata cache but never used for selection or sorting. Reddit, sentiment analysis, AI classification and scheduled updates are outside this phase.

## Setup and full run

Python 3.10+ and Node 22+ are required. From this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
npm ci --prefix site
# Set YOUTUBE_API_KEY securely in your environment before enrichment.
python -m pytest -q
python -m ytrec all
python -m http.server 8000 --directory site/dist
```

Open http://localhost:8000. Nothing is deployed. The full crawl defaults to 2007-01-01 through the current UTC time and can take many hours. A key is only required when eligible uncached candidates exist. No fabricated seed videos are provided; a small smoke crawl will usually select zero videos.

Individual stages / explicit date range:

```bash
python -m ytrec crawl --start 2024-01-01 --end 2024-01-08
python -m ytrec extract
python -m ytrec aggregate
python -m ytrec enrich
python -m ytrec report
python -m ytrec build-site
```

`all` runs crawl → extract → aggregate → enrich → report → Astro build. `build-site` regenerates the report/data before building. `aggregate` also writes `data/aggregates.json`. All commands accept `--config PATH`. Dates are inclusive start / exclusive end, UTC ISO dates or timestamps. Use `--refresh-metadata` with `enrich` or `all` to refresh eligible cached videos; otherwise the metadata cache expires after 30 days. Build/report do not contact YouTube; rerun enrichment to check availability.

## Criteria

Edit `config.yaml`: defaults require 5 distinct HN authors, 6 distinct UTC calendar months and a 365-day earliest/latest gap. Metadata must show public, processed, published at least 365 days ago and at least 300 seconds long. The source rule retains `min_sources: 2` but is disabled; enabling it excludes all Phase 1 HN-only candidates. Sentiment is explicitly disabled; attempting to enable it raises an error rather than silently claiming to analyze sentiment.

A link is only a proxy for a recommendation: criticism and incidental links can qualify until phase 2. One author counts once toward the people threshold, while all of that author's dated mentions contribute to temporal coverage. Thus months measure repeated linking, not necessarily six different endorsers. Authors without an identity are excluded. HN usernames are the independence proxy; account coordination cannot be ruled out.

## Storage and resuming

`data/ytrec.sqlite` stores original HN JSON, completed windows, normalized per-item video mentions, cached YouTube responses (including unavailable IDs), approximate quota units and first selection timestamps. Stories and comments are searched separately for `youtube.com`, `youtu.be` and `youtube-nocookie.com`, including story URL fields. HTML entities and attribution links are decoded. A unique `(video_id,item_id)` prevents duplicate query hits; aggregation counts distinct `(video_id,author)` pairs.

HN uses half-open timestamp windows, at most 1000 hits per response, and recursively splits windows if counts exceed retrievable results. A window is complete only after all children or all returned hits are persisted. Rerunning the same range skips finished windows; crash recovery may refetch an unfinished request but never duplicate stored mentions. An irreducible one-second overflow fails visibly. Changing range boundaries can refetch overlapping windows safely. Already completed historical windows are snapshots; use a separate database/config for a fresh historical recrawl if HN edits/deletions matter.

Requests start at least one second apart, including retries; 429/5xx and transport failures use bounded exponential backoff. YouTube requests batch 50 IDs and fetch only recommendation candidates, never the relaxed what-if pool. Each attempted YouTube request records an approximate quota unit, including retries. `max_units_per_run` limits each enrichment run (seven units reserved for retries); provider daily quota remains authoritative. Failed batches remain pending. Exceptions suppress request details so API keys cannot leak through HTTP exception URLs. Secrets are read only from the environment; no .env loader is used.

## Outputs

- `reports/report.json`: complete metrics, effective config and 18 what-if settings.
- `reports/report.md`: human-readable summary and what-if table.
- `site/src/data/videos.json`: selected videos, quotes, metrics, report snapshot.
- `site/dist/`: static Astro site, thumbnails, 2–3 quotes when available, HN links and client-side people/newest-selected sort. Selection timestamps record the first successful report inclusion.

Gate drop counts are independent and can overlap. Metadata-unavailable includes missing cache entries and API-confirmed unavailable/private/unprocessed videos. What-if rows report recommendation candidates, selected with cached metadata, and uncached unknowns separately; they are lower bounds, not estimates of unknown outcomes. The defaults are never relaxed to reach 100. All passing videos are displayed, with actual count even below or above 100.

Tests cover URL forms and negatives, adaptive splitting/resume, author/month dedupe, gate boundaries, metadata candidate filtering/cache, and report output. Live smoke verification is recorded in `reports/smoke.md`; its database and built output are ignored by git.

API references: [HN search API](https://hn.algolia.com/api), [YouTube videos.list](https://developers.google.com/youtube/v3/docs/videos/list) (one unit per request). This is a discovery aid, not an endorsement guarantee.
