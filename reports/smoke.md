# Live smoke verification

Performed 2026-11-05. Only 2024-01-01 inclusive to 2024-01-08 exclusive was crawled; no long crawl was run.

Commands:

```bash
python -m pytest -q
python -m ytrec crawl --start 2024-01-01 --end 2024-01-08
python -m ytrec crawl --start 2024-01-01 --end 2024-01-08
python -m ytrec extract
python -m ytrec aggregate
python -m ytrec enrich
python -m ytrec build-site
```

- Unit tests: 34 passed, including URL normalization, host rejection, split/resume, incomplete response recovery, metadata gates/cache/batching, retry secret suppression, and report generation.
- Live HN: six completed query/tag windows, 215 stories and 562 comments; 728 distinct video IDs, 797 per-item mentions.
- Repeated crawl: no API requests needed (all windows already complete).
- Recommendation candidates and final selected: 0. A one-week sample cannot pass six months / 365 days. Defaults unchanged.
- YouTube units: 0; no candidates meant no live YouTube metadata request. YouTube batching, unavailable responses and caching were verified with fake responses in unit tests; live key validity was not tested.
- Astro static build succeeded in `site/dist`. A temporary local HTTP server served `/` with HTTP 200, the real empty state and sort control; server was stopped afterward.
- No deployment or remote git operations.

`report.json`, `report.md`, and the site JSON are real sample outputs, not long-history results. SQLite and build outputs are ignored.
