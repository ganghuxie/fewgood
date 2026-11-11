import json
import json as json_module
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ytrec import weekly_topics as wt


NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
NOW_TS = int(NOW.timestamp())


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def _raw(video_id, title, *, channel_id='chan-new-1', duration='PT20M',
         language='en', privacy='public', embeddable=True,
         view_count=1234, like_count=10):
    return {
        'id': video_id,
        'snippet': {
            'publishedAt': '2020-01-01T00:00:00Z',
            'title': title,
            'channelTitle': 'Channel ' + channel_id,
            'channelId': channel_id,
            'defaultAudioLanguage': language,
        },
        'contentDetails': {'duration': duration},
        'statistics': {'viewCount': str(view_count), 'likeCount': str(like_count)},
        'status': {'privacyStatus': privacy, 'uploadStatus': 'processed',
                   'embeddable': embeddable},
    }


def _hit(item_id, video_id, author='alice'):
    return {
        'objectID': item_id,
        'author': author,
        'created_at_i': NOW_TS,
        'comment_text': f'Good watch: https://youtu.be/{video_id}',
    }


class FakeAlgolia:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def get(self, url, params, youtube=False):
        assert url == 'https://hn.algolia.com/api/v1/search_by_date'
        self.calls.append(params)
        return {'nbHits': len(self.hits), 'nbPages': 1, 'hits': self.hits}


class FakeYouTube:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def get(self, url, params, youtube=False):
        assert url.endswith('/videos')
        assert youtube is True
        ids = params['id'].split(',')
        assert len(ids) <= 50
        self.calls.append(ids)
        return {'items': [self.items[video_id] for video_id in ids if video_id in self.items]}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _fixture_root(tmp_path):
    root = tmp_path / 'site/src/data'
    old_pool = [
        {'id': 'oldvideo001', 'title': 'Old AI video', 'channel': 'Old AI',
         'channel_id': 'old-ai-channel', 'published_at': '2020-01-01T00:00:00Z',
         'quotes': [], 'recommenders': 20, 'months': 3, 'span_days': 40},
        {'id': 'oldvideo002', 'title': 'Old programming video', 'channel': 'Old Code',
         'channel_id': 'old-code-channel', 'published_at': '2020-01-01T00:00:00Z',
         'quotes': [], 'recommenders': 10, 'months': 2, 'span_days': 20},
    ]
    topics = {
        'generated_at': '2026-01-01T00:00:00Z',
        'count': 2,
        'topics': [
            {'id': 'ai', 'name_zh': '人工智能', 'aliases_en': ['ai'],
             'keywords': ['ai', 'machine', 'learning', 'neural', 'models'],
             'source_channel_ids': ['old-ai-channel'],
             'video_ids': ['oldvideo001'], 'added_last_24h': 0},
            {'id': 'programming', 'name_zh': '编程思想', 'aliases_en': ['programming'],
             'keywords': ['programming', 'software', 'code', 'python', 'javascript'],
             'source_channel_ids': ['old-code-channel'],
             'video_ids': ['oldvideo002'], 'added_last_24h': 0},
        ],
    }
    lookup = {'oldvideo001': 'ai', 'oldvideo002': 'programming'}
    _write(root / 'hn_pool.json', {
        'generated_at': '2026-01-01T00:00:00Z', 'kind': 'hn_pool', 'limit': 1000,
        'count': len(old_pool), 'videos': old_pool,
    })
    _write(root / 'topics.json', topics)
    _write(root / 'topic_lookup.json', lookup)
    _write(root / 'trending.json', {'generated_at': 'unchanged', 'videos': [{'id': 'trendvid001'}]})
    config = {
        'database': str(tmp_path / 'main.sqlite'),
        'crawl': {'window_days': 30, 'request_interval_seconds': 0},
        'metadata': {
            'daily_quota_limit': 8000,
            'max_units_per_run': 1000,
            'classic_speech': {'enabled': False},
        },
    }
    return root, old_pool, topics, lookup, config


