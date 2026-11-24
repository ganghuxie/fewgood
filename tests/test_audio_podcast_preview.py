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
    assert 'initAudioPodcastPlayers(roots, initAudioPodcastDebug(roots))' in component
    assert '诊断模式' not in component
    assert '复制诊断结果' not in component
    assert '← {show.display_name}</a>' in component
    assert '第 {page} 页' not in component
    assert '<p class="audio-preview-kicker"><a href={showPath(show.slug, 1, base)}>{show.display_name}</a></p>' not in component
    debug = (ROOT / 'site/src/lib/audio-podcast-debug.mjs').read_text(encoding='utf8')
    for forbidden in ('fetch(', 'sendBeacon', 'posthog', '.capture(', 'track(', 'WebSocket', 'readText('):
        assert forbidden not in debug
    analytics = (ROOT / 'site/src/scripts/analytics.js').read_text()
    assert 'if (shouldInitPostHog({ key, dnt, localHost, search: window.location.search }))' in analytics


AUDIO_PLAYER_FAKES = r'''
import assert from 'node:assert/strict';
import {
  PLAYER_LOADING_TEXT,
  PLAYER_PLAY_TEXT,
  PLAYER_RETRY_TEXT,
  initAudioPodcastPlayers,
} from './site/src/lib/audio-podcast-player.mjs';
import { initAudioPodcastDebug } from './site/src/lib/audio-podcast-debug.mjs';
import { shouldInitPostHog } from './site/src/scripts/analytics-policy.mjs';

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
    this.style = {};
  }

  append(...children) {
    this.children = children;
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
    this.error = null;
    this.networkState = 0;
    this.readyState = 0;
  }

  canPlayType(type) {
    return type.startsWith('audio/mp4') ? 'maybe' : '';
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
'''


@pytest.mark.skipif(NODE is None, reason='node is required for the audio player tests')
def test_audio_player_pending_error_retry_and_pause_others_are_hermetic():
    run_audio_player_checks(r'''
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

''')


