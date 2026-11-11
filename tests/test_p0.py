import json
from datetime import datetime, timezone, timedelta
from ytrec.core import (
    language_ok,
    language_gate,
    dedupe_channel_caps,
    apply_channel_caps_pool,
    podcast_display_cap,
    why_good_for,
    build_picks,
    PICKS_MIN_DURATION_SECONDS,
    PICKS_OFFICIAL_MIN_DURATION_SECONDS,
    is_official_brand_clip,
    published_at_dt,
    within_freshness_window,
    freshness_bucket,
    freshness_sort_key,
    drop_stale_videos,
)


def video(**overrides):
    base = dict(id='a', title='Example', channel='Channel', channel_id='ch1',
                published_at='2026-11-01T00:00:00Z', duration_seconds=600,
                view_count=100, like_count=1)
    base.update(overrides)
    return base


def _days_ago_iso(days, now=None):
    now = now or datetime.now(timezone.utc)
    return (now - timedelta(days=days)).isoformat().replace('+00:00', 'Z')


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
    podcast_with_reason = [video(id='p0', channel_id='pc0', published_at='2026-11-01T00:00:00Z', view_count=9, why_good='近 30 天同类长视频播放第 1')]
    podcast_without_reason = [video(id='p1', channel_id='pc1', published_at='2026-11-01T00:00:00Z', view_count=8)]
    picks = build_picks({'community': {'videos': community}, 'ai': {'videos': ai}, 'podcast': {'videos': podcast_with_reason + podcast_without_reason}})
    ids = [v['id'] for v in picks['videos']]
    assert len(ids) <= 10
    assert 'p1' not in ids
    assert all(v.get('why_good') for v in picks['videos'])
    assert all(v.get('pick_source') for v in picks['videos'])
    assert all(int(v.get('duration_seconds') or 0) >= PICKS_MIN_DURATION_SECONDS for v in picks['videos'])


def test_picks_require_eight_minutes():
    short = video(id='short', recommenders=99, months=12, span_days=400, duration_seconds=PICKS_MIN_DURATION_SECONDS - 1)
    long = video(id='long', recommenders=98, months=12, span_days=400, duration_seconds=PICKS_MIN_DURATION_SECONDS)
    picks = build_picks({'community': {'videos': [short, long]}, 'ai': {'videos': []}, 'podcast': {'videos': []}})
    ids = [v['id'] for v in picks['videos']]
    assert 'short' not in ids
    assert 'long' in ids


def test_picks_missing_duration_counts_as_zero():
    missing = video(id='missing', recommenders=99, months=12, span_days=400)
    missing.pop('duration_seconds')
    picks = build_picks({'community': {'videos': [missing]}, 'ai': {'videos': []}, 'podcast': {'videos': []}})
    assert picks['videos'] == []


def test_picks_never_pick_trending_even_when_other_pools_are_small():
    trending = [video(id='mrbeast', title='MrBeast Lab Ep 1', channel='MrBeast', duration_seconds=900,
                      view_count=999, why_good='近 30 天同类长视频播放第 1')]
    picks = build_picks({'community': {'videos': []}, 'ai': {'videos': []}, 'podcast': {'videos': []},
                         'trending': {'videos': trending}})
    assert picks['videos'] == []


def test_build_picks_tolerates_missing_or_none_editorial():
    community = [video(id='c0', channel_id='ch-c', published_at=_days_ago_iso(1),
                       recommenders=12, months=3)]
    base = {'community': {'videos': community}, 'ai': {'videos': []}, 'podcast': {'videos': []}}
    for feeds in (base, dict(base, editorial={'videos': None})):
        picks = build_picks(feeds)
        assert [item['id'] for item in picks['videos']] == ['c0']


def test_rebuild_offline_without_editorial_feed(tmp_path):
    from ytrec.offline import rebuild_offline

    community = video(id='community0', channel_id='ch-community', published_at=_days_ago_iso(1),
                      recommenders=12, months=3)
    ai = video(id='ai0', channel_id='ch-ai', published_at=_days_ago_iso(1), view_count=20)
    podcast = video(id='podcast0', channel_id='ch-podcast', published_at=_days_ago_iso(1), view_count=10)
    for name, items in (('videos', [community]), ('ai', [ai]), ('podcast', [podcast])):
        (tmp_path / f'{name}.json').write_text(json.dumps({'videos': items}))

    summary, updated = rebuild_offline(root=tmp_path)

    assert summary['picks'] > 0
    assert updated['picks']['videos']
    assert not (tmp_path / 'editorial.json').exists()


def test_picks_exclude_official_brand_clip_under_three_minutes():
    clip = video(id='official', title='Song (Official Video)', channel='Artist',
                 duration_seconds=PICKS_OFFICIAL_MIN_DURATION_SECONDS - 1,
                 recommenders=99, months=12, span_days=400)
    picks = build_picks({'community': {'videos': [clip]}, 'ai': {'videos': []}, 'podcast': {'videos': []}})
    assert picks['videos'] == []