def _run(root, config, tmp_path, hits, items, **kwargs):
    return wt.run_weekly_topics(
        config, root=root, yaml_path=tmp_path / 'config/topics.yaml',
        db_path=tmp_path / 'weekly.sqlite', algolia_client=FakeAlgolia(hits),
        youtube_client=FakeYouTube(items),
        playability_cache_path=tmp_path / 'playability.json',
        thumbnail_cache_path=tmp_path / 'thumbnails.json',
        now_dt=NOW, build=False, no_commit=True, **kwargs,
    )


def test_topup_preserves_existing_data_drops_bad_gates_and_appends_pass(monkeypatch, tmp_path):
    root, old_pool, old_topics, old_lookup, config = _fixture_root(tmp_path)
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.setattr(wt, 'probe_thumbnail',
                        lambda video_id: {'kind': 'maxresdefault', 'url': f'https://img/{video_id}.jpg'})
    ids = {
        'goodvideo01': _raw('goodvideo01', 'AI agents in production'),
        'shortvid001': _raw('shortvid001', 'A short', duration='PT45S'),
        'unplay00001': _raw('unplay00001', 'Blocked embed', embeddable=False),
        'langblock01': _raw('langblock01', 'French video', language='fr-FR'),
        'duramin0001': _raw('duramin0001', 'Three minute talk', duration='PT3M'),
    }
    hits = [_hit(f'item-{index}', video_id) for index, video_id in enumerate(ids)]
    trending_before = (root / 'trending.json').read_bytes()

    summary = _run(root, config, tmp_path, hits, ids)

    assert summary['candidates'] == 5
    assert summary['new_videos'] == 1
    assert summary['dropped_by_gate'] == {
        'vertical_or_short': 1, 'not_embeddable': 1, 'language': 1, 'duration': 1,
    }
    assert summary['fetched_batches'] == 1
    assert summary['per_topic'] == {
        'ai': {
            'count': 1,
            'titles': ['AI agents in production'],
            'samples': ['AI agents in production'],
        },
    }

    pool = json.loads((root / 'hn_pool.json').read_text())
    assert pool['videos'][:2] == old_pool
    assert [video['id'] for video in pool['videos']] == ['oldvideo001', 'oldvideo002', 'goodvideo01']
    assert pool['count'] == 3
    assert pool['videos'][2]['thumb'] == 'https://img/goodvideo01.jpg'

    topics = json.loads((root / 'topics.json').read_text())
    by_id = {topic['id']: topic for topic in topics['topics']}
    assert by_id['ai']['name_zh'] == old_topics['topics'][0]['name_zh']
    assert by_id['ai']['video_ids'][:1] == ['oldvideo001']
    assert by_id['ai']['video_ids'][-1] == 'goodvideo01'
    assert 'chan-new-1' in by_id['ai']['source_channel_ids']
    assert by_id['programming']['video_ids'] == ['oldvideo002']

    lookup = json.loads((root / 'topic_lookup.json').read_text())
    assert lookup['oldvideo001'] == old_lookup['oldvideo001']
    assert lookup['oldvideo002'] == old_lookup['oldvideo002']
    assert lookup['goodvideo01'] == 'ai'
    assert (root / 'trending.json').read_bytes() == trending_before
    playability = json.loads((tmp_path / 'playability.json').read_text())['entries']
    assert playability['goodvideo01']['reason'] is None
    assert 'shortvid001' in playability


