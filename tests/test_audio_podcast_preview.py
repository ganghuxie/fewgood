import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')


@pytest.mark.skipif(NODE is None, reason='node is required for the static preview helper test')
def test_audio_preview_routes_and_pagination_are_latest_first():
    script = r'''
import assert from 'node:assert/strict';
import {
  PAGE_SIZE,
  episodeAnchor,
  episodePath,
  pageCount,
  previewPath,
  showPath,
  sliceEpisodePage,
} from './site/src/lib/audio-podcast.mjs';

assert.equal(PAGE_SIZE, 20);
assert.equal(previewPath(), '/audio-podcast/');
assert.equal(showPath('story-fm'), '/audio-podcast/story-fm/');
assert.equal(showPath('story-fm', 2), '/audio-podcast/story-fm/page/2/');
assert.equal(showPath('story-fm', 2, '/base'), '/base/audio-podcast/story-fm/page/2/');
assert.equal(pageCount(0), 1);
assert.equal(pageCount(20), 1);
assert.equal(pageCount(21), 2);
assert.equal(pageCount(1001), 51);

const episodes = Array.from({ length: 45 }, (_, index) => ({
  episode_id: `episode-${index}`,
  published_at: new Date(Date.UTC(2026, 0, 1, 0, 0, index)).toISOString(),
}));
const first = sliceEpisodePage(episodes, 1);
const second = sliceEpisodePage(episodes, 2);
const third = sliceEpisodePage(episodes, 3);
assert.equal(first.length, 20);
assert.equal(first[0].episode_id, 'episode-44');
assert.equal(first[19].episode_id, 'episode-25');
assert.equal(second[0].episode_id, 'episode-24');
assert.equal(second[19].episode_id, 'episode-5');
assert.equal(third.length, 5);
assert.equal(third[0].episode_id, 'episode-4');
assert.equal(third[4].episode_id, 'episode-0');

const show = { slug: 'story-fm', episodes };
assert.equal(
  episodePath(show, episodes[20]),
  `/audio-podcast/story-fm/episode-20/`,
);
console.log('audio preview helper checks ok');
'''
    subprocess.run(
        [NODE, '--input-type=module', '-e', script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_video_podcast_nav_label_preserves_audio_label_and_routes():
    brand = (ROOT / 'site/src/lib/brand.mjs').read_text(encoding='utf8')
    match = re.search(r'export const SECTION_LABELS = \{([^}]*)\};', brand, re.S)
    assert match, 'SECTION_LABELS declaration not found'
    labels = dict(re.findall(r"(\w+): '([^']+)'", match.group(1)))
    assert labels == {
        'picks': '精选',
        'trending': '趋势',
        'ai': 'AI前沿',
        'podcast': '视频播客',
        'music': '音乐',
        'community': '社区推荐',
    }

    header = (ROOT / 'site/src/components/Header.astro').read_text(encoding='utf8')
    for route in ("'/'", "'/trending/'", "'/ai/'", "'/podcast/'", "'/music/'", "'/community/'"):
        assert route in header
    assert "href={link('/podcast/')}>{SECTION_LABELS.podcast}</a>" in header
    assert "href={link('/audio-podcast/')}" in header
    assert '>音频播客</a>' in header
    assert "active === 'audio-podcast'" in header
    assert 'audio-podcast-preview' not in header


def test_audio_player_markup_keeps_click_only_playback_and_no_download():
    component = (ROOT / 'site/src/components/AudioPodcastEpisodePage.astro').read_text(encoding='utf8')
    assert 'preload="none"' in component
    assert 'controlsList="nodownload"' in component
    assert 'autoplay' not in component.lower()
    assert 'data-audio-source' in component
    assert 'initAudioPodcastPlayers' in component


@pytest.mark.skipif(NODE is None, reason='node is required for the audio player tests')
def test_audio_player_pending_error_retry_and_pause_others_are_hermetic():
    script = r'''
import assert from 'node:assert/strict';
import {
  PLAYER_LOADING_TEXT,
  PLAYER_PLAY_TEXT,
  PLAYER_RETRY_TEXT,
  initAudioPodcastPlayers,
} from './site/src/lib/audio-podcast-player.mjs';

class FakeTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type, listener) {
    this.listeners.get(type)?.delete(listener);
  }

  emit(type) {
    for (const listener of [...(this.listeners.get(type) || [])]) listener({ type });
  }
}

class FakeElement extends FakeTarget {
  constructor() {
    super();
    this.attributes = new Map();
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.textContent = '';
    this.src = null;
  }

  setAttribute(name, value) {
    const text = String(value);
    this.attributes.set(name, text);
    if (name === 'src') this.src = text;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === 'src') this.src = null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }
}

class FakeAudio extends FakeElement {
  constructor(playImpl) {
    super();
    this.paused = true;
    this.playCalls = 0;
    this.pauseCalls = 0;
    this.loadCalls = 0;
    this.playImpl = playImpl;
  }

  play() {
    this.playCalls += 1;
    return this.playImpl(this);
  }

  pause() {
    this.pauseCalls += 1;
    this.paused = true;
  }

  load() {
    this.loadCalls += 1;
  }
}

function makePlayer(playImpl, url) {
  const audio = new FakeAudio(playImpl);
  const button = new FakeElement();
  const errorBox = new FakeElement();
  const sourceLink = new FakeElement();
  errorBox.hidden = true;
  sourceLink.hidden = true;
  const elements = {
    '[data-audio]': audio,
    '[data-audio-play]': button,
    '[data-audio-error]': errorBox,
    '[data-audio-source]': sourceLink,
  };
  const root = {
    dataset: { audioUrl: url },
    querySelector(selector) {
      return elements[selector] || null;
    },
  };
  return { root, audio, button, errorBox, sourceLink, url };
}

const never = () => new Promise(() => {});
const reject = () => Promise.reject(new Error('playback rejected'));
const succeed = audio => {
  audio.paused = false;
  audio.emit('play');
  return Promise.resolve();
};
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

{
  const player = makePlayer(never, 'https://tk.wavpub.com/official.mp3?token=abc');
  const [controller] = initAudioPodcastPlayers([player.root]);
  assert.equal(player.audio.playCalls, 0, 'must not autoplay');
  assert.equal(player.audio.hasAttribute('src'), false, 'src must wait for click');
  player.button.emit('click');
  assert.equal(player.audio.src, player.url, 'official enclosure must be set verbatim');
  assert.equal(controller.pending, true);
  assert.match(player.button.textContent, /加载中/);
  assert.equal(player.button.hidden, false);
  assert.equal(player.audio.hidden, false);
  assert.equal(player.audio.paused, true, 'pending must not present a playing state');
  assert.equal(player.errorBox.hidden, true);
  assert.equal(PLAYER_LOADING_TEXT, player.button.textContent);

  await wait(30);
  assert.equal(controller.pending, true, 'long loading must remain pending');
  assert.equal(player.errorBox.hidden, true, 'long loading must not auto-error');
  assert.equal(player.audio.playCalls, 1, 'loading must not auto-retry');
}

for (const [label, playImpl, fail] of [
  ['reject', reject, () => {}],
  ['error event', never, player => player.audio.emit('error')],
]) {
  const player = makePlayer(playImpl, 'https://www.ximalaya.com/official.m4a?jt=https://cdn.example.test/a.m4a');
  const [controller] = initAudioPodcastPlayers([player.root]);
  player.button.emit('click');
  fail(player);
  await tick();
  assert.equal(controller.pending, false, `${label} must leave pending`);
  assert.equal(player.audio.paused, true, `${label} must not remain playing`);
  assert.equal(player.audio.hidden, true, `${label} must hide audio`);
  assert.equal(player.audio.hasAttribute('src'), false, `${label} must drop src`);
  assert.equal(player.button.hidden, false);
  assert.equal(player.button.textContent, PLAYER_RETRY_TEXT);
  assert.equal(player.errorBox.hidden, false);
  assert.equal(player.sourceLink.hidden, false);
  const callsAfterFailure = player.audio.playCalls;
  await wait(30);
  assert.equal(player.audio.playCalls, callsAfterFailure, `${label} must not auto-retry`);
}

{
  const first = makePlayer(succeed, 'https://feeds.example.test/first.mp3');
  const second = makePlayer(never, 'https://feeds.example.test/second.mp3');
  const [firstController, secondController] = initAudioPodcastPlayers([first.root, second.root]);
  first.button.emit('click');
  await tick();
  assert.equal(firstController.pending, false);
  assert.equal(first.audio.paused, false);
  assert.equal(first.button.hidden, true);

  second.button.emit('click');
  assert.equal(first.audio.paused, true, 'starting another player must pause the first');
  assert.ok(first.audio.pauseCalls >= 1);
  assert.equal(secondController.pending, true);
  assert.equal(second.audio.src, second.url);
}

{
  const first = makePlayer(never, 'https://tk.wavpub.com/slow.mp3');
  const second = makePlayer(succeed, 'https://jt.ximalaya.com//ok.m4a?jt=https://cdn.example.test/ok.m4a');
  const [firstController, secondController] = initAudioPodcastPlayers([first.root, second.root]);
  first.button.emit('click');
  assert.equal(firstController.pending, true);
  assert.match(first.button.textContent, /加载中/);

  second.button.emit('click');
  await tick();
  assert.equal(firstController.pending, false, 'starting another player must cancel the first pending load');
  assert.equal(first.audio.paused, true, 'cancelled pending player must not start playing later');
  assert.equal(first.audio.hidden, true);
  assert.equal(first.button.textContent, PLAYER_PLAY_TEXT);
  assert.equal(first.errorBox.hidden, true, 'switching players is not a playback error');
  assert.equal(secondController.pending, false);
  assert.equal(second.audio.paused, false);
  await wait(20);
  assert.equal(first.audio.paused, true);
  assert.equal(first.audio.playCalls, 1, 'cancelled pending player must not auto-retry');
}

console.log('audio player checks ok');
'''
    subprocess.run(
        [NODE, '--input-type=module', '-e', script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_loader_missing_invalid_and_malformed_data_are_safe(tmp_path):
    invalid = tmp_path / 'invalid.json'
    invalid.write_text('{broken')
    malformed = tmp_path / 'malformed.json'
    malformed.write_text('{"shows":[null],"recent_selection":{}}')
    script = '''
import assert from 'node:assert/strict';
import { loadAudioPodcastData } from './site/src/lib/audio-podcast.mjs';
for (const file of process.argv.slice(1)) {
  const data = loadAudioPodcastData(file);
  assert.equal(data.available, false);
  assert.deepEqual(data.shows, []);
  assert.deepEqual(data.recent_selection.items, []);
  assert.match(data.unavailable_message, /当前音频目录暂不可用/);
}
'''
    subprocess.run([NODE, '--input-type=module', '-e', script,
                    str(tmp_path / 'missing.json'), str(invalid), str(malformed)], cwd=ROOT, check=True)


def test_production_layout_retains_standard_shell():
    layout = (ROOT / 'site/src/components/AudioPodcastLayout.astro').read_text()
    assert "import Layout from './Layout.astro'" in layout
    assert 'active="audio-podcast"' in layout
    assert '测试预览' not in layout
    assert 'noindex' not in layout
    assert not (ROOT / 'site/src/pages/audio-podcast-preview').exists()


def test_refresh_audio_hook_failure_is_nonfatal(monkeypatch):
    import inspect
    from ytrec import __main__ as cli, audio_podcast
    calls = []
    monkeypatch.setattr(audio_podcast, 'ingest', lambda: calls.append('ingest'))
    cli.refresh_audio_podcasts()
    assert calls == ['ingest']
    def fail():
        raise OSError('RSS unavailable')
    monkeypatch.setattr(audio_podcast, 'ingest', fail)
    cli.refresh_audio_podcasts()
    source = inspect.getsource(cli.refresh)
    assert source.index('refresh_audio_podcasts()') < source.index("['npm', 'run', 'build']")


def test_stable_route_ids_are_safe_unique_and_escape_unsafe_guids():
    subprocess.run([NODE, '--input-type=module', '-e', r'''
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {episodeRouteId, episodeEntries, episodePath, loadAudioPodcastData} from './site/src/lib/audio-podcast.mjs';
for (const guid of ['https://a.test/路径?a=1&b=2', '../', '.', '..', 'page', '罕见龘', 'a'.repeat(500), 'ep-abc']) {
 const id = episodeRouteId({guid});
 assert.match(id, /^[A-Za-z0-9._-]{1,96}$/);
 assert.equal(id, 'ep-' + createHash('sha256').update(guid).digest('hex'));
 assert.equal(id, episodeRouteId({guid, episode_id:'different'}));
 assert.equal(decodeURIComponent(encodeURIComponent(id)), id);
}
assert.equal(episodeRouteId({episode_id:'xmly_track_123'}), 'xmly_track_123');
assert.notEqual(episodeRouteId({guid:'https://a/b'}), episodeRouteId({guid:'https://a:b'}));
assert.throws(() => episodeEntries({slug:'s',episodes:[{guid:'a'},{guid:'a'}]}), /Duplicate/);
for (const show of loadAudioPodcastData().shows) {
 const entries = episodeEntries(show);
 assert.equal(new Set(entries.map(e=>e.id)).size, show.episodes.length);
 for (const {episode,id} of entries) assert.equal(episodePath(show,episode), `/audio-podcast/${show.slug}/${id}/`);
}
'''], cwd=ROOT, check=True)


def test_list_detail_and_index_information_architecture():
    show = (ROOT / 'site/src/components/AudioPodcastShowPage.astro').read_text()
    detail = (ROOT / 'site/src/components/AudioPodcastEpisodePage.astro').read_text()
    index = (ROOT / 'site/src/components/AudioPodcastIndex.astro').read_text()
    assert 'data-audio-player' not in show
    assert 'description_html' not in show
    assert 'episodePath(show, episode, base)' in show
    assert detail.count('data-audio-player data-audio-url') == 1
    assert 'set:html={displayNotes(episode.description_html, episode.description_text)}' in detail
    assert 'description_missing' in detail and 'description_truncated' in detail
    assert 'showPath(show.slug, page, base)' in detail
    assert 'episodePath(show, episode, base)' in index
    assert 'description_text' not in index and 'description_html' not in index
    assert '<details' in index
