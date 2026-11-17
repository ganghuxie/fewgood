import json

import pytest
import yaml

from ytrec.core import (
    ai_feed,
    build_picks,
    filter_ai_topic_videos,
    is_ai_topic_video,
    iso_now,
    matches_ai_topic_keywords,
)
from ytrec.offline import rebuild_offline


LEX_ID = 'UCSHZKyawb77ixDdsGog4iWA'
UKRAINE_TITLE = (
    'Ukraine War: Putin, Zelenskyy, Trump, Drones and the Future of Warfare '
    '| Lex Fridman Podcast #504'
)
UKRAINE_DESCRIPTION = (
    'A conversation about the Ukraine war, Putin, Zelenskyy, Trump, drones, '
    'and the future of warfare.\n\n'
    '*SPONSORS:*\nCheck out our sponsors:\n'
    'Go to https://lexfridman.com/s/ for an AI agent for customer service,\n'
    'AI-powered voice dictation, and an AI-powered answer engine.'
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
    ukraine = record('2hJkprFnzhY', UKRAINE_TITLE, description=UKRAINE_DESCRIPTION)

    assert not matches_ai_topic_keywords(ukraine)
    assert not is_ai_topic_video(ukraine)
    assert filter_ai_topic_videos([ukraine]) == ([], 1)
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
        '2hJkprFnzhY': raw_video('2hJkprFnzhY', UKRAINE_TITLE, description=UKRAINE_DESCRIPTION),
        'lex-ai': raw_video('lex-ai', AI_TITLE),
    })

    result = ai_feed(
        channels_file=str(channels_path), client=client, output=str(output),
        rss_fetcher=lambda channel_id: [
            {'id': '2hJkprFnzhY', 'published_at': iso_now()},
            {'id': 'lex-ai', 'published_at': iso_now()},
        ],
    )

    assert [video['id'] for video in result['videos']] == ['lex-ai']
    assert result['dropped_ai_topic'] == 1


def test_rebuild_offline_removes_non_ai_lex_from_ai_but_keeps_podcast(tmp_path):
    ukraine = record('2hJkprFnzhY', UKRAINE_TITLE, description=UKRAINE_DESCRIPTION)
    write_feed(tmp_path, 'ai', [ukraine])
    write_feed(tmp_path, 'podcast', [ukraine])

    summary, updated = rebuild_offline(root=tmp_path)

    assert updated['ai']['videos'] == []
    assert updated['ai']['dropped_ai_topic'] == 1
    assert [video['id'] for video in updated['podcast']['videos']] == ['2hJkprFnzhY']
    assert summary['dropped_ai_topic'] == 1
    assert all(video.get('pick_source') != 'AI前沿' for video in updated['picks']['videos'])
    assert any(video['id'] == '2hJkprFnzhY' and video.get('pick_source') == '播客'
               for video in updated['picks']['videos'])


@pytest.mark.parametrize('marker', [
    'Check out our sponsors',
    'Thank you to our sponsors',
    'This episode is brought to you by',
    '*SPONSORS:*',
    'SPONSORS:',
    'Go to https://lexfridman.com/s/',
])
@pytest.mark.parametrize('raw', [False, True])
def test_sponsor_markers_exclude_ad_keywords(marker, raw):
    factory = raw_video if raw else record
    episode = factory('2hJkprFnzhY', UKRAINE_TITLE,
                      description=f'A discussion of the Ukraine war.\n{marker} AI-powered tools.')
    assert not matches_ai_topic_keywords(episode)
    assert not is_ai_topic_video(episode)


def test_topic_matches_before_sponsors_and_in_title():
    assert matches_ai_topic_keywords(record(
        'description-ai', 'A conversation about the future',
        description='Meet our guest.\nWe discuss OpenAI and AGI in depth.\n'
                    '*SPONSORS:*\nOther products.',
    ))
    assert is_ai_topic_video(record('title-ai', AI_TITLE, description=UKRAINE_DESCRIPTION))


def test_dedicated_ai_channel_does_not_require_topic_keyword():
    episode = record('hugging-face', 'Pi Durable EXPLAINED: Build Always-On Agents with Local Models')
    episode['channel_id'] = 'UCHlNU7kIZhRgSbhHvFoy72w'
    assert not matches_ai_topic_keywords(episode)
    assert is_ai_topic_video(episode)
    assert filter_ai_topic_videos([episode]) == ([episode], 0)
    assert is_ai_topic_video(episode, dual_channel_ids={LEX_ID})
    assert filter_ai_topic_videos([episode], dual_channel_ids={LEX_ID}) == ([episode], 0)


