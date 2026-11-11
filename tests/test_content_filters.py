import json
from datetime import datetime, timedelta, timezone

import pytest

from ytrec.core import (
    AI_MIN_DURATION_SECONDS,
    channel_display_cap,
    content_type_blocked,
    filter_ai_duration_and_promo_titles,
    is_official_brand_clip,
    is_official_short_promo,
    visible_language_blocked,
)
from ytrec.offline import rebuild_offline


NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


def video(**overrides):
    base = dict(
        id='video', title='Example', channel='Channel', channel_id='ch1',
        published_at=NOW.isoformat().replace('+00:00', 'Z'),
        default_audio_language='en', duration_seconds=600, view_count=100,
    )
    base.update(overrides)
    return base


# AI duration + promo-title gate --------------------------------------------

def test_ai_gate_drops_one_minute_official_promos():
    kept, dropped_short, dropped_title = filter_ai_duration_and_promo_titles([
        video(id='openai', title='GPT-Image-2.6: Faster image generation', channel='OpenAI',
              duration_seconds=88),
        video(id='nvidia', title='NVIDIA RTX Spark | A New Beginning', channel='NVIDIA',
              duration_seconds=76),
    ])
    assert kept == []
    assert dropped_short == 2
    assert dropped_title == 0


def test_ai_gate_drops_live_keynote_pregame_but_keeps_eight_minute_talk():
    kept, dropped_short, dropped_title = filter_ai_duration_and_promo_titles([
        video(id='pregame', title='NVIDIA GTC Berlin 2026 | Live Keynote Pregame',
              channel='NVIDIA', duration_seconds=6914),
        video(id='talk', title='How to Build a Software Factory That Improves Itself',
              channel='AI Engineer', duration_seconds=AI_MIN_DURATION_SECONDS),
    ])
    assert [item['id'] for item in kept] == ['talk']
    assert dropped_short == 0
    assert dropped_title == 1


def test_ai_gate_missing_duration_counts_as_zero():
    missing = video(id='missing', title='AI talk')
    missing.pop('duration_seconds')
    kept, dropped_short, _dropped_title = filter_ai_duration_and_promo_titles([missing])
    assert kept == []
    assert dropped_short == 1


def test_music_live_performance_is_not_touched_by_ai_live_title_rule(tmp_path):
    kexp = video(id='kexp', title='sub:shaman - Full Performance (Live on KEXP)',
                 channel='KEXP', channel_id='ch-kexp', duration_seconds=1548)
    blocked, _reason = content_type_blocked(kexp, 'music')
    assert not blocked
    summary, _updated = rebuild_offline(
        root=tmp_path, feeds={'music': {'videos': [kexp]}}, write=False,
    )
    assert summary['feeds']['music']['kept'] == 1


# Vendor / official promo shorts -------------------------------------------

def test_known_vendor_channels_are_official_brand_clips():
    for channel in ('OpenAI', 'NVIDIA', 'HyundaiIndia', 'Bambu Lab', 'Nintendo of America'):
        assert is_official_brand_clip(video(channel=channel))
    assert not is_official_brand_clip(video(title='A normal talk', channel='Lectures'))


def test_official_short_promo_drops_on_trending_but_long_non_promo_stays():
    assert is_official_short_promo(
        video(title='New model launch', channel='OpenAI', duration_seconds=90), 'trending',
    )
    assert not is_official_short_promo(
        video(title='A 20 minute interview', channel='OpenAI', duration_seconds=1200), 'trending',
    )
    assert not is_official_short_promo(
        video(title='A short community talk', channel='Community Group', duration_seconds=90),
        'community',
    )


# Content-type filter ------------------------------------------------------

@pytest.mark.parametrize('case', [
    dict(title='Mohabbat Episode 12 [Eng Sub] Feroze Khan - Nawal Saeed',
         channel='HAR PAL GEO'),
    dict(title='Mitti De Baway Ep 13 (Sub) 4th Nov 26 | Green TV',
         channel='Green TV Entertainment'),
    dict(title='Jochonay Fera | Aisha Khan | New Natok 2026',
         channel='Laser Vision Natok'),
    dict(title='Upin & Ipin - Kepiting Nipah (Full Episode)',
         channel='Upin & Ipin Indonesia'),
    dict(title='PHƯƠNG MỸ CHI x DTAP | GẠO CỦA TA | OFFICIAL MUSIC VIDEO',
         channel='Phương Mỹ Chi'),
    dict(title='တော်ပြီ Official Music Video - Zaw Gyi', channel='Zaw Gyi'),
    dict(title='Fadel Chaker - Nam El Layl | Official Music Video', channel='Fadel Chaker'),
    dict(title='Republicans turn against Hegseth after election losses', channel='CNN'),
    dict(title='The Legend of Zelda: Ocarina of Time – Overview Trailer – Nintendo Switch 2',
         channel='Nintendo of America'),
    dict(title='Humpty Dumpty Mix | CoComelon Nursery Rhymes & Kids Songs',
         channel='Cocomelon - Nursery Rhymes'),
    dict(title='Controlling Mom FORCES DAUGHTER To Be Popular',
         channel='Dhar Mann Studios'),
    dict(title='NEW! Ep 4859 - Taarak Mehta Ka Ooltah Chashmah',
         channel='Taarak Mehta ka Ooltah Chashmah'),
])
def test_trending_content_type_examples_are_blocked(case):
    blocked, reason = content_type_blocked(video(**case), 'trending')
    assert blocked
    assert reason


