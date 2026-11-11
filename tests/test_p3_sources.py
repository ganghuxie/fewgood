import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from ytrec import __main__ as cli
from ytrec.core import build_picks, iso_now
from ytrec.podcast_whitelist import curated_editorial_feed
from ytrec.sources import (
    channel_sources_for_topic,
    channels_for_topic,
    load_sources,
    sources_for_topic,
)

ROOT = Path(__file__).resolve().parents[1]
NEW_IDS = {
    'crossroads-luoyonghao', 'stanford-hai', 'ycombinator', 'a16z', 'mit-csail',
    'sequoia-capital', 'veritasium', 'computerphile', 'ted', 'long-now',
    'computer-history-museum', 'kurzgesagt', 'numberphile', 'pbs-space-time',
    'usenix', 'stanford-gsb', 'harvard-business-review', 'knowledge-project',
    'hard-fork', 'steve-mould', 'sabine-hossenfelder', 'minutephysics',
}
LEX_ID = 'UCSHZKyawb77ixDdsGog4iWA'
LATENT_AI_ID = 'UCxBcwypKK-W3GHd_RZ9FZrQ'
LATENT_PODCAST_ID = 'UC_gbloeO227-3D_otwJUrGQ'


def legacy_channels():
    rows = []
    for name in ('ai_channels.yaml', 'podcast_channels.yaml', 'music_channels.yaml'):
        rows.extend((yaml.safe_load((ROOT / 'config' / name).read_text()) or {}).get('channels') or [])
    return rows


def video(video_id, *, duration=900, age_days=2, why=None, **extra):
    published = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat().replace('+00:00', 'Z')
    record = dict(
        id=video_id, title=f'Title {video_id}', channel=f'Channel {video_id}',
        channel_id=f'ch-{video_id}', published_at=published, duration_seconds=duration,
        view_count=100 + int(extra.pop('views', 0)), default_audio_language='en',
    )
    if why is not None:
        record['why_good'] = why
    record.update(extra)
    return record


def source_by_id(sources, source_id):
    return next(source for source in sources if source['id'] == source_id)


def test_sources_yaml_contains_every_existing_whitelist_channel():
    sources = load_sources(ROOT / 'config' / 'sources.yaml')
    legacy = legacy_channels()
    assert len(legacy) == 59
    legacy_ids = {channel['youtube_channel_id'] for channel in legacy}
    assert len(legacy_ids) == 58
    source_ids = {source['external_id'] for source in sources if source['type'] == 'channel'}
    assert legacy_ids <= source_ids


def test_lex_is_one_source_for_ai_and_podcast():
    sources = load_sources(ROOT / 'config' / 'sources.yaml')
    lex = [source for source in sources if source['external_id'] == LEX_ID]
    assert len(lex) == 1
    assert lex[0]['topics'] == ['ai', 'podcast']


def test_hacker_news_community_row_exists():
    sources = load_sources(ROOT / 'config' / 'sources.yaml')
    hn = [source for source in sources if source['external_id'] == 'hn']
    assert len(hn) == 1
    assert hn[0]['type'] == 'community'
    assert hn[0]['tier'] == 4
    assert hn[0]['topics'] == ['community']


def test_no_new_music_sources_beyond_the_original_six():
    sources = load_sources(ROOT / 'config' / 'sources.yaml')
    music = [source for source in sources if 'music' in source['topics']]
    assert len(music) == 6
    assert {source['id'] for source in music} == {
        'npr-music', 'kexp', 'colors', 'cercle', 'boiler-room', 'bbc-radio-1',
    }


def test_about_twenty_new_validated_active_channels():
    sources = load_sources(ROOT / 'config' / 'sources.yaml')
    new = [source for source in sources if source['id'] in NEW_IDS]
    assert len(new) == len(NEW_IDS)
    assert 20 <= len(new) <= 22
    assert all(source['status'] == 'active' and source['type'] == 'channel' for source in new)
    assert all(re.search(r'\b\d[\d.]*[KM]? subs;', source['notes']) for source in new)
    assert all('before 2026-11-11' in source['notes'] for source in new)
    tiers = {source['id']: source['tier'] for source in new}
    assert tiers['stanford-hai'] == 2
    assert tiers['veritasium'] == 3
    assert tiers['crossroads-luoyonghao'] == 3


def test_every_channel_has_uc_id_and_no_duplicate_channel_ids():
    sources = load_sources(ROOT / 'config' / 'sources.yaml')
    channel_ids = [source['external_id'] for source in sources if source['type'] == 'channel']
    assert all(re.fullmatch(r'UC[\w-]{22}', channel_id) for channel_id in channel_ids)
    assert len(channel_ids) == len(set(channel_ids))
    assert LATENT_AI_ID in channel_ids and LATENT_PODCAST_ID in channel_ids


def test_sources_for_topic_returns_new_channels_in_the_right_buckets():
    ai = {source['id'] for source in sources_for_topic('ai')}
    podcast = {source['id'] for source in sources_for_topic('podcast')}
    editorial = {source['id'] for source in sources_for_topic('editorial')}
    assert {'stanford-hai', 'ycombinator', 'a16z', 'mit-csail', 'sequoia-capital'} <= ai
    assert 'crossroads-luoyonghao' in podcast
    assert {'veritasium', 'computerphile', 'ted', 'hard-fork', 'minutephysics'} <= editorial
    assert 'hacker-news' in {source['id'] for source in sources_for_topic('community')}
    assert not [source for source in channel_sources_for_topic('editorial') if source['type'] != 'channel']


