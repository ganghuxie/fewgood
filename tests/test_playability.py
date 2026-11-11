import json
from pathlib import Path

import pytest

from ytrec.core import metadata_gates, stamp, youtube_videos
from ytrec.playability import (
    REGION_MOST_THRESHOLD,
    backfill_playability,
    check_playability,
    filter_playable,
    playability_reason,
)


def raw(video_id='dQw4w9WgXcQ', *, privacy='public', upload='processed', embeddable=True,
        region=None, published='2020-01-01T00:00:00Z', duration='PT5M'):
    payload = {
        'id': video_id,
        'snippet': {'publishedAt': published, 'title': 'Example', 'channelTitle': 'Channel'},
        'contentDetails': {'duration': duration},
        'status': {'privacyStatus': privacy, 'uploadStatus': upload},
    }
    if embeddable is not None:
        payload['status']['embeddable'] = embeddable
    if region is not None:
        payload['contentDetails']['regionRestriction'] = region
    return payload


def test_public_embeddable_video_is_kept():
    assert playability_reason(raw()) is None


@pytest.mark.parametrize('kwargs,reason', [
    ({'embeddable': False}, 'not_embeddable'),
    ({'embeddable': 'false'}, 'not_embeddable'),
    ({'privacy': 'private'}, 'not_public'),
    ({'privacy': 'unlisted'}, 'not_public'),
    ({'upload': 'failed'}, 'not_processed'),
    ({'upload': 'deleted'}, 'not_processed'),
])
def test_status_gates(kwargs, reason):
    assert playability_reason(raw(**kwargs)) == reason


def test_missing_item_is_rejected():
    assert playability_reason(None) == 'missing'
    assert playability_reason({}) == 'missing'


def test_small_region_blocks_are_kept():
    assert playability_reason(raw(region={'blocked': ['US']})) is None
    assert playability_reason(raw(region={'blocked': ['US', 'CA']})) is None
    assert playability_reason(raw(region={'blocked': ['US'] * (REGION_MOST_THRESHOLD - 1)})) is None


def test_most_region_blocks_are_rejected():
    assert playability_reason(raw(region={'blocked': ['US'] * REGION_MOST_THRESHOLD})) == 'region_restricted'


def test_small_allowlist_is_rejected_and_large_allowlist_is_kept():
    assert playability_reason(raw(region={'allowed': ['US'] * (REGION_MOST_THRESHOLD - 1)})) == 'region_restricted'
    assert playability_reason(raw(region={'allowed': ['US'] * REGION_MOST_THRESHOLD})) is None


def test_filter_playable_counts_reasons():
    videos = [{'id': 'a'}, {'id': 'b'}, {'id': 'c'}, {'id': 'a'}]
    kept, dropped = filter_playable(videos, {'a': 'not_embeddable', 'b': None, 'c': 'missing'})
    assert kept == [{'id': 'b'}]
    assert dropped == {'not_embeddable': 2, 'missing': 1}


def test_metadata_gates_reject_embeddable_and_region_failures():
    config = {'min_publish_age_days': 365, 'min_duration_seconds': 300}
    at = stamp('2025-01-01')
    assert not any(metadata_gates(raw(), config, at).values())
    assert metadata_gates(raw(embeddable=False), config, at)['metadata_unavailable']
    assert metadata_gates(raw(region={'blocked': ['US'] * REGION_MOST_THRESHOLD}), config, at)['metadata_unavailable']
    assert not any(metadata_gates(raw(region={'blocked': ['US', 'CA']}), config, at).values())


def test_youtube_videos_requests_status():
    class Client:
        def __init__(self):
            self.parts = []

        def get(self, url, params, youtube=False):
            self.parts.append(params['part'])
            return {'items': []}

    client = Client()
    youtube_videos(client, 'key', ['dQw4w9WgXcQ'])
    assert 'status' in client.parts[0]


class RecordingClient:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def get(self, url, params, youtube=False):
        assert url.endswith('/videos')
        ids = params['id'].split(',')
        assert len(ids) <= 50
        self.calls.append(ids)
        return {'items': [self.items[video_id] for video_id in ids if video_id in self.items]}


