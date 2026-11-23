import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_click_to_play_samples_keep_no_initial_iframe_and_dynamic_fill_style():
    detail = (ROOT / 'site/src/pages/v/[id].astro').read_text(encoding='utf-8')
    initial_html = detail.split('</Layout>', 1)[0]
    catalog = json.loads((ROOT / 'site/src/data/catalog.json').read_text(encoding='utf-8'))
    assert '<iframe' not in initial_html
    assert 'data-player-load' in detail
    assert "frame.width = '1280'; frame.height = '720';" in detail
    assert "frame.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;border:0;'" in detail
    assert "loadEmbed(detail, button.dataset.videoId, { autoplay: true })" in detail
    assert "params.set('autoplay', '1')" in detail
    sample_videos = [video for video in catalog if isinstance(video, dict) and video.get('id')][:2]
    assert len(sample_videos) == 2, 'catalog should provide current click-to-play samples'
    assert all(isinstance(video['id'], str) and video['id'] for video in sample_videos)
    assert 'data-video-id={video.id}' in detail


def test_hero_images_are_separate_from_card_thumbnail_policy():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { heroThumbFor, thumbFor, thumbUrl } from './site/src/lib/format.mjs';
const video = { id: 'uHjd6nwwEWI', thumb_verified: true, thumb: thumbUrl('uHjd6nwwEWI', 'maxresdefault') };
assert.equal(thumbFor(video), thumbUrl(video.id, 'hqdefault'));
assert.equal(heroThumbFor(video), thumbUrl(video.id, 'maxresdefault'));
assert.equal(heroThumbFor({ id: video.id }), thumbUrl(video.id, 'hqdefault'));
'''], cwd=ROOT, check=True)
    detail = (ROOT / 'site/src/pages/v/[id].astro').read_text(encoding='utf-8')
    assert 'const shareImage = heroThumbFor(primary.video);' in detail
    assert 'class="player-poster" src={heroThumbFor(video)}' in detail


def test_audio_player_only_unwraps_the_verified_ximalaya_media_target():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { playbackAudioUrl } from './site/src/lib/audio-podcast-media.mjs';
const target = 'https://aod.cos.tx.xmcdn.com/storages/5026-audiofreehighqps/D8/63/GKwRIW4O1H-MA4f1ygT9ypDx.m4a';
const jumper = 'https://jt.ximalaya.com//GKwRIW4O1H-MA4f1ygT9ypDx.m4a?channel=rss&jt=' + encodeURIComponent(target);
assert.equal(playbackAudioUrl(jumper), target);
assert.equal(playbackAudioUrl('https://jt.ximalaya.com/a.m4a?jt=https%3A%2F%2Fevil.example%2Fa.m4a'), 'https://jt.ximalaya.com/a.m4a?jt=https%3A%2F%2Fevil.example%2Fa.m4a');
assert.equal(playbackAudioUrl('https://cdn.fireside.fm/file/example.mp3'), 'https://cdn.fireside.fm/file/example.mp3');
'''], cwd=ROOT, check=True)
    page = (ROOT / 'site/src/components/AudioPodcastEpisodePage.astro').read_text(encoding='utf-8')
    assert 'const playbackUrl = playbackAudioUrl(audioUrl);' in page
    assert 'data-audio-url={playbackUrl}' in page


def test_audio_cover_loading_preserves_official_sources_and_prioritizes_only_recent_cards():
    index = (ROOT / 'site/src/components/AudioPodcastIndex.astro').read_text(encoding='utf-8')
    assert "loading={index < 4 ? 'eager' : 'lazy'}" in index
    assert "fetchpriority={index < 4 ? 'high' : undefined}" in index
    assert 'width="320" height="320" decoding="async"' in index
    assert 'src={coverDisplayUrl(coverUrl, { width: 640 })}' in index
    assert 'srcset={coverSrcset(coverUrl, CARD_COVER_WIDTHS)}' in index
    assert 'data-cover-original={coverUrl}' in index
