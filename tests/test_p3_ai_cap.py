import json
from datetime import datetime, timedelta, timezone

import yaml

from ytrec.core import (
    AI_FEED_DISPLAY_CAP,
    ai_feed,
    cap_ai_feed_display,
    iso_now,
    write_feed_if_not_sharply_smaller,
)
from ytrec.offline import rebuild_offline


NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


def days_ago(days):
    return (NOW - timedelta(days=days)).isoformat().replace('+00:00', 'Z')


def eligible_video(video_id, *, channel_id=None, published_at=None, likes=10, views=10000):
    return {
        'id': video_id,
        'title': f'AI update {video_id}',
        'channel': f'Channel {channel_id or video_id}',
        'channel_id': channel_id or f'ch-{video_id}',
        'published_at': published_at or days_ago(2),
        'default_audio_language': 'en',
        'default_language': 'en',
        'duration_seconds': 3600,
        'view_count': views,
        'like_count': likes,
    }


def raw_video(video_id, channel_id, likes):
    return {
        'id': video_id,
        'snippet': {
            'publishedAt': iso_now(),
            'title': f'AI update {video_id}',
            'channelTitle': f'Channel {channel_id}',
            'channelId': channel_id,
            'defaultAudioLanguage': 'en',
            'defaultLanguage': 'en',
        },
        'contentDetails': {'duration': 'PT1H'},
        'statistics': {'viewCount': '10000', 'likeCount': str(likes)},
    }


class RecordingClient:
    def __init__(self, raws):
        self.raws = raws

    def get(self, url, params, youtube=False):
        assert url.endswith('/videos'), url
        return {'items': [self.raws[video_id] for video_id in params['id'].split(',')]}


def channel_config(tmp_path, count):
    channels = [{
        'name': f'AI Channel {index}',
        'youtube_channel_id': f'UCcap{index:03d}',
    } for index in range(count)]
    path = tmp_path / 'ai_channels.yaml'
    path.write_text(yaml.safe_dump({'channels': channels}, allow_unicode=True))
    return path, channels


def test_ai_feed_keeps_40_highest_scored_of_50(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    channels_path, channels = channel_config(tmp_path, 50)
    raws, rss = {}, {}
    for index, channel in enumerate(channels):
        video_id = f'ai-cap-{index:02d}'
        channel_id = channel['youtube_channel_id']
        raws[video_id] = raw_video(video_id, channel_id, 10 + index * 10)
        rss[channel_id] = [{'id': video_id, 'published_at': iso_now()}]

    output = tmp_path / 'out'
    result = ai_feed(
        channels_file=str(channels_path), client=RecordingClient(raws), output=str(output),
        rss_fetcher=lambda channel_id: rss[channel_id],
    )

    kept = {video['id'] for video in result['videos']}
    assert len(result['videos']) == AI_FEED_DISPLAY_CAP
    assert kept == {f'ai-cap-{index:02d}' for index in range(10, 50)}
    assert result['dropped_ai_display_cap'] == 10
    assert result['pre_cap_count'] == 50
    assert result['final_count'] == 40
    assert len(json.loads((output / 'ai.json').read_text())['videos']) == 40


def test_cap_prefers_higher_scored_older_video_over_lower_scored_newer():
    older = eligible_video('older', channel_id='ch-older', published_at=days_ago(10), likes=1000)
    newer = eligible_video('newer', channel_id='ch-newer', published_at=days_ago(2), likes=0)
    fillers = [
        eligible_video(f'filler-{index}', channel_id=f'ch-filler-{index}',
                       published_at=days_ago(5), likes=300)
        for index in range(39)
    ]

    kept, dropped = cap_ai_feed_display([older, newer, *fillers], now=NOW)
    kept_ids = {video['id'] for video in kept}

    assert len(kept) == AI_FEED_DISPLAY_CAP
    assert dropped == 1
    assert 'older' in kept_ids
    assert 'newer' not in kept_ids


def test_30_eligible_ai_videos_are_all_kept():
    videos = [eligible_video(f'ai-{index:02d}', likes=10 + index) for index in range(30)]

    kept, dropped = cap_ai_feed_display(videos, now=NOW)

    assert len(kept) == 30
    assert dropped == 0
    assert {video['id'] for video in kept} == {video['id'] for video in videos}


def test_ai_feed_writes_capped_feed_when_pre_cap_count_is_healthy(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    output = tmp_path / 'out'
    output.mkdir()
    channels_path, channels = channel_config(tmp_path, 150)
    previous, rss = [], {}
    for index, channel in enumerate(channels):
        video_id = f'ai-prev-{index:03d}'
        channel_id = channel['youtube_channel_id']
        previous.append(eligible_video(
            video_id, channel_id=channel_id, published_at=iso_now(), likes=10 + index,
        ))
        rss[channel_id] = [{'id': video_id, 'published_at': iso_now()}]
    (output / 'ai.json').write_text(json.dumps({
        'generated_at': iso_now(), 'videos': previous,
    }))

    result = ai_feed(
        channels_file=str(channels_path), client=object(), output=str(output),
        rss_fetcher=lambda channel_id: rss[channel_id],
    )

    saved = json.loads((output / 'ai.json').read_text())
    assert result['videos'] is not previous
    assert len(result['videos']) == 40
    assert len(saved['videos']) == 40
    assert result['pre_cap_count'] == 150
    assert result['final_count'] == 40
    assert result['dropped_ai_display_cap'] == 110


def test_sparse_pre_cap_refresh_still_keeps_previous_ai_feed(tmp_path):
    previous = {'generated_at': iso_now(), 'videos': [eligible_video(f'old-{i}') for i in range(150)]}
    path = tmp_path / 'ai.json'
    path.write_text(json.dumps(previous))
    payload = {
        'generated_at': iso_now(), 'pre_cap_count': 74, 'final_count': 40,
        'videos': [eligible_video(f'new-{i}') for i in range(40)],
    }

    result = write_feed_if_not_sharply_smaller('ai', payload, tmp_path)

    assert result == previous
    assert len(json.loads(path.read_text())['videos']) == 150


def test_rebuild_offline_caps_ai_feed_at_40(tmp_path):
    videos = [
        eligible_video(f'offline-{index:02d}', published_at=iso_now(), likes=10 + index * 10)
        for index in range(50)
    ]
    (tmp_path / 'ai.json').write_text(json.dumps({
        'generated_at': iso_now(), 'videos': videos,
    }))

    summary, updated = rebuild_offline(root=tmp_path)

    kept = {video['id'] for video in updated['ai']['videos']}
    saved = json.loads((tmp_path / 'ai.json').read_text())
    assert len(updated['ai']['videos']) == 40
    assert len(saved['videos']) == 40
    assert updated['ai']['dropped_ai_display_cap'] == 10
    assert updated['ai']['pre_cap_count'] == 50
    assert updated['ai']['final_count'] == 40
    assert summary['dropped_ai_display_cap'] == 10
    assert all(
        video['id'] in kept
        for video in updated['picks']['videos']
        if video.get('source') == 'ai'
    )