def test_status_cache_avoids_repeat_calls_and_batches_by_50(tmp_path):
    ids = [f'{index:011d}' for index in range(120)]
    items = {video_id: raw(video_id, embeddable=index % 2 == 0) for index, video_id in enumerate(ids)}
    cache = tmp_path / 'playability.json'
    client = RecordingClient(items)
    reasons, stats = check_playability(client, 'test-key', ids, cache_path=cache, return_stats=True)
    assert stats['fetched'] == 120
    assert stats['batches'] == 3
    assert len(client.calls) == 3
    assert reasons[ids[1]] == 'not_embeddable'

    second = RecordingClient(items)
    reasons_again, stats_again = check_playability(second, 'test-key', ids, cache_path=cache, return_stats=True)
    assert second.calls == []
    assert stats_again['from_cache'] == 120
    assert reasons_again == reasons

    forced = RecordingClient(items)
    check_playability(forced, 'test-key', ids, cache_path=cache, force=True)
    assert len(forced.calls) == 3


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + '\n')


def _fixture_root(tmp_path):
    root = tmp_path / 'data'
    videos = [
        raw('good0000001'),
        raw('badembed001', embeddable=False),
        raw('badprivate1', privacy='private'),
        raw('badregion01', region={'blocked': ['US'] * REGION_MOST_THRESHOLD}),
        raw('badupload01', upload='failed'),
    ]
    feed = {'generated_at': '2026-11-11T00:00:00Z', 'videos': videos}
    _write(root / 'picks.json', feed)
    _write(root / 'videos.json', {'videos': []})
    _write(root / 'catalog.json', [dict(video) for video in videos])
    _write(root / 'hn_pool.json', {'count': 2, 'videos': [raw('good0000002'), raw('badembed001', embeddable=False)]})
    _write(root / 'topics.json', {'count': 1, 'topics': [
        {'id': 'topic-a', 'video_ids': ['good0000002', 'badembed001']},
    ]})
    _write(root / 'topic_lookup.json', {'good0000002': 'topic-a', 'badembed001': 'topic-a'})
    missing = {'id': 'missing0001', 'title': 'Missing'}
    _write(root / 'podcast.json', {'videos': [missing]})
    return root, videos, missing


def test_backfill_removes_every_source_and_bypasses_shrink_guard(tmp_path):
    root, videos, missing = _fixture_root(tmp_path)
    items = {video['id']: video for video in videos}
    items['good0000002'] = raw('good0000002')
    cache = tmp_path / 'cache.json'
    summary = backfill_playability(
        root=root, cache_path=cache, client=RecordingClient(items), key='test-key',
        rebuild=False,
    )
    assert summary['removed_ids'] == 5
    assert summary['by_reason'] == {
        'not_embeddable': 1, 'not_public': 1, 'region_restricted': 1,
        'not_processed': 1, 'missing': 1,
    }
    picks = json.loads((root / 'picks.json').read_text())
    assert [video['id'] for video in picks['videos']] == ['good0000001']
    podcast = json.loads((root / 'podcast.json').read_text())
    assert podcast['videos'] == []
    pool = json.loads((root / 'hn_pool.json').read_text())
    assert [video['id'] for video in pool['videos']] == ['good0000002']
    assert pool['count'] == 1
    topics = json.loads((root / 'topics.json').read_text())
    assert topics['topics'][0]['video_ids'] == ['good0000002']
    lookup = json.loads((root / 'topic_lookup.json').read_text())
    assert lookup == {'good0000002': 'topic-a'}
    assert summary['pb5olipo62g']['listed'] is False


def test_backfill_keeps_files_when_status_response_is_malformed(tmp_path):
    root, _videos, _missing = _fixture_root(tmp_path)
    before = (root / 'picks.json').read_text()

    class BrokenClient:
        def get(self, url, params, youtube=False):
            return {}

    with pytest.raises(RuntimeError):
        backfill_playability(
            root=root, cache_path=tmp_path / 'cache.json', client=BrokenClient(),
            key='test-key', rebuild=False,
        )
    assert (root / 'picks.json').read_text() == before


def test_backfill_refuses_to_remove_every_listed_id(tmp_path):
    root = tmp_path / 'data'
    _write(root / 'picks.json', {'videos': [{'id': 'missing0001'}, {'id': 'missing0002'}]})
    before = (root / 'picks.json').read_text()

    class EmptyClient:
        def get(self, url, params, youtube=False):
            return {'items': []}

    with pytest.raises(RuntimeError):
        backfill_playability(
            root=root, cache_path=tmp_path / 'cache.json', client=EmptyClient(),
            key='test-key', rebuild=False,
        )
    assert (root / 'picks.json').read_text() == before
