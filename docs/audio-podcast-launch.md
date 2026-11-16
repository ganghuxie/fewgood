# 音频播客 production integration

The 15 enabled official-publisher feeds in `config/audio_podcasts.yaml` appear at
`/audio-podcast/`, `/audio-podcast/<slug>/`, and
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
items per show, newest first, without stale backfill. It is refreshed with the
existing daily pipeline; upstream failures can leave a show's snapshot stale.

Playback starts only on user action and uses the official HTTPS enclosure URL
verbatim. Audio is never downloaded, rehosted, proxied, or transcoded by this
pipeline. Publisher redirects (especially 谐星), region restrictions, and browser
codec support can delay or prevent playback; the UI keeps loading pending until
success or a real failure, then offers manual retry and an official source link.