def test_official_brand_clip_detection():
    assert is_official_brand_clip(video(title='Foo (Official Video)'))
    assert is_official_brand_clip(video(title='Foo Trailer'))
    assert is_official_brand_clip(video(title='Foo MV'))
    assert is_official_brand_clip(video(title='官方 MV'))
    assert is_official_brand_clip(video(channel='Artist Official'))
    assert not is_official_brand_clip(video(title='A normal talk', channel='Lectures'))


# P0-6 freshness gate ------------------------------------------------------

def test_freshness_window_and_bucket():
    now = datetime(2026, 11, 11, tzinfo=timezone.utc)
    recent = video(published_at=_days_ago_iso(3, now))
    middle = video(published_at=_days_ago_iso(20, now))
    stale = video(published_at=_days_ago_iso(31, now))
    missing = video()
    missing.pop('published_at')
    assert within_freshness_window(recent, now=now)
    assert within_freshness_window(middle, now=now)
    assert not within_freshness_window(stale, now=now)
    assert not within_freshness_window(missing, now=now)
    assert freshness_bucket(recent, now=now) == 0
    assert freshness_bucket(middle, now=now) == 1
    assert freshness_bucket(stale, now=now) == 2
    assert freshness_bucket(missing, now=now) == 2


def test_drop_stale_videos_counts_excluded():
    now = datetime.now(timezone.utc)
    videos = [
        video(id='fresh', published_at=_days_ago_iso(6, now)),
        video(id='stale', published_at=_days_ago_iso(31, now)),
        video(id='missing'),
    ]
    videos[2].pop('published_at')
    kept, dropped = drop_stale_videos(videos, now=now)
    assert [v['id'] for v in kept] == ['fresh']
    assert dropped == 2


def test_build_picks_drops_stale_ai_and_podcast_but_keeps_fresh():
    ai = [
        video(id='ai-stale', channel_id='a1', published_at=_days_ago_iso(31), view_count=999),
        video(id='ai-fresh', channel_id='a2', published_at=_days_ago_iso(6), view_count=1),
    ]
    podcast = [
        video(id='pod-stale', channel_id='p1', published_at=_days_ago_iso(31), view_count=999,
              why_good='近 30 天同类长视频播放第 1'),
        video(id='pod-fresh', channel_id='p2', published_at=_days_ago_iso(6), view_count=1,
              why_good='近 30 天同类长视频播放第 2'),
    ]
    picks = build_picks({'community': {'videos': []}, 'ai': {'videos': ai}, 'podcast': {'videos': podcast}})
    ids = [v['id'] for v in picks['videos']]
    assert 'ai-stale' not in ids
    assert 'pod-stale' not in ids
    assert 'ai-fresh' in ids
    assert 'pod-fresh' in ids


def test_build_picks_keeps_old_community_classics():
    classic = video(id='sugar', channel_id='c1', published_at=_days_ago_iso(6000),
                    recommenders=99, months=60, span_days=5000)
    picks = build_picks({'community': {'videos': [classic]}, 'ai': {'videos': []}, 'podcast': {'videos': []}})
    assert [v['id'] for v in picks['videos']] == ['sugar']


def test_freshness_sort_prefers_recent_over_higher_views():
    now = datetime.now(timezone.utc)
    older = video(id='older', channel_id='a1', published_at=_days_ago_iso(20, now), view_count=999)
    recent = video(id='recent', channel_id='a2', published_at=_days_ago_iso(3, now), view_count=1)
    ordered = sorted([older, recent], key=lambda v: freshness_sort_key(v, now=now))
    assert [v['id'] for v in ordered] == ['recent', 'older']


def test_published_at_dt_parses_and_rejects_bad_dates():
    assert published_at_dt(video(published_at='2026-11-01T00:00:00Z')).tzinfo is not None
    bad = video(published_at='not-a-date')
    assert published_at_dt(bad) is None


def test_enrich_records_merges_videos_list_fields():
    from ytrec.offline import enrich_records
    records = [dict(id='a', title='old', channel='old channel', channel_id='ch1')]
    raws = [{'id': 'a', 'snippet': {'title': 'New', 'channelTitle': 'New Channel', 'channelId': 'ch1',
                                    'publishedAt': '2026-11-01T00:00:00Z',
                                    'defaultAudioLanguage': 'en', 'defaultLanguage': 'en'},
             'contentDetails': {'duration': 'PT10M'}}]
    enrich_records(records, raws)
    assert records[0]['default_audio_language'] == 'en'
    assert records[0]['default_language'] == 'en'
    assert records[0]['title'] == 'New'
    assert records[0]['duration_seconds'] == 600