def test_trending_keeps_science_tech_and_documentary_talks():
    for item in (
        video(title='I finally saw quantum mechanics with my own eyes', channel='Veritasium'),
        video(title='I Solved Every Board Game', channel='Mark Rober'),
        video(title='What Actually Happens When You Die?', channel='Kurzgesagt – In a Nutshell'),
        video(title='I Let My Staff Upgrade the Office', channel='Linus Tech Tips'),
        video(title='Conflicting Our AI Future: Closing Keynote', channel='Stanford HAI'),
    ):
        assert not content_type_blocked(item, 'trending')[0]


def test_podcast_full_episode_audio_is_blocked():
    blocked, reason = content_type_blocked(
        video(title='Seinfeld - Full Episode (Audio)', channel='Acquired',
              duration_seconds=13819),
        'podcast',
    )
    assert blocked
    assert reason == 'full_episode'


def test_music_official_mv_is_not_a_content_filter_drop():
    blocked, _reason = content_type_blocked(
        video(title='Artist - Song (Official Music Video)', channel='Artist'), 'music',
    )
    assert not blocked


# Visible-title language net ----------------------------------------------

def test_visible_language_drops_foreign_scripts_even_when_audio_is_english():
    assert visible_language_blocked(video(title='တော်ပြီ Official Music Video',
                                          default_audio_language='en'))
    assert visible_language_blocked(video(title='জোছনায় ফেরা', default_audio_language='en'))
    assert visible_language_blocked(video(title='PHƯƠNG MỸ CHI | GẠO CỦA TA',
                                          default_audio_language='en'))
    assert visible_language_blocked(video(title='नमस्ते दुनिया', default_audio_language='en'))
    assert visible_language_blocked(video(title='مرحبا بالعالم', default_audio_language='en'))
    assert visible_language_blocked(video(title='สวัสดีชาวโลก', default_audio_language='en'))
    assert visible_language_blocked(video(title='안녕하세요 아이브', default_audio_language='en'))


def test_visible_language_keeps_english_chinese_and_rare_borrowed_chars():
    assert not visible_language_blocked(video(title='A perfectly normal English title'))
    assert not visible_language_blocked(video(title='中文标题（特别版）'))
    assert not visible_language_blocked(video(title='中文标题 ا'))
    assert not visible_language_blocked(video(title='English title with one ă'))


# Per-tab channel display cap ---------------------------------------------

def test_channel_display_cap_keeps_two_per_channel():
    videos = [video(id=f'v{index}', channel_id='same-channel', view_count=100 - index)
              for index in range(3)]
    kept, dropped = channel_display_cap(videos, per_channel=2)
    assert [item['id'] for item in kept] == ['v0', 'v1']
    assert dropped == 1


def test_channel_display_cap_keeps_highest_viewed_when_ordered():
    videos = [
        video(id='low', channel_id='same-channel', view_count=1),
        video(id='high', channel_id='same-channel', view_count=999),
        video(id='medium', channel_id='same-channel', view_count=100),
        video(id='other', channel_id='other-channel', view_count=500),
    ]
    kept, dropped = channel_display_cap(
        videos, per_channel=2, order_key=lambda item: -item['view_count'],
    )
    assert dropped == 1
    assert {item['id'] for item in kept} == {'high', 'medium', 'other'}


# Offline rebuild fixture --------------------------------------------------

def test_rebuild_offline_applies_ai_duration_and_trending_drama_gate(tmp_path):
    ai = [
        video(id='ai-short', title='Short AI update', channel='AI Channel',
              channel_id='ch-ai-short', duration_seconds=AI_MIN_DURATION_SECONDS - 1),
        video(id='ai-ok', title='Long AI research talk', channel='AI Channel 2',
              channel_id='ch-ai-ok', duration_seconds=AI_MIN_DURATION_SECONDS),
    ]
    trending = [
        video(id='drama', title='Mohabbat Episode 12 [Eng Sub]', channel='HAR PAL GEO',
              channel_id='ch-drama', duration_seconds=1200),
        video(id='science', title='I finally saw quantum mechanics', channel='Veritasium',
              channel_id='ch-veritasium', duration_seconds=3956),
    ]
    music = [
        video(id='kexp', title='sub:shaman - Full Performance (Live on KEXP)',
              channel='KEXP', channel_id='ch-kexp', duration_seconds=1548),
    ]
    for name, videos in (('ai', ai), ('trending', trending), ('music', music)):
        (tmp_path / f'{name}.json').write_text(json.dumps({'videos': videos}))

    summary, _updated = rebuild_offline(root=tmp_path, write=False)

    assert summary['feeds']['ai']['kept'] == 1
    assert summary['dropped_ai_short'] == 1
    assert summary['feeds']['trending']['kept'] == 1
    assert summary['dropped_content_type']['trending'] == 1
    assert summary['feeds']['music']['kept'] == 1
