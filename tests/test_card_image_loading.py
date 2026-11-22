from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_card_thumbnail_variants_cap_verified_maxres_and_keep_fallback_metadata():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { CARD_THUMB_SIZES, thumbCandidates, thumbFor, thumbSrcset, thumbUrl } from './site/src/lib/format.mjs';
import { card } from './site/src/lib/myspace-card.mjs';

const id = 'aAb7hSCtvGw';
assert.equal(thumbFor({ id, thumb: thumbUrl(id, 'maxresdefault'), thumb_verified: true }), thumbUrl(id, 'hqdefault'));
assert.equal(thumbFor({ id, thumb: thumbUrl(id, 'mqdefault') }), thumbUrl(id, 'mqdefault'));
assert.deepEqual(thumbCandidates(id), [thumbUrl(id, 'hqdefault'), thumbUrl(id, 'mqdefault')]);
assert.equal(thumbSrcset(id), `${thumbUrl(id, 'mqdefault')} 320w, ${thumbUrl(id, 'hqdefault')} 480w, ${thumbUrl(id, 'sddefault')} 640w`);
assert.ok(CARD_THUMB_SIZES.includes('1600px') && CARD_THUMB_SIZES.includes('1300px'));
const html = card({ id, title: 'Card', channel: 'Channel', duration_seconds: 61 }, `/v/${id}/`);
assert.ok(html.includes('srcset='));
assert.ok(html.includes('sizes='));
assert.ok(html.includes('data-thumb-id="aAb7hSCtvGw"'));
assert.ok(html.includes(`href="/v/${id}/"`));
assert.ok(!html.includes('maxresdefault'));
'''], cwd=ROOT, check=True)


def test_initial_grid_prioritizes_only_first_eight_and_later_cards_stay_lazy():
    source = (ROOT / 'site/src/components/VideoPage.astro').read_text(encoding='utf-8')
    assert 'pageVideos.map((v, index)' in source
    assert "loading={index < 8 ? 'eager' : 'lazy'}" in source
    assert "fetchpriority={index < 8 ? 'high' : undefined}" in source
    assert 'srcset={thumbSrcset(v)}' in source
    assert 'sizes={CARD_THUMB_SIZES}' in source
    assert 'loading="lazy" src="${esc(thumbFor(video))}" srcset="${esc(thumbSrcset(video))}"' in source


def test_small_avatars_and_media_preconnects_are_low_priority():
    avatar = (ROOT / 'site/src/components/ChannelAvatar.astro').read_text(encoding='utf-8')
    page = (ROOT / 'site/src/components/VideoPage.astro').read_text(encoding='utf-8')
    layout = (ROOT / 'site/src/components/Layout.astro').read_text(encoding='utf-8')
    assert "size === 'sm' ? '=s88'" in avatar
    assert 'Math.max' not in avatar
    assert "loading={size === 'sm' ? 'lazy' : undefined}" in avatar
    assert "const smallAvatar = value => String(value || '').replace(/=s\\d+/, '=s88');" in page
    assert '<img class="channel-avatar" loading="lazy"' in page
    assert '<link rel="preconnect" href="https://i.ytimg.com"/>' in layout
    assert '<link rel="preconnect" href="https://yt3.ggpht.com"/>' in layout


def test_click_to_play_and_audio_filter_newness_sources_remain_wired():
    detail = (ROOT / 'site/src/pages/v/[id].astro').read_text(encoding='utf-8')
    audio_index = (ROOT / 'site/src/components/AudioPodcastIndex.astro').read_text(encoding='utf-8')
    audio_newness = (ROOT / 'site/src/lib/audio-podcast-newness.mjs').read_text(encoding='utf-8')
    initial_html = detail.split('</Layout>', 1)[0]
    assert 'data-player-load' in detail
    assert '<iframe' not in initial_html
    assert "const STANDARD_EMBED_HOST = 'www.youtube.com';" in detail
    assert 'data-category-filters' in audio_index
    assert 'data-audio-newness-dot' in audio_index
    assert 'applyAudioNewnessDots' in audio_index
    assert 'latestEpisodeMarker' in audio_newness
