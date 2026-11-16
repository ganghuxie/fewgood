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

### t211u display revision (2026-11-16)

This remains an isolated design preview. No publishing or pushing is part of this revision.

`audio-podcast-display.mjs` parses the existing sanitized RSS HTML with parse5,
then filters siblings at display time. Raw RSS and `audio_podcast.json` are unchanged.
Only a block whose complete visible text is a recognized appendix heading
(相关播客、相关节目、推荐播客、节目推荐、相关推荐、我们还有这些播客,
with emoji/bracket/colon variants), or a new block beginning `相关播客：` /
`我们还有这些播客：` (optionally a bullet marker), starts filtering. Multi-block
wrappers never qualify as headings. Following empty blocks, numbered episode
rows, lists composed of episode titles/links, and standalone episode links are
omitted until the first unrecognized sibling or genuine HTML heading. That
boundary and all subsequent actual content remain. The same transform supplies
plain list excerpts, capped at 150 characters and visually clamped to two lines.

Intro prose, timestamps, credits, topic reading/book lists, mid-sentence mentions,
and uncertain social CTAs stay. No generic phrase replacement or blanket bullet
removal is used. Tests use verbatim stored HTML fixtures for 独树375、知行E257、
声动早咖啡, plus boundary and heading variants. Official original-notes links
remain on detail pages. Residual risk: publishers may introduce unknown headings
or unusual mixed blocks; these are deliberately retained. A numbered paragraph
immediately inside an explicit related-episode appendix may be interpreted as an
episode row. Official notes remain the complete reference.

The show masthead keeps official art and publisher; tabs switch between paginated
rows and RSS show introduction. Rows navigate to stable detail URLs, never inline
players. Detail pages retain one official HTTPS click-only player, native controls,
loading, retry and cancellation, with concise failure copy and secondary attribution.
The audio-only inline navigation adjustment scrolls the chipbar horizontally,
without changing shared Header markup or navigation labels.

Validation: 48 audio/whitelist/packager tests; isolated build with restored dotenv
checksums; full dist link crawl; packager graph and privacy audit (4,879 detail
players); browser checks at 390 and 1440 in light/dark preferences, tabs, active
chip bounds, no horizontal page overflow, and no audio src before click. External
requests were blocked during browser inspection; official image failures correctly
hide covers. Live publisher audio availability is not established by these checks.
The five supplied attachment filenames were absent at the requested locations.

Example artifact routes (under `/fewgood-audio-podcast-preview`):
- `/audio-podcast-preview/du-shu-bu-cheng-lin/`
- `/audio-podcast-preview/du-shu-bu-cheng-lin/page/2/`
- `/audio-podcast-preview/du-shu-bu-cheng-lin/6af8cc9a14d01a26f8a9e2ce/`

Packaged artifact: `/tmp/fewgood-audio-design-artifact`.
