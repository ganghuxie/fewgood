import json
from datetime import datetime, timedelta, timezone
from itertools import groupby

import pytest

from ytrec.core import (
    AI_MIN_DURATION_SECONDS,
    cap_same_event,
    channel_display_cap,
    content_type_blocked,
    filter_ai_duration_and_promo_titles,
    filter_trending_quality,
    interleave_by_channel,
    is_official_brand_clip,
    is_official_short_promo,
    is_community_classic,
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


def test_trending_blocks_faze_rug_vlog_but_keeps_veritasium():
    faze = video(title='I BOUGHT MY DREAM CAR!!', channel='FaZe Rug')
    veritasium = video(title='I finally saw quantum mechanics with my own eyes', channel='Veritasium')
    assert content_type_blocked(faze, 'trending') == (True, 'prank_vlog')
    assert not content_type_blocked(veritasium, 'trending')[0]

    # A title that only says "vlog" is not enough; Jason asked for vlog-prank /
    # flex content, not every travel or lab diary.
    assert not content_type_blocked(
        video(title='A week in the lab (vlog)', channel='Veritasium'),
        'trending',
    )[0]
    assert content_type_blocked(
        video(title='Epic prank vlog at the mall', channel='Unknown'),
        'trending',
    ) == (True, 'prank_vlog')


def test_trending_blocks_ytp_and_parody_edits():
    blocked, reason = content_type_blocked(
        video(title='BLUEY FLOOR TIME [YTP]', channel='Parody Uploads'),
        'trending',
    )
    assert blocked and reason == 'parody_edit'


def test_trending_blocks_samspedy_style_comedy_skit():
    blocked, reason = content_type_blocked(
        video(title='AFRICAN HOME: HALLOWEEN ZOMBIE', channel='SamSpedy'),
        'trending',
    )
    assert blocked and reason == 'comedy_skit'


def test_trending_blocks_hindi_song_but_not_english_tech_talk():
    blocked, reason = content_type_blocked(
        video(title='New Hindi Song | Prakash Jojawar', channel='Prakash Jojawar'),
        'trending',
    )
    assert blocked and reason == 'hindi_song'
    assert not content_type_blocked(
        video(title='A normal English tech talk about databases', channel='Engineering Talks'),
        'trending',
    )[0]


def test_trending_blocks_brand_collab_but_keeps_science_explainers():
    blocked, reason = content_type_blocked(
        video(title='Once upon a time in Mexico City | DHL x Holly Humberstone',
              channel='Holly Humberstone'),
        'trending',
    )
    assert blocked and reason == 'brand_collab'
    for channel, title in (
        ('Veritasium', 'I finally saw quantum mechanics with my own eyes'),
        ('Mark Rober', 'I Solved Every Board Game'),
    ):
        assert not content_type_blocked(video(title=title, channel=channel), 'trending')[0]


def test_trending_blocks_entertainment_factories_but_keeps_linus():
    for channel, title in (
        ('ZHC', 'MrBeast Trapped My Wife'),
        ('OG Crew', 'Confession Booth Challenge'),
        ('Quantastic', 'This fidget toy is impossible'),
    ):
        blocked, reason = content_type_blocked(video(title=title, channel=channel), 'trending')
        assert blocked and reason == 'entertainment'
    assert not content_type_blocked(
        video(title='I Let My Staff Upgrade the Office', channel='Linus Tech Tips'),
        'trending',
    )[0]


def test_trending_blocks_movie_reviews_and_indic_fan_edits():
    blocked, reason = content_type_blocked(
        video(title='Ramayana Movie Review | Yogi Bolta Hai', channel='YOGI BOLTA HAI',
              default_language='zxx'),
        'trending',
    )
    assert blocked and reason == 'movie_review'
    blocked, reason = content_type_blocked(
        video(title='Magale | Baththa | Sai Abhyankar | Vijay Sethupathi', channel='Moon editzz'),
        'trending',
    )
    assert blocked and reason == 'indic_romanized'
    assert not content_type_blocked(
        video(title='A normal English tech talk about databases', channel='Engineering Talks'),
        'trending',
    )[0]


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


def test_music_drops_actor_interviews_but_keeps_music_sessions():
    for title in (
        'Jenna Ortega and Amy Adams rate & slate Unpopular Opinions',
        'Olivia Colman and Alexander Skarsgård rate or slate your Unpopular Opinions',
        '“Pardon my arse!” Wicker’s Olivia Colman & Alexander Skarsgård on bed-breaking scenes & wrap gifts!',
    ):
        blocked, reason = content_type_blocked(video(title=title, channel='BBC Radio 1'), 'music')
        assert blocked and reason == 'non_music_interview'
    for title in (
        'A COLORS SHOW',
        'A COLORS INTERVIEW',
        'Tiny Desk Concert',
        'Essential Mix',
        'Zara Larsson live at Big Weekend',
        'KEXP full performance',
    ):
        assert not content_type_blocked(video(title=title, channel='Music'), 'music')[0]


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


def test_visible_language_blocks_portuguese_without_treating_cedilla_as_portuguese():
    assert visible_language_blocked(video(title='Perguntando a Profissão dos Passageiros…'))
    assert visible_language_blocked(video(title='Não deixe de assistir'))
    assert visible_language_blocked(video(title='A normal English title', default_language='pt-BR'))
    assert not visible_language_blocked(video(title='François présente un film'))
    assert not visible_language_blocked(video(title='The façade of a normal English video'))


def test_community_classic_requires_community_source_and_more_than_two_years():
    old = (NOW - timedelta(days=3 * 365)).isoformat().replace('+00:00', 'Z')
    recent = (NOW - timedelta(days=6)).isoformat().replace('+00:00', 'Z')
    assert is_community_classic(video(source='community', published_at=old), now=NOW)
    assert is_community_classic(video(pick_source='社区推荐', published_at=old), now=NOW)
    assert not is_community_classic(video(source='ai', published_at=old), now=NOW)
    assert not is_community_classic(video(source='podcast', published_at=old), now=NOW)
    assert not is_community_classic(video(source='community', published_at=recent), now=NOW)
    assert not is_community_classic(video(source='community', published_at='not-a-date'), now=NOW)


def test_trending_floor_restores_five_least_bad_items_to_thirty():
    good = [
        video(id=f'good-{index}', title=f'Documentary number {index}', channel=f'Channel {index}',
              view_count=1000 - index)
        for index in range(25)
    ]
    blocked = [
        video(id=f'blocked-{index}', title=f'BLUEY [YTP] part {index}', channel='Parody Uploads',
              view_count=index)
        for index in range(15)
    ]
    kept, dropped, restored, restored_reasons = filter_trending_quality(good + blocked)
    assert len(kept) == 30
    assert dropped['parody_edit'] == 15
    assert restored == 5
    assert restored_reasons['parody_edit'] == 5
    assert {item['id'] for item in kept if item['id'].startswith('blocked-')} == {
        f'blocked-{index}' for index in range(10, 15)
    }


def test_same_event_cap_keeps_two_highest_viewed_learjet_videos():
    learjets = [
        video(id='pilot', title='Shocking New Details in Deadly Learjet Crash!',
              channel='Pilot Debrief', channel_id='pilot', view_count=300),
        video(id='captain', title='Learjet Crash Update: NTSB Finds Tail Debris Miles Away',
              channel='Captain Steeeve', channel_id='captain', view_count=200),
        video(id='flying', title='Learjet 60 Crash: What Was She Trying to Tell the Captain?',
              channel='Flying for Money', channel_id='flying', view_count=100),
    ]
    kept, dropped_videos = cap_same_event(learjets)
    assert [item['id'] for item in kept] == ['pilot', 'captain']
    assert [item['id'] for item in dropped_videos] == ['flying']

    kept, reasons, restored, restored_reasons = filter_trending_quality(learjets, minimum=0)
    assert [item['id'] for item in kept] == ['pilot', 'captain']
    assert reasons['event_cap'] == 1
    assert restored == 0 and not restored_reasons


def test_trending_floor_runs_after_event_and_channel_caps():
    good = [
        video(id=f'good-{index}', title=f'Documentary number {index}',
              channel=f'Channel {index}', channel_id=f'good-{index}', view_count=1000 - index)
        for index in range(25)
    ]
    brand = [
        video(id=f'brand-{index}', title=f'DHL x Artist film {index}',
              channel=f'Brand Channel {index}', channel_id=f'brand-{index}', view_count=index)
        for index in range(6)
    ]
    learjets = [
        video(id=f'jet-{index}', title=f'Learjet crash report {index}',
              channel=f'News Channel {index}', channel_id=f'jet-{index}', view_count=50 - index)
        for index in range(3)
    ]
    kept, reasons, restored, restored_reasons = filter_trending_quality(
        good + brand + learjets, per_channel=2,
    )
    assert len(kept) == 30
    assert reasons['event_cap'] == 1
    assert reasons['brand_collab'] == 6
    assert restored == 3
    assert restored_reasons['event_cap'] == 1
    assert restored_reasons['brand_collab'] == 2


def test_interleave_by_channel_keeps_every_item_and_avoids_clumps():
    channels = [('colors', 9), ('npr', 8), ('kexp', 5)]
    videos = [
        video(id=f'{channel}-{index}', channel_id=channel, channel=channel)
        for channel, count in channels
        for index in range(count)
    ]
    interleaved = interleave_by_channel(videos)
    assert len(interleaved) == len(videos)
    assert {item['id'] for item in interleaved} == {item['id'] for item in videos}
    for channel, _count in channels:
        expected = [item['id'] for item in videos if item['channel_id'] == channel]
        actual = [item['id'] for item in interleaved if item['channel_id'] == channel]
        assert actual == expected
    runs = [len(list(group)) for _key, group in groupby(
        interleaved, key=lambda item: item['channel_id'],
    )]
    assert max(runs) == 1


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
    assert summary['feeds']['trending']['kept'] == 2
    assert summary['dropped_content_type']['trending'] == 1
    assert summary['restored_for_min']['trending'] == 1
    assert summary['feeds']['music']['kept'] == 1


def test_trending_drops_vendor_brand_film_over_three_minutes():
    hyundai = video(
        title="Hyundai’s India Journey: 30 Years of Scale, Trust and Progress",
        channel='HyundaiIndia', duration_seconds=330,
    )
    science = video(title='I finally saw quantum mechanics', channel='Veritasium', duration_seconds=3956)
    blocked, reason = content_type_blocked(hyundai, 'trending')
    assert blocked and reason == 'brand_promo'
    kept, _ = content_type_blocked(science, 'trending')
    assert not kept
