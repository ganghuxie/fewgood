"""Offline rebuild of the site feed JSONs.

Applies the zh/en language gate, per-channel day/7-day caps, the podcast
display cap, honest `why_good` backfill and the 今日精选 `picks` feed using only
data already stored under `site/src/data`. No YouTube API calls are made.
"""
import json
from pathlib import Path

from .core import (
    iso_now,
    duration,
    language_gate,
    apply_channel_caps_pool,
    podcast_display_cap,
    why_good_or_existing,
    build_picks,
    write_feed,
    _video_view,
    dual_topic_channel_ids,
    filter_ai_topic_videos,
    freshness_sort_key,
    drop_stale_videos,
    cap_ai_feed_display,
    visible_language_blocked,
    content_type_blocked,
    filter_trending_quality,
    is_official_short_promo,
    filter_ai_duration_and_promo_titles,
    channel_display_cap,
)

FEED_NAMES = ('trending', 'ai', 'podcast', 'music', 'editorial', 'videos')


def enrich_records(records, raws):
    """Update feed records with raw ``videos.list`` items (offline, no API calls).

    `raws` are already-fetched YouTube ``videos.list`` responses, so a reviewer
    can run one cheap metadata refresh and then re-check the language gate
    without refetching anything here. Missing fields are left untouched.
    """
    by_id = {}
    for raw in raws:
        if not raw or not raw.get('id'):
            continue
        snippet = raw.get('snippet', {})
        update = dict(
            title=snippet.get('title', ''),
            description=snippet.get('description', ''),
            channel=snippet.get('channelTitle', ''),
            channel_id=snippet.get('channelId', ''),
            published_at=snippet.get('publishedAt', ''),
            default_audio_language=snippet.get('defaultAudioLanguage') or None,
            default_language=snippet.get('defaultLanguage') or None,
        )
        if raw.get('contentDetails'):
            update['duration_seconds'] = duration(raw.get('contentDetails', {}).get('duration'))
        by_id[raw['id']] = update
    for record in records:
        update = by_id.get(record.get('id'))
        if update:
            record['default_audio_language'] = update.get('default_audio_language')
            record['default_language'] = update.get('default_language')
            for key in ('title', 'description', 'channel', 'channel_id', 'published_at', 'duration_seconds'):
                if update.get(key):
                    record[key] = update[key]
    return records


def load_feeds(root='site/src/data'):
    root = Path(root)
    feeds = {}
    for name in FEED_NAMES:
        path = root / f'{name}.json'
        if not path.exists():
            continue
        feeds[name] = json.loads(path.read_text())
    return feeds


def sort_by_view(videos):
    return sorted(videos, key=lambda video: (-_video_view(video), str(video.get('id', ''))))


