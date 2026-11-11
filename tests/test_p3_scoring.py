from datetime import datetime, timedelta, timezone

import pytest

from ytrec.core import PICKS_MIN_DURATION_SECONDS, build_picks, video_record
from ytrec.scoring import (
    has_chapters_from_description,
    independent_community_source_count,
    is_clickbait_title,
    score_video,
)


NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


def days_ago(days):
    return (NOW - timedelta(days=days)).isoformat().replace('+00:00', 'Z')


def video(video_id='a', **overrides):
    record = dict(
        id=video_id, title=f'Title {video_id}', channel=f'Channel {video_id}',
        channel_id=f'ch-{video_id}', published_at=days_ago(2),
        duration_seconds=1200, view_count=1000, like_count=10,
        comment_count=0, why_good='rule generated',
    )
    record.update(overrides)
    return record


def test_worked_example_c_hits_the_final_clamp():
    candidate = video(
        'sugar', title='Sugar: The Bitter Truth', channel='UCTV', channel_id='UC-uctv',
        published_at=days_ago(6000), duration_seconds=5377,
        view_count=10000, like_count=400, comment_count=0,
        recommenders=198, source='community',
    )
    result = score_video(
        candidate, channel_median_views=1000, already_picked_from_channel=0,
        now=NOW, sources=[],
    )

    assert result.parts['s_ext'] == pytest.approx(0.9274930007)
    assert result.parts['s_rel'] == pytest.approx(1.0)
    assert result.parts['s_eng'] == pytest.approx(0.80)
    assert result.parts['s_str'] == pytest.approx(0.75)
    assert result.parts['raw'] == pytest.approx(0.8934972003)
    assert result.parts['c_tier'] == pytest.approx(1.3)
    assert result.parts['c_freq'] == pytest.approx(1.0)
    assert result.parts['c_fresh'] == pytest.approx(1.0)
    assert result == pytest.approx(1.0)


def test_worked_example_b_style_uses_tier_two_multiplier():
    candidate = video(
        'claude-prompts', title='Your Old Prompts Are Making Claude Worse - Lance Martin, Anthropic',
        channel='AI Engineer', channel_id='UCLKPca3kwwd-B59HNr-_lvA',
        published_at=days_ago(2), duration_seconds=3840,
        view_count=68000, like_count=1360, comment_count=0,
        has_chapters=True, has_captions=False, source='ai',
    )
    result = score_video(candidate, channel_median_views=40000, now=NOW)

    assert result.parts['s_ext'] == pytest.approx(0.0)
    assert result.parts['s_rel'] == pytest.approx(0.2304489214)
    assert result.parts['s_eng'] == pytest.approx(0.40)
    assert result.parts['s_str'] == pytest.approx(0.90)
    assert result.parts['c_tier'] == pytest.approx(1.2)
    assert result == pytest.approx(0.33, abs=0.005)


def test_stage_one_rejects_short_and_trending_only_items_even_with_high_scores():
    short = video(
        'short', duration_seconds=PICKS_MIN_DURATION_SECONDS - 1,
        view_count=10_000_000, like_count=900_000, recommenders=500, source='community',
    )
    assert build_picks({'community': {'videos': [short]}, 'ai': {'videos': []},
                        'podcast': {'videos': []}}, now=NOW)['videos'] == []

    trending = video(
        'trending', duration_seconds=1200, view_count=10_000_000,
        like_count=900_000, recommenders=500, why_good='来自频道「Channel trending」的近期长视频',
    )
    assert build_picks({'community': {'videos': []}, 'ai': {'videos': []},
                        'podcast': {'videos': []}, 'trending': {'videos': [trending]}},
                       now=NOW)['videos'] == []


def test_mix_is_preserved_and_ai_column_orders_by_score():
    community = [
        video(f'c{i}', channel_id=f'community-{i}', recommenders=200 - i * 25,
              published_at=days_ago(600 + i), duration_seconds=3600)
        for i in range(4)
    ]
    ai = [
        video('ai-high', channel_id='ai-high-channel', published_at=days_ago(2),
              view_count=1000, like_count=60),
        video('ai-mid-1', channel_id='ai-mid-1-channel', published_at=days_ago(3),
              view_count=1000, like_count=10),
        video('ai-mid-2', channel_id='ai-mid-2-channel', published_at=days_ago(4),
              view_count=1000, like_count=10),
        video('ai-low', channel_id='ai-low-channel', published_at=days_ago(10),
              view_count=5_000_000, like_count=10),
    ]
    podcast = [
        video('p0', channel_id='podcast-0', why_good='播客推荐一'),
        video('p1', channel_id='podcast-1', why_good='播客推荐二'),
    ]

    picks = build_picks({
        'community': {'videos': community}, 'ai': {'videos': ai},
        'podcast': {'videos': podcast},
    }, now=NOW)
    ids = [item['id'] for item in picks['videos']]

    assert len(picks['videos']) == 10
    assert sum(item['source'] == 'community' for item in picks['videos']) == 4
    assert sum(item['source'] == 'ai' for item in picks['videos']) == 4
    assert sum(item['source'] == 'podcast' for item in picks['videos']) == 2
    assert ids.index('ai-high') < ids.index('ai-low')
    assert all(item['score'] <= 1.0 for item in picks['videos'])
    assert all(item['score_parts']['raw'] >= 0 for item in picks['videos'])