def test_weekly_cap_keeps_top_three_confident_videos_per_topic(monkeypatch, tmp_path):
    root, old_pool, old_topics, old_lookup, config = _fixture_root(tmp_path)
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.setattr(wt, 'probe_thumbnail',
                        lambda video_id: {'kind': 'maxresdefault', 'url': f'https://img/{video_id}.jpg'})
    ids = {
        'capvideo001': _raw('capvideo001', 'AI agents ranked first', view_count=1000, like_count=40),
        'capvideo002': _raw('capvideo002', 'AI agents ranked second', view_count=1000, like_count=30),
        'capvideo003': _raw('capvideo003', 'AI agents ranked third', view_count=1000, like_count=20),
        'capvideo004': _raw('capvideo004', 'AI agents ranked fourth', view_count=1000, like_count=10),
    }
    hits = [_hit(f'item-{video_id}', video_id) for video_id in ids]

    summary = _run(root, config, tmp_path, hits, ids)

    kept_ids = ['capvideo001', 'capvideo002', 'capvideo003']
    assert summary['new_videos'] == 3, summary
    assert summary['topic_cap'] == 3
    assert summary['per_topic']['ai']['titles'] == [
        'AI agents ranked first', 'AI agents ranked second', 'AI agents ranked third',
    ]
    assert summary['skipped_over_cap'] == ['capvideo004']
    assert summary['skipped_over_cap_details'][0]['reason'] == 'over_cap'
    report = wt.format_summary(summary)
    for title in ('AI agents ranked first', 'AI agents ranked second', 'AI agents ranked third'):
        assert title in report
    assert 'Skipped over cap: 1' in report
    assert 'capvideo004' in report
    assert 'AI agents ranked fourth' in report

    pool = json.loads((root / 'hn_pool.json').read_text())
    assert pool['videos'][:2] == old_pool
    assert [video['id'] for video in pool['videos']] == [
        'oldvideo001', 'oldvideo002', *kept_ids,
    ]
    topics = json.loads((root / 'topics.json').read_text())
    by_id = {topic['id']: topic for topic in topics['topics']}
    assert by_id['ai']['video_ids'] == ['oldvideo001', *kept_ids]
    lookup = json.loads((root / 'topic_lookup.json').read_text())
    assert {video_id: lookup.get(video_id) for video_id in kept_ids} == {
        video_id: 'ai' for video_id in kept_ids
    }
    assert 'capvideo004' not in lookup
    assert lookup['oldvideo001'] == old_lookup['oldvideo001']


@pytest.mark.parametrize('run_kwargs', [{'dry_run': True}, {'write': False}])
def test_dry_run_writes_nothing_and_does_not_commit(monkeypatch, tmp_path, run_kwargs):
    root, _old_pool, _old_topics, _old_lookup, config = _fixture_root(tmp_path)
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    monkeypatch.setattr(wt, 'probe_thumbnail',
                        lambda video_id: {'kind': 'hqdefault', 'url': f'https://img/{video_id}.jpg'})
    snapshots = {path.name: path.read_bytes() for path in root.iterdir()}
    original_run = subprocess.run

    def forbidden(*args, **kwargs):
        raise AssertionError('dry run must not invoke git or npm')

    monkeypatch.setattr(subprocess, 'run', forbidden)
    try:
        summary = _run(
            root, config, tmp_path,
            [_hit('item-good', 'goodvideo01')],
            {'goodvideo01': _raw('goodvideo01', 'AI agents in production')},
            **run_kwargs,
        )
    finally:
        monkeypatch.setattr(subprocess, 'run', original_run)

    assert summary['new_videos'] == 1
    assert summary['dry_run'] is True
    assert {path.name: path.read_bytes() for path in root.iterdir()} == snapshots
    assert not (tmp_path / 'playability.json').exists()
    assert not (tmp_path / 'thumbnails.json').exists()
    assert not (tmp_path / 'weekly.sqlite').exists()


def test_curation_rules_beat_llm(monkeypatch):
    videos = [{'id': 'curated0001', 'title': 'AI agents in production',
               'channel': 'Example', 'channel_id': 'chan-1'}]
    topics = [{'id': 'ai', 'name_zh': '人工智能', 'keywords': ['ai']},
              {'id': 'programming', 'name_zh': '编程思想', 'keywords': ['code']}]
    curated, unmatched, skipped = wt._curation_partition(videos, {'ai', 'programming'})
    assert curated == {'curated0001': 'ai'}
    assert unmatched == []
    assert skipped == {}

    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')

    def should_not_call(*args, **kwargs):
        raise AssertionError('curated videos must not reach DeepSeek')

    assignments, stats = wt.llm_assignments(unmatched, topics, cap=30, post=should_not_call)
    assert assignments == {}
    assert stats['calls'] == 0
    assert stats['skipped'] == 'empty'


