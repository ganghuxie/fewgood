import json
from pathlib import Path
import yaml
from ytrec.podcast_whitelist import (
    load_music_channels,
    duration_in_bounds,
    curated_music_feed,
    MUSIC_MIN_DURATION,
    MUSIC_MAX_DURATION,
)


def test_music_whitelist_has_named_channels_and_bounds():
    payload, channels, minimum, maximum = load_music_channels()
    names = {channel['name'] for channel in channels}
    for required in ('NPR Music', 'KEXP', 'COLORS', 'Cercle', 'Boiler Room', 'BBC Radio 1'):
        assert required in names
    assert minimum == 180
    assert maximum == 7200
    assert MUSIC_MIN_DURATION == 180
    assert MUSIC_MAX_DURATION == 7200


def test_music_duration_bounds():
    assert not duration_in_bounds(179, MUSIC_MIN_DURATION, MUSIC_MAX_DURATION)
    assert not duration_in_bounds(7201, MUSIC_MIN_DURATION, MUSIC_MAX_DURATION)
    assert duration_in_bounds(181, MUSIC_MIN_DURATION, MUSIC_MAX_DURATION)


def raw_video(video_id, duration_iso):
    return {
        'id': video_id,
        'snippet': {
            'publishedAt': '2026-11-01T00:00:00Z',
            'title': f'Title {video_id}',
            'channelTitle': 'Channel',
            'channelId': 'UC1',
            'defaultAudioLanguage': 'en',
        },
        'contentDetails': {'duration': duration_iso},
        'statistics': {'viewCount': '10', 'likeCount': '1'},
    }


def test_curated_music_feed_keeps_only_in_range_tracks(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    config_path = tmp_path / 'music_channels.yaml'
    config_path.write_text(yaml.safe_dump({
        'min_duration_seconds': 180,
        'max_duration_seconds': 7200,
        'channels': [{'name': 'Test Channel', 'handle': 'test', 'youtube_channel_id': 'UC1'}],
    }, allow_unicode=True))

    rss_calls = []

    def rss_fetcher(channel_id):
        rss_calls.append(channel_id)
        return [{'id': vid, 'published_at': '2026-11-01T00:00:00Z'} for vid in ('short', 'long', 'ok')]

    class YT:
        def get(self, url, params, youtube=False):
            assert url.endswith('/videos'), url
            ids = params['id'].split(',')
            raws = {
                'short': raw_video('short', 'PT2M59S'),   # 179 seconds
                'long': raw_video('long', 'PT2H1S'),      # 7201 seconds
                'ok': raw_video('ok', 'PT3M1S'),          # 181 seconds
            }
            return {'items': [raws[vid] for vid in ids]}

    result = curated_music_feed(
        config_path=str(config_path), client=YT(), output=str(tmp_path / 'out'),
        rss_fetcher=rss_fetcher,
    )
    ids = [v['id'] for v in result['videos']]
    assert ids == ['ok']
    assert rss_calls == ['UC1']
    assert result['min_duration_seconds'] == 180
    assert result['max_duration_seconds'] == 7200
    assert 'dropped_podcast_display_cap' not in result
    saved = json.loads((tmp_path / 'out' / 'music.json').read_text())
    assert [v['id'] for v in saved['videos']] == ['ok']
