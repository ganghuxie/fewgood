"""Verified official cover-rendition policy for the audio podcast pages."""

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_cover_variants_are_limited_to_verified_official_hosts_and_slots():
    subprocess.run(['node', '--input-type=module', '-e', r'''
import assert from 'node:assert/strict';
import {
  CARD_COVER_SIZES,
  CARD_COVER_WIDTHS,
  SMALL_COVER_WIDTH,
  coverDisplayUrl,
  coverSrcset,
} from './site/src/lib/audio-podcast-covers.mjs';

const xyz = 'https://image.xyzcdn.net/FrJquLUC5yZR0tQrShVB857O8J8g.jpg';
assert.equal(coverDisplayUrl(xyz, { width: 320 }), `${xyz}?imageView2/2/w/320`);
assert.equal(coverDisplayUrl(`${xyz}?token=ok`, { width: 640 }), `${xyz}?token=ok&imageView2/2/w/640`);
assert.equal(coverDisplayUrl(`${xyz}?imageView2/2/w/320`, { width: 640 }), `${xyz}?imageView2/2/w/320`);
assert.equal(coverDisplayUrl(`${xyz}?imageMogr2/thumbnail/320x`, { width: 640 }), `${xyz}?imageMogr2/thumbnail/320x`);
assert.equal(coverDisplayUrl('https://cdn.example.net/a.jpg', { width: 320 }), 'https://cdn.example.net/a.jpg');
assert.equal(coverDisplayUrl('http://image.xyzcdn.net/a.jpg', { width: 320 }), 'http://image.xyzcdn.net/a.jpg');

assert.deepEqual(CARD_COVER_WIDTHS, [320, 640, 960]);
assert.equal(CARD_COVER_SIZES, '(min-width: 1280px) 25vw, (min-width: 600px) 50vw, 92vw');
assert.equal(SMALL_COVER_WIDTH, 320);
assert.equal(
  coverSrcset(xyz, CARD_COVER_WIDTHS),
  `${xyz}?imageView2/2/w/320 320w, ${xyz}?imageView2/2/w/640 640w, ${xyz}?imageView2/2/w/960 960w`,
);
assert.equal(coverDisplayUrl(xyz, { width: 640 }), `${xyz}?imageView2/2/w/640`);

const storages = 'https://fdfs.xmcdn.com/storages/abc/cover.jpg';
const group = 'https://fdfs.xmcdn.com/group53/M00/cover.jpg';
const rendition = path => `https://imagev2.xmcdn.com${path}!op_type=5&upload_type=album&device_type=ios&name=mobile_large&magick=png`;
assert.equal(coverDisplayUrl(storages, { width: 320 }), rendition('/storages/abc/cover.jpg'));
assert.equal(coverDisplayUrl(group, { width: 320 }), rendition('/group53/M00/cover.jpg'));
assert.equal(coverDisplayUrl(storages, { width: 640 }), storages); // cards retain the high-DPR source
assert.equal(coverSrcset(storages, CARD_COVER_WIDTHS), undefined);
for (const original of [
  'https://static2.ximalaya.com/css/cover.jpg',
  'https://imagev2.xmcdn.com/storages/abc/cover.jpg',
  'https://fdfs.xmcdn.com/not-storages/cover.jpg',
  'https://fdfs.xmcdn.com/group53/M00/cover.jpg?bad=query',
  'https://fdfs.xmcdn.com/group53/M00/cover.jpg!op_type=5',
]) assert.equal(coverDisplayUrl(original, { width: 320 }), original);

for (const original of [
  'https://cdn.fireside.fm/file/cover.jpg',
  'https://wavpub.example/cover.jpg',
  'https://cdn.vistopia.com.cn/cover.jpg',
]) assert.equal(coverDisplayUrl(original, { width: 320 }), original);
'''], cwd=ROOT, check=True)


def test_audio_cover_markup_falls_back_to_original_urls_without_mutating_metadata():
    index = (ROOT / 'site/src/components/AudioPodcastIndex.astro').read_text(encoding='utf-8')
    show = (ROOT / 'site/src/components/AudioPodcastShowPage.astro').read_text(encoding='utf-8')
    fallback = "this.removeAttribute('srcset');this.src=original;"

    assert 'data-cover-original={coverUrl}' in index
    assert 'srcset={coverSrcset(coverUrl, CARD_COVER_WIDTHS)}' in index
    assert 'sizes={CARD_COVER_SIZES}' in index
    assert fallback in index
    assert 'data-cover-original={showCoverUrl}' in show
    assert 'data-cover-original={coverUrl}' in show
    assert fallback in show
    assert 'this.hidden=true;' in index and 'this.hidden=true;' in show

    metadata = json.loads((ROOT / 'site/src/data/audio_podcast.json').read_text(encoding='utf-8'))
    cover_urls = [
        url
        for show_data in metadata['shows']
        for url in [show_data.get('feed', {}).get('cover_url'), *(episode.get('cover_url') for episode in show_data.get('episodes', []))]
        if url
    ]
    assert cover_urls
    assert all('imageView2/2/w/' not in url and 'name=mobile_large' not in url for url in cover_urls)
