# Audio podcast design preview

Local-only work on `audio-podcast-design-preview`, based on production `5b6dafe`.
No push, deployment, DNS, CNAME, schedule, or database changes.

The index uses warm paper, ink typography, small green accents and concise recent
rows. Its same 20 selections link directly to episode details. The 15-show
directory has a separate inset panel and larger official artwork. Methodology
lives in an accessible disclosure. Show pages contain only 20 episode links per
page, newest first. Episode details own the player and publisher shownotes,
including missing/truncated notices and a link back to the correct list page.
No transcripts are generated.

Source examples:

- `/audio-podcast/`
- `/audio-podcast/yan-zhong-hua-shu/`
- `/audio-podcast/yan-zhong-hua-shu/6aafab73ac389df82734bbf3/`
- `/audio-podcast/yan-zhong-hua-shu/page/2/`

Episode route IDs use GUID, falling back to episode_id. Safe ASCII IDs up to
96 characters are preserved, except reserved `page`, dot segments, and `ep-`
prefixes. Other values become `ep-` plus the full SHA-256 hex digest of the
original identity. Reserving the prefix prevents collisions between literal
and hashed IDs. The build rejects duplicate routes within a show.

Covers come only from official RSS itunes:image or image/url HTTPS fields.
Episode covers fall back to the show cover; absent artwork stays absent.
All 15 shows have cover URLs after offline XML reparsing. Cache version 2
invalidates old parsed JSON; cached XML is reparsed without a network request.
The tracked export retains its original selection timestamp, all 20 selection
identities, and every original enclosure URL. Images are hotlinked, never
stored in source or packaged. Failed images hide without substitute artwork.

Audio styles, including muted OS-dark surfaces, are scoped to the audio section.
One audio-page-only mobile spacing rule clears the shared shell's positioned
search above the chipbar. Shared Header/Layout source and navigation labels
remain unchanged; the header remains light in dark mode.

## Local verification

```
pytest -q tests/test_audio_podcast.py tests/test_audio_podcast_preview.py tests/test_audio_design_packager.py
python3 scripts/build-audio-design-preview.py
python3 -m ytrec.crawl_links --base /fewgood-audio-podcast-preview
python3 scripts/package-audio-podcast-preview-site.py --src site/dist --dest /tmp/fewgood-audio-design-artifact --source-commit "$(git rev-parse HEAD)"
```

The helper runs `npm run build` in this worktree's site directory with the
preview PUBLIC_BASE. It temporarily moves dotenv files into a private temporary
directory, restores them in finally, and verifies their SHA-256 checksums without
printing values. It preserves the node_modules symlink.

Verified: 43 tests; 6,591 built pages; 4,879 detail pages with one click-only
player each; zero broken internal links. Packaged output has 5,131 audio HTML
pages, remapped under `/fewgood-audio-podcast-preview/audio-podcast-preview/`.
The graph audit covers all detail pages, keeps header/chipbar and player inline
scripts, strips shell/auth/analytics modules, and checks noindex, missing assets,
environment values, audio files and CNAME. Other navigation destinations are
stubbed. No artifact was deployed.

Browser checks covered index, show, episode and page 2 at 1440px and 390px in
light and dark modes: no horizontal overflow, list pages have no players,
episode pages have one, and the shared header stays white. External requests
were blocked during screenshots: cover availability and live publisher audio
playback were not tested. Existing hermetic player tests cover click-only src,
verbatim URL, long loading, error, explicit retry, pending cancellation and
preventing overlapping playback. Remote hosts can still restrict playback or
artwork by region, redirect behavior, browser codec support or publisher policy.

The authorized public preview URL remains
`https://ganghuxie.github.io/fewgood-audio-podcast-preview/audio-podcast-preview/`;
it will only reflect this design after a separate authorized deployment.
