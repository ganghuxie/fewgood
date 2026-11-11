import json

import yaml

from ytrec.core import (
    ai_feed,
    build_picks,
    is_ai_topic_video,
    iso_now,
    matches_ai_topic_keywords,
)
from ytrec.offline import rebuild_offline


LEX_ID = 'UCSHZKyawb77ixDdsGog4iWA'
UKRAINE_TITLE = (
    'Russia-Ukraine War: Putin, Zelenskyy, Drones and the Future of Warfare '
    '| Lex Fridman Podcast #504'
)
AI_TITLE = 'OpenAI, Anthropic, and the Future of AGI | Lex Fridman Podcast'


def record(video_id, title, *, description='', published_at=None):
    published_at = published_at or iso_now()
    return {
        'id': video_id,
        'title': title,
        'description': description,
        'channel': 'Lex Fridman',
        'channel_id': LEX_ID,
        'published_at': published_at,
        'default_audio_language': 'en',
        'default_language': 'en',
        'duration_seconds': 7200,
        'view_count': 1000,
        'like_count': 100,
    }


def raw_video(video_id, title, *, description=''):
    return {
        'id': video_id,
        'snippet': {
            'publishedAt': iso_now(),
            'title': title,
            'description': description,
            'channelTitle': 'Lex Fridman',
            'channelId': LEX_ID,
            'defaultAudioLanguage': 'en',
            'defaultLanguage': 'en',
        },
        'contentDetails': {'duration': 'PT2H'},
        'statistics': {'viewCount': '1000', 'likeCount': '100'},
    }


class RecordingClient:
    def __init__(self, raws):
        self.raws = raws
        self.calls = []

    def get(self, url, params, youtube=False):
        self.calls.append((url, dict(params)))
        assert url.endswith('/videos')
        return {'items': [self.raws[video_id] for video_id in params['id'].split(',')]}


def write_feed(root, name, videos):
    (root / f'{name}.json').write_text(json.dumps({'generated_at': iso_now(), 'videos': videos}))


def test_lex_ukraine_episode_is_not_ai_topic_or_an_ai_pick():
    ukraine = record('lex-ukraine', UKRAINE_TITLE)

    assert not is_ai_topic_video(ukraine)
    picks = build_picks({
        'community': {'videos': []},
        'ai': {'videos': [ukraine]},
        'podcast': {'videos': []},
    })
    assert picks['videos'] == []


def test_lex_ai_episode_matches_keywords_and_can_enter_ai_picks():
    episode = record('lex-ai', AI_TITLE)

    assert is_ai_topic_video(episode)
    picks = build_picks({
        'community': {'videos': []},
        'ai': {'videos': [episode]},
        'podcast': {'videos': []},
    })
    assert [video['id'] for video in picks['videos']] == ['lex-ai']
    assert picks['videos'][0]['pick_source'] == 'AI前沿'


def test_ai_topic_keywords_match_title_or_description_with_wordish_boundaries():
    assert matches_ai_topic_keywords(record('one', 'A.I. safety and LLMs'))
    assert matches_ai_topic_keywords(record(
        'two', 'A conversation about the future',
        description='We discuss machine learning, alignment, and foundation models.',
    ))
    assert not matches_ai_topic_keywords(record(
        'three', 'Russia-Ukraine War: Drones and the Future of Warfare',
        description='A conversation about maintaining a family said to be affected by war.',
    ))
    assert not matches_ai_topic_keywords(record('four', 'The Transformers movie'))


def test_ai_feed_drops_cached_non_ai_lex_episode_before_channel_caps(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    channels_path = tmp_path / 'ai_channels.yaml'
    channels_path.write_text(yaml.safe_dump({'channels': [{
        'name': 'Lex Fridman', 'youtube_channel_id': LEX_ID,
    }]}, allow_unicode=True))
    output = tmp_path / 'out'
    client = RecordingClient({
        'lex-ukraine': raw_video('lex-ukraine', UKRAINE_TITLE),
        'lex-ai': raw_video('lex-ai', AI_TITLE),
    })

    result = ai_feed(
        channels_file=str(channels_path), client=client, output=str(output),
        rss_fetcher=lambda channel_id: [
            {'id': 'lex-ukraine', 'published_at': iso_now()},
            {'id': 'lex-ai', 'published_at': iso_now()},
        ],
    )

    assert [video['id'] for video in result['videos']] == ['lex-ai']
    assert result['dropped_ai_topic'] == 1


def test_rebuild_offline_removes_non_ai_lex_from_ai_but_keeps_podcast(tmp_path):
    ukraine = record('lex-ukraine', UKRAINE_TITLE)
    write_feed(tmp_path, 'ai', [ukraine])
    write_feed(tmp_path, 'podcast', [ukraine])

    summary, updated = rebuild_offline(root=tmp_path)

    assert updated['ai']['videos'] == []
    assert updated['ai']['dropped_ai_topic'] == 1
    assert [video['id'] for video in updated['podcast']['videos']] == ['lex-ukraine']
    assert summary['dropped_ai_topic'] == 1
    assert all(video.get('pick_source') != 'AI前沿' for video in updated['picks']['videos'])
    assert any(video['id'] == 'lex-ukraine' and video.get('pick_source') == '播客'
               for video in updated['picks']['videos'])
