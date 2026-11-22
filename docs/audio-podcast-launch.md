# 音频播客 production integration

The catalog configuration currently documents 40 confirmed official programs in
six categories. `玄而未决` is a confirmed psychology program, but its documented
feed URL currently redirects to HTML rather than a parseable RSS feed; it remains
directory-only until a valid public RSS feed is available. They appear at `/audio-podcast/`, `/audio-podcast/<slug>/`, and
`/audio-podcast/<slug>/page/<n>/`. Existing YouTube categories remain unchanged.

`python3 -m ytrec ingest-audio-podcasts` updates the compact, tracked
`site/src/data/audio_podcast.json`. RSS XML and parsed caches stay ignored under
`data/audio_podcast_cache/`. The existing refresh command runs this ingest before
its Astro build and stages the export through its existing `git add site/src/data`.
No additional schedule or Pages workflow is needed.

Each failed publisher uses its local parsed cache, or its previous committed
snapshot when a fresh runner has no cache. A fatal ingest error retains the old
export. Missing, invalid, or malformed exports render an explicit unavailable
catalog and produce no show routes; other sections can still build.

Recent selection uses the export generation time: last 30 days, at most two
items per non-daily show, newest first, without stale backfill. It is refreshed
with the existing daily pipeline; upstream failures can leave a show's snapshot
stale. It is a time-window view, not an episode heat ranking.

`python3 -m ytrec weekly-audio-picks` writes the separate
`site/src/data/audio_weekly_picks.json` status artifact. It intentionally writes
`skipped` with a reason while there is no compliant, stable, documented public
episode-level popularity source; it never substitutes show charts, subscriptions,
or recency for heat. `.github/workflows/weekly-audio-picks.yml` is a separate
Saturday 05:00 Asia/Shanghai configuration and does not commit, deploy, or claim
that a production schedule has been authorized.

Playback starts only on user action and uses the official HTTPS enclosure URL
verbatim. Audio is never downloaded, rehosted, proxied, or transcoded by this
pipeline. Publisher redirects (especially 谐星), region restrictions, and browser
codec support can delay or prevent playback; the UI keeps loading pending until
success or a real failure, then offers manual retry and an official source link.