def test_community_external_signal_and_independent_source_boost():
    community = video('community', recommenders=198, community_sources=['hn', 'reddit'])
    result = score_video(community, channel_median_views=1000, now=NOW, sources=[], section='community')
    assert independent_community_source_count(community) == 2
    assert result.parts['s_ext'] == pytest.approx(1.0)

    no_signal = video('ai', published_at=days_ago(2), recommenders=None, source='ai')
    assert score_video(no_signal, channel_median_views=None, now=NOW)['s_ext'] == 0

    inferred = video('inferred', published_at=days_ago(6000), recommenders=50)
    inferred_result = score_video(inferred, channel_median_views=None, now=NOW)
    assert inferred_result.parts['tier'] == 4
    assert inferred_result.parts['c_fresh'] == pytest.approx(1.0)


def test_freshness_multiplier_for_editorial_and_community_exemption():
    middle = video('middle', published_at=days_ago(10), source='ai')
    recent = video('recent', published_at=days_ago(6), source='ai')
    classic = video('classic', published_at=days_ago(6000), recommenders=50, source='community')

    assert score_video(middle, channel_median_views=1000, now=NOW)['c_fresh'] == pytest.approx(0.7)
    assert score_video(recent, channel_median_views=1000, now=NOW)['c_fresh'] == pytest.approx(1.0)
    assert score_video(classic, channel_median_views=1000, now=NOW)['c_fresh'] == pytest.approx(1.0)


def test_frequency_decay_and_exclusion():
    candidate = video('repeat', recommenders=100, source='community')
    zero = score_video(candidate, channel_median_views=1000, already_picked_from_channel=0, now=NOW)
    one = score_video(candidate, channel_median_views=1000, already_picked_from_channel=1, now=NOW)
    two = score_video(candidate, channel_median_views=1000, already_picked_from_channel=2, now=NOW)
    three = score_video(candidate, channel_median_views=1000, already_picked_from_channel=3, now=NOW)

    assert zero.parts['c_freq'] == pytest.approx(1.0)
    assert one.parts['c_freq'] == pytest.approx(0.5)
    assert two.parts['c_freq'] == pytest.approx(0.2)
    assert three.excluded
    assert three == pytest.approx(0.0)


def test_build_picks_rescored_repeat_channel_at_selection_time():
    community = [
        video('first', channel_id='same-channel', recommenders=200, published_at=days_ago(600)),
        video('second', channel_id='same-channel', recommenders=190, published_at=days_ago(601)),
    ]
    picks = build_picks({'community': {'videos': community}, 'ai': {'videos': []},
                         'podcast': {'videos': []}}, limit=2, now=NOW)

    assert [item['id'] for item in picks['videos']] == ['first', 'second']
    assert picks['videos'][0]['score_parts']['c_freq'] == pytest.approx(1.0)
    assert picks['videos'][1]['score_parts']['c_freq'] == pytest.approx(0.5)


def test_clickbait_and_chapter_helpers_are_conservative():
    assert is_clickbait_title('你绝对想不到这个结局')
    assert is_clickbait_title('SHOCKING AI NEWS')
    assert is_clickbait_title('You Won\u2019t Believe What Happened')
    assert is_clickbait_title('THIS TITLE IS ALMOST ALL CAPS')
    assert is_clickbait_title('🔥🔥🔥 New model')
    assert not is_clickbait_title('A normal technical talk')
    assert has_chapters_from_description('0:00 Intro\n12:34 Deep dive')
    assert not has_chapters_from_description('00:00 only one timestamp')


def test_video_record_stores_scoring_metadata():
    record = video_record({
        'id': 'meta',
        'snippet': {
            'title': 'A technical talk', 'channelTitle': 'Channel', 'channelId': 'UC1',
            'publishedAt': days_ago(1),
            'description': '0:00 Intro\n20:00 Main section',
        },
        'contentDetails': {'duration': 'PT25M', 'caption': 'true'},
        'statistics': {'viewCount': '1000', 'likeCount': '20', 'commentCount': '7'},
    })

    assert record['comment_count'] == 7
    assert record['has_captions'] is True
    assert record['has_chapters'] is True