def test_rebuild_offline_does_not_move_rejected_ai_episode_to_other_feeds(tmp_path):
    ukraine = record('2hJkprFnzhY', UKRAINE_TITLE, description=UKRAINE_DESCRIPTION)
    write_feed(tmp_path, 'ai', [ukraine])
    write_feed(tmp_path, 'podcast', [])

    summary, updated = rebuild_offline(root=tmp_path)

    assert updated['ai']['videos'] == []
    assert updated['ai']['dropped_ai_topic'] == 1
    assert summary['dropped_ai_topic'] == 1
    assert updated['podcast']['videos'] == []
    assert updated['picks']['videos'] == []


YC_ID = 'UCcefcZRL2oaA_uBNeo5UOWg'


def yc_record(video_id, title, **kwargs):
    episode = record(video_id, title, **kwargs)
    episode.update(channel='Y Combinator', channel_id=YC_ID)
    return episode


def test_yc_theranos_is_removed_without_other_feed_placement(tmp_path):
    episode = yc_record(
        'iXWSYlAX5Lg', 'Inside Theranos with ex-Employee Tyler Shultz',
        description='Tyler Shultz discusses Elizabeth Holmes, whistleblowing, '
                    'and the failed blood tests at Theranos.',
    )
    assert not matches_ai_topic_keywords(episode)
    assert not is_ai_topic_video(episode)
    assert filter_ai_topic_videos([episode]) == ([], 1)
    assert build_picks({'ai': {'videos': [episode]}})['videos'] == []
    write_feed(tmp_path, 'ai', [episode])
    write_feed(tmp_path, 'podcast', [])
    summary, updated = rebuild_offline(root=tmp_path)
    assert updated['ai']['videos'] == []
    assert summary['dropped_ai_topic'] == 1
    assert updated['podcast']['videos'] == []
    assert updated['picks']['videos'] == []


@pytest.mark.parametrize('title,description', [
    ('The Rise Of AI Coworkers', 'Building and deploying Grok Bot.'),
    ('', 'We discuss frontier AI labs.\nSPONSORS: Other products.'),
    ('Building the future', 'A discussion of ChatGPT.\nSPONSORS: Other products.'),
])
def test_yc_ai_title_or_pre_sponsor_body_is_kept(title, description):
    episode = yc_record('y1-9yeYLJUo', title, description=description)
    assert matches_ai_topic_keywords(episode)
    assert is_ai_topic_video(episode)
    assert filter_ai_topic_videos([episode]) == ([episode], 0)


@pytest.mark.parametrize('url', [
    'https://www.transformernews.ai/p/x',
    'https://example.com/affair-ai.html',
    'https://bfl.ai/blog',
    'www.transformernews.ai/p/x',
])
@pytest.mark.parametrize('raw', [False, True])
def test_url_tokens_do_not_supply_ai_topic_keywords(url, raw):
    episode = (raw_video if raw else yc_record)(
        'url-only', f'Company history {url}', description=f'Read more: {url}',
    )
    assert not matches_ai_topic_keywords(episode)
    assert not is_ai_topic_video(episode)


def test_inference_and_training_pair_is_a_narrow_ml_signal():
    title = 'Why Inference Matters 12x More Than Training | YC Paper Club'
    assert matches_ai_topic_keywords(yc_record('paper', title))
    assert is_ai_topic_video(yc_record(
        'paper', title, description='We discuss compute costs during inference and training.',
    ))
    for title in ('10 Habits PhDs Must Unlearn To Build a Startup',
                  'Sales training for founders', 'Causal inference in market research'):
        assert not matches_ai_topic_keywords(yc_record('non-ai', title))


def test_ai_feed_uses_explicit_yc_gate(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-only')
    channels_path = tmp_path / 'channels.yaml'
    channels_path.write_text(yaml.safe_dump({'channels': [{
        'name': 'Y Combinator', 'youtube_channel_id': YC_ID,
    }]}))
    raws = {}
    for video_id, title in [('iXWSYlAX5Lg', 'Inside Theranos with ex-Employee Tyler Shultz'),
                            ('y1-9yeYLJUo', 'The Rise Of AI Coworkers')]:
        raw = raw_video(video_id, title)
        raw['snippet'].update(channelId=YC_ID, channelTitle='Y Combinator')
        raws[video_id] = raw
    result = ai_feed(
        channels_file=str(channels_path), client=RecordingClient(raws),
        output=str(tmp_path / 'out'),
        rss_fetcher=lambda channel_id: [{'id': video_id, 'published_at': iso_now()}
                                       for video_id in raws],
    )
    assert [v['id'] for v in result['videos']] == ['y1-9yeYLJUo']
    assert result['dropped_ai_topic'] == 1