@pytest.mark.skipif(NODE is None, reason='node is required for the audio player tests')
def test_audio_debug_query_failure_snapshots_and_copy_are_hermetic():
    run_audio_player_checks(r'''
function makeDebugPlayer(search, playImpl = never) {
  const url = 'https://cdn.example.test/private/audio.m4a?token=secret-enclosure';
  const player = makePlayer(playImpl, url);
  const panels = [];
  const clipboard = [];
  let clock = 100;
  const browser = {
    userAgent: 'Chrome/140.0.0.0',
    platform: 'Win32',
    onLine: true,
    clipboard: { writeText: async text => { clipboard.push(text); } },
  };
  player.root.after = panel => panels.push(panel);
  const options = initAudioPodcastDebug([player.root], {
    search, browser, now: () => clock,
    document: { createElement: tag => Object.assign(new FakeElement(), { tag }) },
  });
  initAudioPodcastPlayers([player.root], options);
  return { ...player, options, panels, clipboard, browser, advance: ms => { clock += ms; } };
}

const production = { key: 'production-key', dnt: false, localHost: false };
for (const search of ['', '?audio_debug', '?audio_debug=', '?audio_debug=0',
  '?audio_debug=true', '?audio_debug=01', '?audio_debug=0&audio_debug=1']) {
  const player = makeDebugPlayer(search);
  assert.equal(player.options, undefined);
  assert.equal(player.panels.length, 0);
  assert.equal(shouldInitPostHog({ ...production, search }), true);
}
for (const search of ['?audio_debug=1', '?x=y&audio_debug=1', '?audio_debug=1&audio_debug=0']) {
  assert.equal(makeDebugPlayer(search).panels.length, 1);
  assert.equal(shouldInitPostHog({ ...production, search }), false);
}
assert.equal(shouldInitPostHog(production), true);
for (const overrides of [{ key: '' }, { dnt: true }, { localHost: true }]) {
  assert.equal(shouldInitPostHog({ ...production, ...overrides }), false);
}

{
  let rejectFirst;
  const player = makeDebugPlayer('?audio_debug=1', audio => audio.playCalls === 1
    ? new Promise((_, reject) => { rejectFirst = reject; })
    : never());
  const { audio, button, browser, panels, clipboard, advance, url } = player;
  const [heading, note, copy, status, output] = panels[0].children;
  assert.equal(heading.textContent, '诊断模式');
  assert.match(note.textContent, /不会自动上传/);
  assert.equal(copy.textContent, '复制诊断结果');
  assert.equal(output.tag, 'pre');
  assert.equal(audio.playCalls, 0);
  assert.equal(audio.hasAttribute('src'), false);
  button.emit('click');
  assert.equal(audio.src, url);
  advance(3);
  audio.emit('loadstart');
  audio.networkState = 2;
  audio.readyState = 1;
  advance(7);
  rejectFirst(Object.assign(new Error('Unsupported ' + url + ' ' + 'x'.repeat(250)), {
    name: 'NotSupportedError',
  }));
  await tick();
  assert.equal(audio.src, null);
  assert.equal(audio.networkState, 0);
  assert.equal(button.textContent, PLAYER_RETRY_TEXT);
  const first = JSON.parse(output.textContent);
  assert.equal(first.sourceHostname, 'cdn.example.test');
  assert.equal(first.userAgent, browser.userAgent);
  assert.equal(first.platform, browser.platform);
  assert.equal(first.online, true);
  assert.deepEqual(first.canPlayType, {
    'audio/mp4': 'maybe', 'audio/mp4; codecs="mp4a.40.2"': 'maybe',
    'audio/aac': '', 'audio/x-m4a': '', 'audio/mpeg': '',
  });
  assert.deepEqual(first.events.map(({ type, ms }) => [type, ms]),
    [['click', 0], ['loadstart', 3], ['play-rejection', 10]]);
  const rejection = first.events.at(-1);
  assert.equal(rejection.networkState, 2);
  assert.equal(rejection.readyState, 1);
  assert.equal(rejection.playRejection.name, 'NotSupportedError');
  assert.match(rejection.playRejection.message, /^Unsupported /);
  assert.equal(rejection.playRejection.message.length, 200);
  assert.doesNotMatch(output.textContent, /https:|private\/audio|token=|secret-enclosure/);
  assert.deepEqual(clipboard, []);

  advance(45);
  button.emit('click');
  advance(12);
  browser.onLine = false;
  audio.networkState = 3;
  audio.readyState = 2;
  for (let index = 0; index < 30; index++) audio.emit('waiting');
  audio.error = { code: 4, message: 'Format failure at ' + url + ' secret-enclosure ' + 'x'.repeat(250) };
  audio.emit('error');
  assert.equal(audio.src, null);
  assert.equal(audio.error, null);
  const second = JSON.parse(output.textContent);
  assert.equal(second.online, false);
  assert.equal(second.events.length, 20);
  const failure = second.events.at(-1);
  assert.equal(failure.type, 'error');
  assert.equal(failure.attempt, 2);
  assert.equal(failure.ms, 12);
  assert.equal(failure.networkState, 3);
  assert.equal(failure.readyState, 2);
  assert.equal(failure.mediaError.code, 4);
  assert.match(failure.mediaError.message, /^Format failure/);
  assert.equal(failure.mediaError.message.length, 200);
  assert.doesNotMatch(output.textContent, /https:|private\/audio|token=|secret-enclosure/);
  assert.equal(clipboard.length, 0);
  copy.emit('click');
  await tick();
  assert.deepEqual(clipboard, [output.textContent]);
  assert.match(status.textContent, /已复制/);
  browser.clipboard = { writeText: async () => { throw new Error('denied'); } };
  copy.emit('click');
  await tick();
  assert.match(status.textContent, /手动复制/);
  assert.deepEqual(JSON.parse(output.textContent), second);
}
''')


def run_audio_player_checks(script):
    subprocess.run(
        [NODE, '--input-type=module', '-e', AUDIO_PLAYER_FAKES + script],
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