def test_channels_for_topic_unions_legacy_rows_without_duplicating_ids():
    legacy = yaml.safe_load((ROOT / 'config' / 'ai_channels.yaml').read_text())['channels']
    merged = channels_for_topic('ai', legacy)
    ids = [channel['youtube_channel_id'] for channel in merged]
    assert len(ids) == len(set(ids))
    assert 'UChugFTK0KyrES9terTid8vA' in ids
    assert LEX_ID in ids


def test_editorial_overflow_never_evicts_the_preferred_mix():
    community = [video(f'c{i}', why='HN', recommenders=100 - i, months=12, span_days=400) for i in range(4)]
    ai = [video(f'a{i}', why='AI', views=50 - i) for i in range(4)]
    podcast = [video(f'p{i}', why='播客', views=40 - i) for i in range(2)]
    editorial = [video(f'e{i}', views=30 - i) for i in range(5)]
    picks = build_picks({
        'community': {'videos': community}, 'ai': {'videos': ai},
        'podcast': {'videos': podcast}, 'editorial': {'videos': editorial},
    })
    assert len(picks['videos']) == 10
    assert sum(video['source'] == 'community' for video in picks['videos']) == 4
    assert sum(video['source'] == 'ai' for video in picks['videos']) == 4
    assert sum(video['source'] == 'podcast' for video in picks['videos']) == 2
    assert all(video['source'] != 'editorial' for video in picks['videos'])


def test_editorial_fills_only_leftover_slots_and_skips_short_videos():
    community = [video('c0', why='HN', recommenders=50, months=12, span_days=400)]
    ai = [video('a0', why='AI')]
    podcast = [video('p0', why='播客')]
    editorial = [
        video('e-long-1'), video('e-long-2'), video('e-long-3'),
        video('e-short', duration=479),
    ]
    picks = build_picks({
        'community': {'videos': community}, 'ai': {'videos': ai},
        'podcast': {'videos': podcast}, 'editorial': {'videos': editorial},
    })
    ids = [video['id'] for video in picks['videos']]
    assert 'e-short' not in ids
    assert len(ids) == 6
    assert sum(video['source'] == 'editorial' for video in picks['videos']) == 3
    assert all(video.get('why_good') for video in picks['videos'])


def test_editorial_only_pool_is_capped_at_ten():
    editorial = [video(f'e{i}', views=200 - i) for i in range(20)]
    picks = build_picks({'community': {'videos': []}, 'ai': {'videos': []},
                         'podcast': {'videos': []}, 'editorial': {'videos': editorial}})
    assert len(picks['videos']) == 10
    assert all(video['source'] == 'editorial' for video in picks['videos'])


def test_refresh_calls_editorial_feed_before_rebuild_and_adds_no_cron():
    source = inspect.getsource(cli.refresh)
    assert 'curated_editorial_feed(quota_limit=limit)' in source
    assert source.index('curated_editorial_feed') > source.index('curated_music_feed')
    assert source.index('curated_editorial_feed') < source.index('rebuild_offline()')
    cron_lines = []
    for workflow in (ROOT / '.github' / 'workflows').glob('*.yml'):
        cron_lines.extend(re.findall(r'^\s*- cron:', workflow.read_text(), re.M))
    assert len(cron_lines) == 1


class RecordingClient:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def get(self, url, params, youtube=False):
        self.calls.append((url, dict(params)))
        return {'items': [self.raw]}


def test_curated_editorial_feed_reads_sources_yaml_and_writes_editorial_json(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    sources_path = tmp_path / 'sources.yaml'
    sources_path.write_text(yaml.safe_dump({'sources': [{
        'id': 'test-editorial', 'type': 'channel', 'external_id': 'UC1',
        'handle': 'test', 'display_name': 'Test Editorial', 'tier': 3,
        'daily_cap': 1, 'language': 'en', 'status': 'active', 'topics': ['editorial'],
    }]}, allow_unicode=True))
    raw = {
        'id': 'editorial1', 'snippet': {'publishedAt': iso_now(), 'title': 'Science',
        'channelTitle': 'Test Editorial', 'channelId': 'UC1', 'defaultAudioLanguage': 'en'},
        'contentDetails': {'duration': 'PT10M'}, 'statistics': {'viewCount': '10', 'likeCount': '1'},
    }
    client = RecordingClient(raw)
    result = curated_editorial_feed(
        client=client, output=str(tmp_path / 'out'), sources_file=str(sources_path),
        rss_fetcher=lambda channel_id: [{'id': 'editorial1', 'published_at': iso_now()}],
    )
    assert [video['id'] for video in result['videos']] == ['editorial1']
    assert json.loads((tmp_path / 'out' / 'editorial.json').read_text())['videos'][0]['id'] == 'editorial1'
    assert [url.rsplit('/', 1)[-1] for url, _params in client.calls] == ['videos']