def test_llm_cap_invalid_topic_and_missing_key(monkeypatch):
    topics = [{'id': 'ai', 'name_zh': '人工智能', 'keywords': ['ai']}]
    videos = [
        {'id': f'llmvideo{index:03d}', 'title': f'Unmatched talk {index}', 'channel': 'C'}
        for index in range(10)
    ]
    calls = []

    def post(url, headers, json, timeout):
        calls.append(json)
        return FakeResponse({
            'choices': [{'message': {'content': json_module.dumps({
                'assignments': {
                    'llmvideo000': 'ai',
                    'llmvideo001': 'invented-topic',
                    'not-in-batch': 'ai',
                },
            })}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120},
        })

    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')
    assignments, stats = wt.llm_assignments(videos, topics, cap=1, post=post)
    assert len(calls) == 1
    assert calls[0]['model'] == 'deepseek-flash'
    assert calls[0].get('thinking') == {'type': 'disabled'}
    prompt = calls[0]['messages'][0]['content']
    assert 'only for MIT content' in prompt
    assert 'Return null when the fit is uncertain' in prompt
    assert 'Never invent a video id or topic id' in prompt
    assert stats['calls'] == 1
    assert assignments == {'llmvideo000': 'ai'}
    assert stats['invalid_topic_ids'] == 1
    assert stats['invalid_video_ids'] == 1
    assert stats['total_tokens'] == 120
    assert stats['estimated_cost_cny'] > 0

    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    calls.clear()
    assignments, stats = wt.llm_assignments(videos, topics, cap=1, post=post)
    assert calls == []
    assert assignments == {}
    assert stats['skipped'] == 'missing_key'


def test_llm_mit_assignment_is_rejected_for_non_mit_video(monkeypatch):
    topics = [{'id': 'mit', 'name_zh': '高校公开课', 'keywords': ['mit']},
              {'id': 'classic-talks', 'name_zh': '经典演讲', 'keywords': ['lecture']}]
    videos = [{'id': 'stanford001', 'title': 'Stanford CS146S lecture',
               'channel': 'Stanford University', 'channel_id': 'chan-stanford'}]

    def post(url, headers, json, timeout):
        return FakeResponse({
            'choices': [{'message': {'content': json_module.dumps({
                'assignments': {'stanford001': 'mit'},
            })}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
        })

    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')
    assignments, stats = wt.llm_assignments(videos, topics, cap=1, post=post)
    assert assignments == {}
    assert stats['disallowed_mit_ids'] == 1


def test_weekly_mit_guard_reroutes_non_mit_university_lectures():
    topics = {'mit', 'classic-talks', 'conferences'}
    videos = [
        {'id': 'stanford001', 'title': 'Stanford CS146S: How always-on agents work',
         'channel': 'Stanford', 'channel_id': 'UC-EnprmCZ3OXyAoG7vjVNCA'},
        {'id': 'harvard0001', 'title': 'Justice: What is the Right Thing to Do? Lecture 1',
         'channel': 'Harvard University', 'channel_id': 'chan-harvard'},
        {'id': 'stanconfer1', 'title': 'Stanford Systems Conference keynote',
         'channel': 'Stanford', 'channel_id': 'UC-EnprmCZ3OXyAoG7vjVNCA'},
        {'id': 'mitocw0001', 'title': '6.006 Introduction to Algorithms, Lecture 1',
         'channel': 'MIT OpenCourseWare', 'channel_id': 'UCEBb1b_L6zDS3xTUrIALZOw'},
        {'id': 'mitocw0002', 'title': 'MIT OpenCourseWare: 6.006 Lecture 2',
         'channel': 'MIT OpenCourseWare', 'channel_id': 'chan-mit-title'},
    ]

    curated, unmatched, skipped = wt._curation_partition(videos, topics)

    assert curated == {
        'stanford001': 'classic-talks',
        'harvard0001': 'classic-talks',
        'stanconfer1': 'conferences',
        'mitocw0001': 'mit',
        'mitocw0002': 'mit',
    }
    assert unmatched == []
    assert skipped == {}


def test_topic_cap_config_default_and_cli_override():
    assert wt._resolve_topic_cap({}) == 3
    assert wt._resolve_topic_cap({'metadata': {'weekly_topic_cap': 2}}) == 2
    assert wt._resolve_topic_cap({'metadata': {'weekly_topic_cap': 2}}, override=1) == 1
    with pytest.raises(ValueError, match='zero or positive'):
        wt._resolve_topic_cap({'metadata': {'weekly_topic_cap': -1}})


def test_weekly_config_topic_cap_override_is_used(monkeypatch, tmp_path):
    root, _old_pool, _old_topics, _old_lookup, config = _fixture_root(tmp_path)
    config['metadata']['weekly_topic_cap'] = 1
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.setattr(wt, 'probe_thumbnail',
                        lambda video_id: {'kind': 'maxresdefault', 'url': f'https://img/{video_id}.jpg'})
    ids = {
        'override001': _raw('override001', 'AI agents preferred', like_count=40),
        'override002': _raw('override002', 'AI agents overflow', like_count=10),
    }

    summary = _run(root, config, tmp_path,
                   [_hit(f'item-{video_id}', video_id) for video_id in ids], ids)

    assert summary['topic_cap'] == 1
    assert summary['new_videos'] == 1
    assert summary['per_topic']['ai']['titles'] == ['AI agents preferred']
    assert summary['skipped_over_cap'] == ['override002']
    lookup = json.loads((root / 'topic_lookup.json').read_text())
    assert lookup['override001'] == 'ai'
    assert 'override002' not in lookup


def test_centroid_fallback_appends_strong_and_omits_weak(tmp_path):
    pool = [
        {'id': 'oldvideo001', 'title': 'Linux kernel networking internals',
         'channel': 'Systems Channel', 'channel_id': 'chan-sys', 'quotes': []},
        {'id': 'oldvideo002', 'title': 'Kernel networking and distributed systems',
         'channel': 'Systems Channel', 'channel_id': 'chan-sys', 'quotes': []},
    ]
    topics = {
        'generated_at': '2026-01-01T00:00:00Z', 'count': 1,
        'topics': [{
            'id': 'systems', 'name_zh': '系统', 'aliases_en': ['systems'],
            'keywords': ['kernel', 'networking', 'linux', 'systems', 'distributed'],
            'source_channel_ids': ['chan-sys'], 'video_ids': ['oldvideo001', 'oldvideo002'],
            'added_last_24h': 0,
        }],
    }
    lookup = {'oldvideo001': 'systems', 'oldvideo002': 'systems'}
    new_videos = [
        {'id': 'strong00001', 'title': 'Kernel networking internals', 'channel': 'C',
         'channel_id': 'chan-strong', 'quotes': [], 'published_at': '2020-01-01T00:00:00Z'},
        {'id': 'weak0000001', 'title': 'Zebra umbrella', 'channel': 'C',
         'channel_id': 'chan-weak', 'quotes': [], 'published_at': '2020-01-01T00:00:00Z'},
    ]

    updated_topics, updated_lookup, diagnostics = wt.apply_topic_assignments(
        pool, new_videos, deepcopy(topics), dict(lookup), [], {}, {}, set(), now_dt=NOW,
    )

    topic = updated_topics['topics'][0]
    assert topic['video_ids'] == ['oldvideo001', 'oldvideo002', 'strong00001']
    assert 'chan-strong' in topic['source_channel_ids']
    assert 'chan-weak' not in topic['source_channel_ids']
    assert updated_lookup['strong00001'] == 'systems'
    assert 'weak0000001' not in updated_lookup
    assert diagnostics['skipped_low_confidence'] == ['weak0000001']
    assert diagnostics['skipped_low_confidence_details'] == [{
        'id': 'weak0000001',
        'title': 'Zebra umbrella',
        'reason': 'low_confidence',
    }]


def test_news_recap_is_not_added_to_classic_talks(tmp_path):
    pool = [{'id': 'oldvideo001', 'title': 'A real lecture', 'channel': 'U',
             'channel_id': 'chan-classic', 'quotes': []}]
    topics = {
        'generated_at': '2026-01-01T00:00:00Z', 'count': 1,
        'topics': [{
            'id': 'classic-talks', 'name_zh': '经典演讲', 'aliases_en': ['talks'],
            'keywords': ['lecture', 'speech', 'ted', 'classic', 'talk'],
            'source_channel_ids': ['chan-classic'], 'video_ids': ['oldvideo001'],
            'added_last_24h': 0,
        }],
    }
    new_video = {
        'id': 'newsvid0001', 'title': 'Google Loses $500B in 12 Hours | Market Recap',
        'channel': 'News', 'channel_id': 'chan-news', 'quotes': [],
        'published_at': '2020-01-01T00:00:00Z',
    }

    updated_topics, updated_lookup, diagnostics = wt.apply_topic_assignments(
        pool, [new_video], topics, {'oldvideo001': 'classic-talks'}, [],
        {'newsvid0001': 'classic-talks'}, {}, set(), now_dt=NOW,
    )

    assert updated_topics['topics'][0]['video_ids'] == ['oldvideo001']
    assert 'newsvid0001' not in updated_lookup
    assert 'newsvid0001' in diagnostics['retag_dropped']


def test_curation_none_target_is_omitted_entirely():
    videos = [{'id': 'leaptech001', 'title': 'Leap Technology', 'channel': 'C',
               'channel_id': 'chan-leap'}]
    curated, unmatched, skipped = wt._curation_partition(videos, {'systems'})
    assert curated == {}
    assert unmatched == []
    assert skipped == {'leaptech001': 'curation_none'}

    pool = [{'id': 'oldvideo001', 'title': 'Leap technology systems', 'channel': 'C',
             'channel_id': 'chan-old', 'quotes': []}]
    topics = {'generated_at': '2026-01-01T00:00:00Z', 'count': 1,
              'topics': [{'id': 'systems', 'name_zh': '系统', 'aliases_en': ['systems'],
                          'keywords': ['leap', 'systems', 'technology', 'software', 'linux'],
                          'source_channel_ids': ['chan-old'], 'video_ids': ['oldvideo001'],
                          'added_last_24h': 0}]}
    updated_topics, updated_lookup, _diagnostics = wt.apply_topic_assignments(
        pool, videos, topics, {'oldvideo001': 'systems'}, [], curated, {}, skipped,
        now_dt=NOW,
    )
    assert updated_topics['topics'][0]['video_ids'] == ['oldvideo001']
    assert 'leaptech001' not in updated_lookup


def test_quota_cap_refusal_writes_nothing(monkeypatch, tmp_path):
    root, _old_pool, _old_topics, _old_lookup, config = _fixture_root(tmp_path)
    config['metadata']['max_units_per_run'] = 0
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    before_pool = (root / 'hn_pool.json').read_bytes()
    before_topics = (root / 'topics.json').read_bytes()

    class NoNetworkYouTube:
        def get(self, *args, **kwargs):
            raise AssertionError('quota refusal must happen before videos.list')

    with pytest.raises(RuntimeError, match='max_units_per_run'):
        wt.run_weekly_topics(
            config, root=root, yaml_path=tmp_path / 'config/topics.yaml',
            db_path=tmp_path / 'weekly.sqlite',
            algolia_client=FakeAlgolia([_hit('item-good', 'goodvideo01')]),
            youtube_client=NoNetworkYouTube(),
            playability_cache_path=tmp_path / 'playability.json',
            thumbnail_cache_path=tmp_path / 'thumbnails.json',
            now_dt=NOW, build=False, no_commit=True,
        )
    assert (root / 'hn_pool.json').read_bytes() == before_pool
    assert (root / 'topics.json').read_bytes() == before_topics


def test_weekly_topics_command_is_in_help():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-m', 'ytrec', 'weekly-topics', '--help'],
        cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0
    assert 'weekly-topics' in result.stdout
    assert '--llm-cap' in result.stdout
    assert '--topic-cap' in result.stdout
    assert '--no-commit' in result.stdout
