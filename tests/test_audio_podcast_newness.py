"""Contract tests for local-only audio episode newness indicators."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_audio_newness_marker_lifecycle_and_storage_failure():
    subprocess.run(['node', '--input-type=module', '-e', r'''
import assert from 'node:assert/strict';
import {
  FIRST_VISIT_WINDOW_DAYS, latestEpisodeMarker, markAudioShowSeen,
  shouldShowNewEpisode,
} from './site/src/lib/audio-podcast-newness.mjs';

const memory = new Map();
const storage = {getItem:key => memory.get(key) ?? null, setItem:(key, value) => memory.set(key, value)};
const now = Date.parse('2026-11-22T00:00:00Z');
const episode = (id, publishedAt) => ({guid:id, published_at_utc:publishedAt});
const show = (episodes) => ({slug:'tested-show', episodes});
const recent = latestEpisodeMarker(show([episode('first', '2026-11-15T00:00:00Z')]));
assert.equal(latestEpisodeMarker(show([])), null, 'a zero-episode show never creates a newness marker');
assert.equal(shouldShowNewEpisode(recent, {storage, now}), true, 'first visit: recent actual episode is marked');
assert.equal(markAudioShowSeen(recent, {storage}), true, 'opening the show records its actual latest episode');
assert.equal(shouldShowNewEpisode(recent, {storage, now}), false, 'opening clears the marker');

const newer = latestEpisodeMarker(show([episode('second', '2026-11-21T00:00:00Z'), episode('first', '2026-11-15T00:00:00Z')]));
assert.equal(shouldShowNewEpisode(newer, {storage, now}), true, 'a real later latest episode marks again');
const older = latestEpisodeMarker(show([episode('older', '2026-11-14T00:00:00Z')]));
assert.equal(shouldShowNewEpisode(older, {storage, now}), false, 'older episode ids never re-mark');

const noSeen = {getItem:() => null, setItem:()=>{}};
const oldFirstVisit = latestEpisodeMarker(show([episode('archive', '2026-10-01T00:00:00Z')]));
assert.equal(shouldShowNewEpisode(oldFirstVisit, {storage:noSeen, now}), false, 'first visit does not mark an old archive');
const shanghaiDateOnly = latestEpisodeMarker({slug:'date-only', episodes:[{guid:'date-only', published_at_asia_shanghai:'2026-11-21'}]});
assert.equal(shouldShowNewEpisode(shanghaiDateOnly, {storage:noSeen, now}), true, 'date-only RSS uses the site Shanghai convention');
assert.equal(FIRST_VISIT_WINDOW_DAYS, 14);
const blocked = {getItem:() => {throw new Error('blocked')}, setItem:() => {throw new Error('blocked')}};
assert.equal(shouldShowNewEpisode(recent, {storage:blocked, now}), false, 'unavailable localStorage fails closed');
assert.equal(markAudioShowSeen(recent, {storage:blocked}), false, 'unavailable localStorage does not block the page');
'''], cwd=ROOT, check=True)


def test_audio_newness_page_contracts_are_scoped_to_directory_and_show_page():
    index = (ROOT / 'site/src/components/AudioPodcastIndex.astro').read_text(encoding='utf8')
    show = (ROOT / 'site/src/components/AudioPodcastShowPage.astro').read_text(encoding='utf8')
    module = (ROOT / 'site/src/lib/audio-podcast-newness.mjs').read_text(encoding='utf8')
    layout = (ROOT / 'site/src/components/AudioPodcastLayout.astro').read_text(encoding='utf8')

    assert 'data-audio-newness-card' in index
    assert 'data-audio-newness-dot' in index
    assert 'aria-label="有新单集"' in index
    assert 'applyAudioNewnessDots()' in index
    assert 'data-audio-show-seen' in show
    assert 'markAudioShowSeen(markerFromDataset(currentShow?.dataset))' in show
    assert 'episode?.guid, episode?.episode_id, episode?.episode_link, episode?.audio_url' in module
    assert 'FIRST_VISIT_WINDOW_DAYS = 14' in module
    assert 'catch {' in module
    assert '.audio-newness-dot' in layout
