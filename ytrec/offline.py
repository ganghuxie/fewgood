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
    why_good_for,
    build_picks,
    write_feed,
    _video_view,
)

FEED_NAMES = ('trending', 'ai', 'podcast', 'music', 'videos')


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
            for key in ('title', 'channel', 'channel_id', 'published_at', 'duration_seconds'):
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

    lang_kept = {}
    dropped_language = {}
    for name, feed in feeds.items():
        kept, dropped = [], 0
        for video in feed.get('videos', []):
            if language_gate(video):
                kept.append(video)
            else:
                dropped += 1
        lang_kept[name] = kept
        dropped_language[name] = dropped

    cap_kept, dropped_channel = apply_channel_caps_pool(lang_kept)

    dropped_podcast = 0
    if 'podcast' in cap_kept:
        cap_kept['podcast'], dropped_podcast = podcast_display_cap(cap_kept['podcast'])

    final = {}
    for name in FEED_NAMES:
        if name not in cap_kept:
            continue
        if name in ('trending', 'ai', 'podcast', 'music'):
            final[name] = sort_by_view(cap_kept[name])
        else:
            final[name] = cap_kept[name]

    for name, videos in final.items():
        if name in ('trending', 'podcast', 'music'):
            for rank, video in enumerate(videos, 1):
                video['why_good'] = why_good_for(video, name, rank=rank)
        elif name == 'ai':
            for video in videos:
                video['why_good'] = why_good_for(video, 'ai')
        else:
            for video in videos:
                video['why_good'] = why_good_for(video, 'community')

    pick_payload = build_picks(
        {'community': {'videos': final.get('videos')}, 'ai': {'videos': final.get('ai')}, 'podcast': {'videos': final.get('podcast')}},
        generated_at=generated_at or iso_now(),
    )

    updated = {}
    if write:
        for name in FEED_NAMES:
            if name not in feeds:
                continue
            payload = dict(feeds[name], videos=final.get(name, []),
                           dropped_language=dropped_language.get(name, 0),
                           dropped_channel=dropped_channel.get(name, 0))
            if name == 'podcast':
                payload['dropped_podcast_display_cap'] = dropped_podcast
            if name == 'videos':
                payload['feed'] = 'community'
            write_feed(name, payload, root)
            updated[name] = payload
        write_feed('picks', pick_payload, root)
        updated['picks'] = pick_payload

    summary = {
        'generated_at': pick_payload['generated_at'],
        'feeds': {name: {'kept': len(final.get(name, [])), 'dropped_language': dropped_language.get(name, 0), 'dropped_channel': dropped_channel.get(name, 0)} for name in feeds},
        'dropped_podcast_display_cap': dropped_podcast,
        'picks': len(pick_payload['videos']),
    }
    return summary, updated
