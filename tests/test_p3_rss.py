import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from ytrec.core import ai_feed, iso_now
from ytrec.podcast_whitelist import (
    curated_music_feed,
    fetch_channel_rss_video_ids,
    parse_channel_rss,
)


RSS_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/">
  <title>Example channel</title>
  <entry>
    <id>yt:video:firstVideo1</id>
    <yt:videoId>firstVideo1</yt:videoId>
    <yt:channelId>UC1</yt:channelId>
    <title>First</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=firstVideo1"/>
    <published>2026-11-10T12:00:00+00:00</published>
    <updated>2026-11-10T13:00:00+00:00</updated>
  </entry>
  <entry>
    <id>yt:video:secondVideo</id>
    <yt:channelId>UC1</yt:channelId>
    <title>Second</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=secondVideo"/>
    <updated>2026-11-09T09:30:00+00:00</updated>
  </entry>
  <entry>
    <id>https://www.youtube.com/watch?v=thirdVideo3</id>
    <yt:channelId>UC1</yt:channelId>
    <title>Third</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=thirdVideo3"/>
    <published>2026-11-08T08:00:00+00:00</published>
  </entry>
</feed>
'''


def raw_video(video_id, duration_iso='PT10M', channel_id='UC1', published_at=None):
    return {
        'id': video_id,
        'snippet': {
            'publishedAt': published_at or iso_now(),
            'title': f'Title {video_id}',
            'channelTitle': f'Channel {channel_id}',
            'channelId': channel_id,
            'defaultAudioLanguage': 'en',
        },
        'contentDetails': {'duration': duration_iso},
        'statistics': {'viewCount': '10', 'likeCount': '1'},
    }


class RecordingClient:
    def __init__(self, raws):
        self.raws = raws
        self.calls = []

    def get(self, url, params, youtube=False):
        self.calls.append((url, dict(params)))
        assert url.endswith('/videos'), url
        return {'items': [self.raws[vid] for vid in params['id'].split(',')]}


class FallbackRecordingClient:
    def __init__(self, raws, playlists=None, uploads=None):
        self.raws = raws
        self.playlists = playlists or {}
        self.uploads = uploads or {}
        self.calls = []

    def get(self, url, params, youtube=False):
        self.calls.append((url, dict(params)))
        endpoint = url.rsplit('/', 1)[-1]
        if endpoint == 'playlistItems':
            return {'items': self.playlists.get(params['playlistId'], [])}
        if endpoint == 'channels':
            uploads = self.uploads.get(params['id'])
            return {'items': [{'contentDetails': {'relatedPlaylists': {'uploads': uploads}}}]} if uploads else {'items': []}
        assert endpoint == 'videos', url
        return {'items': [self.raws[vid] for vid in params['id'].split(',')]}


def upload(video_id, published_at=None):
    published_at = published_at or iso_now()
    return {
        'snippet': {'publishedAt': published_at},
        'contentDetails': {'videoId': video_id, 'videoPublishedAt': published_at},
    }


def write_music_config(path, channels):
    path.write_text(yaml.safe_dump({
        'min_duration_seconds': 180,
        'max_duration_seconds': 7200,
        'channels': channels,
    }, allow_unicode=True))


def test_parse_channel_rss_extracts_ids_and_published_times():
    entries = parse_channel_rss(RSS_XML)
    assert entries == [
        {'id': 'firstVideo1', 'published_at': '2026-11-10T12:00:00+00:00'},
        {'id': 'secondVideo', 'published_at': '2026-11-09T09:30:00+00:00'},
        {'id': 'thirdVideo3', 'published_at': '2026-11-08T08:00:00+00:00'},
    ]


def test_fetch_channel_rss_uses_plain_http_without_youtube_quota():
    calls = []

    class Response:
        status_code = 200
        text = RSS_XML

    class Session:
        def get(self, url, params, timeout):
            calls.append((url, params, timeout))
            return Response()

    entries = fetch_channel_rss_video_ids('UC1', session=Session())
    assert [entry['id'] for entry in entries] == ['firstVideo1', 'secondVideo', 'thirdVideo3']
    assert calls == [
        ('https://www.youtube.com/feeds/videos.xml', {'channel_id': 'UC1'}, 15),
    ]


def test_fetch_channel_rss_404_falls_back_to_derived_uploads_playlist():
    class Response:
        status_code = 404
        text = ''

    class Session:
        def get(self, url, params, timeout):
            return Response()

    client = FallbackRecordingClient(
        {'fallback001': raw_video('fallback001', 'PT5M')},
        playlists={'UU1': [upload('fallback001')]},
    )

    entries = fetch_channel_rss_video_ids(
        'UC1', session=Session(), client=client, key='test-only',
    )

    assert [entry['id'] for entry in entries] == ['fallback001']
    assert [url.rsplit('/', 1)[-1] for url, _params in client.calls] == ['playlistItems']
    assert client.calls[0][1]['playlistId'] == 'UU1'


def test_curated_music_feed_discovers_via_rss_without_playlist_items(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    config_path = tmp_path / 'music_channels.yaml'
    write_music_config(config_path, [{
        'name': 'Test Channel', 'handle': 'test', 'youtube_channel_id': 'UC1',
    }])
    client = RecordingClient({'rssTrack001': raw_video('rssTrack001', 'PT5M')})

    result = curated_music_feed(
        config_path=str(config_path), client=client, output=str(tmp_path / 'out'),
        rss_fetcher=lambda channel_id: [{'id': 'rssTrack001', 'published_at': iso_now()}],
    )

    assert [video['id'] for video in result['videos']] == ['rssTrack001']
    assert [url.rsplit('/', 1)[-1] for url, _params in client.calls] == ['videos']
    assert result['quota_units_approx'] == 1


def test_curated_music_feed_falls_back_when_rss_raises(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    config_path = tmp_path / 'music_channels.yaml'
    write_music_config(config_path, [{
        'name': 'Test Channel', 'handle': 'test', 'youtube_channel_id': 'UC1',
    }])
    client = FallbackRecordingClient(
        {'fallback001': raw_video('fallback001', 'PT5M')},
        playlists={'UU1': [upload('fallback001')]},
    )

    def rss_fetcher(channel_id):
        raise RuntimeError('RSS unavailable')

    result = curated_music_feed(
        config_path=str(config_path), client=client, output=str(tmp_path / 'out'),
        rss_fetcher=rss_fetcher,
    )

    assert [video['id'] for video in result['videos']] == ['fallback001']
    assert [url.rsplit('/', 1)[-1] for url, _params in client.calls] == ['playlistItems', 'videos']
    assert result['quota_units_approx'] == 2


def test_ai_feed_falls_back_when_rss_returns_no_entries(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    channels_path = tmp_path / 'ai_channels.yaml'
    channels_path.write_text(yaml.safe_dump({'channels': [{
        'name': 'AI Channel', 'youtube_channel_id': 'UC1',
    }]}, allow_unicode=True))
    client = FallbackRecordingClient(
        {'fallbackAI01': raw_video('fallbackAI01', 'PT5M')},
        playlists={'UU1': [upload('fallbackAI01')]},
    )

    result = ai_feed(
        channels_file=str(channels_path), client=client, output=str(tmp_path / 'out'),
        rss_fetcher=lambda channel_id: [],
    )

    assert [video['id'] for video in result['videos']] == ['fallbackAI01']
    assert [url.rsplit('/', 1)[-1] for url, _params in client.calls] == ['playlistItems', 'videos']
    assert result['quota_units_approx'] == 2


def test_ai_feed_discovers_via_rss_and_prefilters_old_posts(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    channels_path = tmp_path / 'ai_channels.yaml'
    channels_path.write_text(yaml.safe_dump({'channels': [{
        'name': 'AI Channel', 'youtube_channel_id': 'UC1',
    }]}, allow_unicode=True))
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    client = RecordingClient({'freshAI0001': raw_video('freshAI0001', 'PT5M')})

    result = ai_feed(
        channels_file=str(channels_path), client=client, output=str(tmp_path / 'out'),
        rss_fetcher=lambda channel_id: [
            {'id': 'oldAI000001', 'published_at': old},
            {'id': 'freshAI0001', 'published_at': iso_now()},
        ],
    )

    assert [video['id'] for video in result['videos']] == ['freshAI0001']
    assert [params['id'] for _url, params in client.calls] == ['freshAI0001']
    assert [url.rsplit('/', 1)[-1] for url, _params in client.calls] == ['videos']
    assert result['quota_units_approx'] == 1


def test_fresh_cached_record_is_reused_and_new_id_is_fetched(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    config_path = tmp_path / 'music_channels.yaml'
    write_music_config(config_path, [
        {'name': 'One', 'handle': 'one', 'youtube_channel_id': 'UC1'},
        {'name': 'Two', 'handle': 'two', 'youtube_channel_id': 'UC2'},
    ])
    output = tmp_path / 'out'
    output.mkdir()
    cached = {
        'id': 'cachedTrack1', 'title': 'Cached', 'channel': 'One', 'channel_id': 'UC1',
        'published_at': iso_now(), 'default_audio_language': 'en', 'default_language': 'en',
        'duration_seconds': 300, 'view_count': 999, 'like_count': 5,
    }
    (output / 'music.json').write_text(json.dumps({
        'generated_at': iso_now(),
        'videos': [cached],
    }))
    client = RecordingClient({'newTrack0001': raw_video('newTrack0001', 'PT5M', channel_id='UC2')})

    def rss_fetcher(channel_id):
        if channel_id == 'UC1':
            return [{'id': 'cachedTrack1', 'published_at': iso_now()}]
        return [{'id': 'newTrack0001', 'published_at': iso_now()}]

    result = curated_music_feed(
        config_path=str(config_path), client=client, output=str(output),
        rss_fetcher=rss_fetcher,
    )

    assert {video['id'] for video in result['videos']} == {'cachedTrack1', 'newTrack0001'}
    assert [params['id'] for _url, params in client.calls] == ['newTrack0001']
    assert result['quota_units_approx'] == 1


def test_fallback_reuses_fresh_cached_record_without_videos_list(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    config_path = tmp_path / 'music_channels.yaml'
    write_music_config(config_path, [{
        'name': 'One', 'handle': 'one', 'youtube_channel_id': 'UC1',
    }])
    output = tmp_path / 'out'
    output.mkdir()
    cached_published = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    cached = {
        'id': 'cachedTrack1', 'title': 'Cached', 'channel': 'One', 'channel_id': 'UC1',
        'published_at': cached_published, 'default_audio_language': 'en', 'default_language': 'en',
        'duration_seconds': 300, 'view_count': 999, 'like_count': 5,
    }
    (output / 'music.json').write_text(json.dumps({
        'generated_at': iso_now(),
        'videos': [cached],
    }))
    client = FallbackRecordingClient(
        {'newTrack0001': raw_video('newTrack0001', 'PT5M')},
        playlists={'UU1': [upload('cachedTrack1'), upload('newTrack0001')]},
    )

    result = curated_music_feed(
        config_path=str(config_path), client=client, output=str(output),
        rss_fetcher=lambda channel_id: (_ for _ in ()).throw(RuntimeError('RSS unavailable')),
    )

    assert {video['id'] for video in result['videos']} == {'cachedTrack1', 'newTrack0001'}
    video_calls = [params for url, params in client.calls if url.endswith('/videos')]
    assert [params['id'] for params in video_calls] == ['newTrack0001']
    assert result['quota_units_approx'] == 2


def test_stale_cached_record_is_refetched(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    config_path = tmp_path / 'music_channels.yaml'
    write_music_config(config_path, [{
        'name': 'One', 'handle': 'one', 'youtube_channel_id': 'UC1',
    }])
    output = tmp_path / 'out'
    output.mkdir()
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    cached = {
        'id': 'staleTrack01', 'title': 'Stale', 'channel': 'One', 'channel_id': 'UC1',
        'published_at': iso_now(), 'default_audio_language': 'en', 'default_language': 'en',
        'duration_seconds': 300, 'view_count': 1, 'like_count': 1, '_metadata_fetched_at': old,
    }
    (output / 'music.json').write_text(json.dumps({
        'generated_at': iso_now(),
        'videos': [cached],
    }))
    client = RecordingClient({'staleTrack01': raw_video('staleTrack01', 'PT5M')})

    result = curated_music_feed(
        config_path=str(config_path), client=client, output=str(output),
        rss_fetcher=lambda channel_id: [{'id': 'staleTrack01', 'published_at': iso_now()}],
    )

    assert [video['id'] for video in result['videos']] == ['staleTrack01']
    assert [params['id'] for _url, params in client.calls] == ['staleTrack01']


def test_failed_rss_fetch_falls_back_and_keeps_other_channels(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    config_path = tmp_path / 'music_channels.yaml'
    write_music_config(config_path, [
        {'name': 'Broken', 'handle': 'broken', 'youtube_channel_id': 'UC1'},
        {'name': 'Working', 'handle': 'working', 'youtube_channel_id': 'UC2'},
    ])
    client = FallbackRecordingClient(
        {
            'fallbackTrack': raw_video('fallbackTrack', 'PT5M', channel_id='UC1'),
            'workingTrack': raw_video('workingTrack', 'PT5M', channel_id='UC2'),
        },
        playlists={'UU1': [upload('fallbackTrack')]},
    )

    def rss_fetcher(channel_id):
        if channel_id == 'UC1':
            raise RuntimeError('RSS unavailable')
        return [{'id': 'workingTrack', 'published_at': iso_now()}]

    result = curated_music_feed(
        config_path=str(config_path), client=client, output=str(tmp_path / 'out'),
        rss_fetcher=rss_fetcher,
    )

    assert {video['id'] for video in result['videos']} == {'fallbackTrack', 'workingTrack'}
    assert [url.rsplit('/', 1)[-1] for url, _params in client.calls] == ['playlistItems', 'videos']
    assert result['quota_units_approx'] == 2