def rebuild_offline(root='site/src/data', feeds=None, generated_at=None, write=True):
    """Rebuild every editorial feed from stored JSON (offline-first).

    Returns a dict summary plus the freshly computed `feeds` mapping. When
    `write` is False the JSON files are left untouched (used by tests).
    """
    root = Path(root)
    feeds = feeds if feeds is not None else load_feeds(root)

    editorial_feeds = {'trending', 'ai', 'podcast', 'music', 'editorial'}
    lang_kept = {}
    dropped_language = {}
    dropped_visible_language = {}
    dropped_content_type = {}
    dropped_official_short = {}
    trending_dropped_reasons = {}
    trending_restored_for_min = 0
    trending_restored_reasons = {}
    for name, feed in feeds.items():
        kept = []
        d_language = d_visible = d_content = d_official = 0
        editorial = name in editorial_feeds
        for video in feed.get('videos', []):
            if name == 'trending':
                # Trending quality (including its 30-item floor) is applied
                # once below, through the same helper used by the daily feed.
                if is_official_short_promo(video, name):
                    d_official += 1
                else:
                    kept.append(video)
                continue
            if not language_gate(video):
                d_language += 1
                continue
            if editorial:
                if visible_language_blocked(video, name):
                    d_visible += 1
                    continue
                blocked, _reason = content_type_blocked(video, name)
                if blocked:
                    d_content += 1
                    continue
            if is_official_short_promo(video, name if editorial else 'community'):
                d_official += 1
                continue
            kept.append(video)
        lang_kept[name] = kept
        dropped_language[name] = d_language
        dropped_visible_language[name] = d_visible
        dropped_content_type[name] = d_content
        dropped_official_short[name] = d_official

    if 'trending' in lang_kept:
        (lang_kept['trending'], trending_dropped_reasons,
         trending_restored_for_min, trending_restored_reasons) = filter_trending_quality(
            lang_kept['trending'],
        )
        dropped_language['trending'] = trending_dropped_reasons.get('language', 0)
        dropped_visible_language['trending'] = (
            trending_dropped_reasons.get('visible_language', 0)
            + trending_dropped_reasons.get('portuguese', 0)
        )
        dropped_content_type['trending'] = sum(
            count for reason, count in trending_dropped_reasons.items()
            if reason not in ('language', 'visible_language', 'portuguese')
        )

    dropped_ai_topic = 0
    if 'ai' in lang_kept:
        lang_kept['ai'], dropped_ai_topic = filter_ai_topic_videos(
            lang_kept['ai'], dual_topic_channel_ids(),
        )

    cap_kept, dropped_channel = apply_channel_caps_pool(lang_kept)

    dropped_stale = {}
    for name in ('ai', 'podcast', 'music', 'editorial'):
        if name in cap_kept:
            cap_kept[name], dropped_stale[name] = drop_stale_videos(cap_kept[name])

    dropped_ai_short = dropped_ai_promo_title = 0
    if 'ai' in cap_kept:
        cap_kept['ai'], dropped_ai_short, dropped_ai_promo_title = (
            filter_ai_duration_and_promo_titles(cap_kept['ai'])
        )

    dropped_podcast = 0
    if 'podcast' in cap_kept:
        cap_kept['podcast'], dropped_podcast = podcast_display_cap(cap_kept['podcast'])

    final = {}
    dropped_channel_display_cap = {}
    for name in FEED_NAMES:
        if name not in cap_kept:
            continue
        if name == 'trending':
            ordered = sort_by_view(cap_kept[name])
            ordered, dropped_channel_display_cap[name] = channel_display_cap(
                ordered, per_channel=2,
                order_key=lambda video: (-_video_view(video), str(video.get('id', ''))),
            )
            final[name] = ordered
        elif name in ('ai', 'podcast', 'music', 'editorial'):
            final[name] = sorted(cap_kept[name], key=freshness_sort_key)
        else:
            final[name] = cap_kept[name]

    feed_priority = {'videos': 0, 'community': 0, 'ai': 1, 'podcast': 2, 'music': 3, 'editorial': 4, 'trending': 5}
    seen_ids, unique = set(), {}
    for name in sorted(final, key=lambda feed: feed_priority.get(feed, 99)):
        kept_videos = []
        for video in final[name]:
            video_id = video.get('id')
            if video_id and video_id in seen_ids:
                continue
            if video_id:
                seen_ids.add(video_id)
            kept_videos.append(video)
        unique[name] = kept_videos
    final = unique

    for name, videos in final.items():
        if name in ('trending', 'podcast', 'music', 'editorial'):
            for rank, video in enumerate(sort_by_view(videos), 1):
                video['why_good'] = why_good_or_existing(video, name, rank=rank)
        elif name == 'ai':
            for video in videos:
                video['why_good'] = why_good_or_existing(video, 'ai')
        else:
            for video in videos:
                video['why_good'] = why_good_or_existing(video, 'community')

    dropped_ai_display_cap = 0
    dropped_ai_channel_display_cap = 0
    ai_pre_cap_count = 0
    if 'ai' in final:
        ai_pre_cap_count = len(final['ai'])
        final['ai'], dropped_ai_display_cap = cap_ai_feed_display(final['ai'])
        final['ai'], dropped_ai_channel_display_cap = channel_display_cap(
            final['ai'], per_channel=2,
        )

    pick_payload = build_picks(
        {'community': {'videos': final.get('videos') or []}, 'ai': {'videos': final.get('ai') or []},
         'podcast': {'videos': final.get('podcast') or []}, 'editorial': {'videos': final.get('editorial') or []}},
        generated_at=generated_at or iso_now(),
    )

    updated = {}
    if write:
        for name in FEED_NAMES:
            if name not in feeds:
                continue
            payload = dict(feeds[name], videos=final.get(name, []),
                           dropped_language=dropped_language.get(name, 0),
                           dropped_channel=dropped_channel.get(name, 0),
                           dropped_content_type=dropped_content_type.get(name, 0),
                           dropped_visible_language=dropped_visible_language.get(name, 0),
                           dropped_official_short=dropped_official_short.get(name, 0))
            if name == 'podcast':
                payload['dropped_podcast_display_cap'] = dropped_podcast
            if name == 'ai':
                payload['dropped_ai_topic'] = int(feeds[name].get('dropped_ai_topic') or 0) + dropped_ai_topic
                payload['dropped_ai_display_cap'] = dropped_ai_display_cap
                payload['dropped_channel_display_cap'] = dropped_ai_channel_display_cap
                payload['dropped_ai_short'] = dropped_ai_short
                payload['dropped_ai_promo_title'] = dropped_ai_promo_title
                payload['pre_cap_count'] = ai_pre_cap_count
                payload['final_count'] = len(final.get('ai', []))
            if name == 'trending':
                payload['dropped_channel_display_cap'] = dropped_channel_display_cap.get(name, 0)
                payload['final_count'] = len(final.get(name, []))
                payload['dropped_quality_reasons'] = dict(sorted(trending_dropped_reasons.items()))
                for reason, count in trending_dropped_reasons.items():
                    payload[f'dropped_{reason}'] = count
                payload['restored_for_min'] = trending_restored_for_min
                if trending_restored_reasons:
                    payload['restored_for_min_reasons'] = dict(sorted(trending_restored_reasons.items()))
            if name in ('ai', 'podcast', 'music', 'editorial'):
                payload['dropped_stale'] = int(feeds[name].get('dropped_stale') or 0) + dropped_stale.get(name, 0)
            if name == 'videos':
                payload['feed'] = 'community'
            write_feed(name, payload, root)
            updated[name] = payload
        write_feed('picks', pick_payload, root)
        updated['picks'] = pick_payload

    summary = {
        'generated_at': pick_payload['generated_at'],
        'feeds': {name: {'kept': len(final.get(name, [])), 'dropped_language': dropped_language.get(name, 0), 'dropped_channel': dropped_channel.get(name, 0)} for name in feeds},
        'dropped_ai_topic': dropped_ai_topic,
        'dropped_ai_display_cap': dropped_ai_display_cap,
        'dropped_ai_channel_display_cap': dropped_ai_channel_display_cap,
        'dropped_ai_short': dropped_ai_short,
        'dropped_ai_promo_title': dropped_ai_promo_title,
        'dropped_channel_display_cap': dropped_channel_display_cap,
        'dropped_content_type': dropped_content_type,
        'dropped_visible_language': dropped_visible_language,
        'dropped_official_short': dropped_official_short,
        'dropped_stale': dropped_stale,
        'dropped_podcast_display_cap': dropped_podcast,
        'dropped_quality_reasons': {'trending': dict(sorted(trending_dropped_reasons.items()))},
        'restored_for_min': {'trending': trending_restored_for_min},
        'restored_for_min_reasons': {'trending': dict(sorted(trending_restored_reasons.items()))},
        'picks': len(pick_payload['videos']),
    }
    return summary, updated
