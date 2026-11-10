import json
from ytrec.core import (
    language_ok,
    language_gate,
    dedupe_channel_caps,
    apply_channel_caps_pool,
    podcast_display_cap,
    why_good_for,
    build_picks,
)


def video(**overrides):
    base = dict(id='a', title='Example', channel='Channel', channel_id='ch1',
                published_at='2026-11-01T00:00:00Z', duration_seconds=600,
                view_count=100, like_count=1)
    base.update(overrides)
    return base


# P0-1 language gate --------------------------------------------------------

def test_language_gate_accepts_zh_and_en():
    assert language_ok('zh')
    assert language_ok('en')
    assert language_ok('zh-CN')
    assert language_ok('en-US')
    assert language_ok('zh-Hans', 'en')
    assert language_ok(None, 'en-GB')
    assert language_ok(None, None, 'A perfectly ordinary English title')


def test_language_gate_rejects_other_language_codes():
    assert not language_ok('hi')
    assert not language_ok('id')
    assert not language_ok(None, 'ko')
    assert not language_ok('ja', None, 'English title ignored because audio lang decides')


def test_language_gate_falls_through_on_missing_or_neutral():
    assert language_ok('und', 'zh')
    assert language_ok('zxx', None, 'English')
    assert language_ok('', 'en')
    assert language_ok(None, None, 'English')


def test_language_gate_rejects_foreign_script_titles():
    assert not language_ok(None, None, '안녕하세요 아이브 MV')
    assert not language_ok(None, None, 'नमस्ते दुनिया')
    assert not language_ok(None, None, 'مرحبا بالعالم')
    assert not language_ok(None, None, 'สวัสดีชาวโลก')
    assert not language_ok(None, None, 'İstanbul ışıkları')


def test_language_gate_allows_umlauts_and_cedilla_alone():
    assert language_ok(None, None, 'Grüße aus München')
    assert language_ok(None, None, 'François çava bien')


def test_language_gate_record_wrapper():
    assert language_gate(video(title='Hello world', default_audio_language='en'))
    assert not language_gate(video(title='Hello', default_audio_language='hi'))


# P0-2 channel caps ---------------------------------------------------------

def test_channel_caps_same_day_keeps_one():
    videos = [
        video(id='a', channel_id='ch1', published_at='2026-11-01T00:00:00Z', view_count=1),
        video(id='b', channel_id='ch1', published_at='2026-11-01T12:00:00Z', view_count=2),
    ]
    kept, dropped = dedupe_channel_caps(videos, feed_name='trending')
    assert [v['id'] for v in kept] == ['b']
    assert dropped == 1


def test_channel_caps_rolling_week_keeps_three():
    videos = [
        video(id='a', channel_id='ch1', published_at='2026-11-01T00:00:00Z', view_count=4),
        video(id='b', channel_id='ch1', published_at='2026-11-03T00:00:00Z', view_count=3),
        video(id='c', channel_id='ch1', published_at='2026-11-05T00:00:00Z', view_count=2),
        video(id='d', channel_id='ch1', published_at='2026-11-06T00:00:00Z', view_count=1),
    ]
    kept, dropped = dedupe_channel_caps(videos, feed_name='trending')
    assert sorted(v['id'] for v in kept) == ['a', 'b', 'c']
    assert dropped == 1


def test_channel_caps_pool_prioritizes_community_then_ai():
    pool = {
        'trending': [video(id='t', channel_id='ch1', published_at='2026-11-01T00:00:00Z', view_count=999)],
        'ai': [video(id='a', channel_id='ch1', published_at='2026-11-01T00:00:00Z', view_count=50)],
        'community': [video(id='c', channel_id='ch1', published_at='2026-11-01T00:00:00Z', recommenders=30)],
    }
    kept, dropped = apply_channel_caps_pool(pool)
    assert [v['id'] for v in kept['community']] == ['c']
    assert kept['ai'] == []
    assert kept['trending'] == []
    assert dropped['ai'] == 1
    assert dropped['trending'] == 1


def test_podcast_display_cap_two_per_channel_in_top_twenty():
    videos = [video(id=f'p{i}', channel_id='ch1', published_at=f'2026-11-{i + 1:02d}T00:00:00Z', view_count=100 - i) for i in range(4)]
    kept, dropped = podcast_display_cap(videos)
    assert sum(1 for v in kept if v['channel_id'] == 'ch1') == 2
    assert dropped == 2


# P0-5 why_good + picks -----------------------------------------------------

def test_why_good_community_and_ai():
    community = video(recommenders=30, months=40, span_days=4000)
    assert '30 位 HN 用户' in why_good_for(community, 'community')
    assert len(why_good_for(community, 'community')) <= 40
    ai = video(channel='A very long channel name that must be truncated', view_count=1)
    reason = why_good_for(ai, 'ai')
    assert 'AI 前沿精选频道' in reason and len(reason) <= 40


def test_picks_require_why_good_and_never_exceed_ten():
    community = [video(id=f'c{i}', channel_id=f'cc{i}', published_at='2018-01-01T00:00:00Z',
                       recommenders=100 - i, months=60, span_days=3000) for i in range(8)]
    ai = [video(id=f'a{i}', channel_id=f'ac{i}', published_at='2026-11-01T00:00:00Z',
                view_count=100 - i, why_good=why_good_for(video(id=f'a{i}'), 'ai')) for i in range(8)]
    trending_with_reason = [video(id='t0', channel_id='tc0', published_at='2026-11-01T00:00:00Z', view_count=9, why_good='近 30 天同类长视频播放第 1')]
    trending_without_reason = [video(id='t1', channel_id='tc1', published_at='2026-11-01T00:00:00Z', view_count=8)]
    picks = build_picks({'community': {'videos': community}, 'ai': {'videos': ai}, 'trending': {'videos': trending_with_reason + trending_without_reason}})
    ids = [v['id'] for v in picks['videos']]
    assert len(ids) <= 10
    assert 't1' not in ids
    assert all(v.get('why_good') for v in picks['videos'])
    assert all(v.get('pick_source') for v in picks['videos'])
