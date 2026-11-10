#!/usr/bin/env python3
"""Fill view counts, dates, durations, and channel avatars for V2 topic videos.

Uses local editorial/backfill/channels data first. Remaining gaps are filled
with videos.list and channels.list only (1 unit per 50 ids). Cap 60 units.
Writes a private quota file so data/quota.json is not touched. Does not print
API keys.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ytrec.core import Client, YOUTUBE_API, duration, iso_now, youtube_key  # noqa: E402

PUBLIC_TOPICS = ROOT / 'site/public/topics'
BACKFILL = ROOT / 'site/src/data/music-subtopic-backfill.json'
STATS = ROOT / 'site/src/data/topic-video-stats.json'
CHANNELS = ROOT / 'site/src/data/channels.json'
FEED_FILES = ['ai.json', 'podcast.json', 'music.json', 'trending.json', 'videos.json']
KEEP_FIXTURES = {'c-plus-plus', 'c-sharp', 'cafe', 'no-results', 'quota-deferred', 'waiting-demo'}


def load_json(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def first(*values):
    for value in values:
        if value is None or value == '':
            continue
        return value
    return None


def positive_int(value):
    if value is None or value == '':
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def local_maps():
    videos = {}
    for name in FEED_FILES:
        payload = load_json(ROOT / 'site/src/data' / name, {})
        for video in payload.get('videos') or []:
            vid = video.get('id') or video.get('video_id')
            if vid:
                videos[vid] = video
    catalog = load_json(ROOT / 'site/src/data/catalog.json', [])
    for video in catalog:
        vid = video.get('id') or video.get('video_id')
        if vid:
            videos.setdefault(vid, video)
    backfill = load_json(BACKFILL, {'channels': []})
    bf_videos = {}
    bf_channels = {}
    for channel in backfill.get('channels') or []:
        if channel.get('id'):
            bf_channels[channel['id']] = channel
        for video in channel.get('videos') or []:
            vid = video.get('id')
            if vid:
                bf_videos[vid] = video
    channels = {row['id']: row for row in (load_json(CHANNELS, {}).get('channels') or []) if row.get('id')}
    return videos, channels, bf_videos, bf_channels, backfill


def topic_files():
    files = []
    for path in sorted(PUBLIC_TOPICS.glob('*.json')):
        if path.name in {'index.json', 'status.json'}:
            continue
        payload = load_json(path)
        if payload.get('topic_id') in KEEP_FIXTURES:
            continue
        files.append((path, payload))
    return files


def merge_video(video, local, channels, bf_videos):
    vid = video.get('video_id') or video.get('id')
    src = local.get(vid) or {}
    bf = bf_videos.get(vid) or {}
    channel_id = first(video.get('channel_id'), src.get('channel_id'), bf.get('channel_id'), '') or ''
    view = first(positive_int(src.get('view_count')), positive_int(video.get('view_count')), positive_int(bf.get('view_count')))
    published = first(video.get('published_at'), src.get('published_at'), bf.get('published_at'), '') or ''
    dur = first(positive_int(src.get('duration_seconds')), positive_int(video.get('duration_seconds')), positive_int(video.get('duration')), positive_int(bf.get('duration_seconds')))
    thumb = first(
        video.get('channel_thumbnail'),
        src.get('channel_thumbnail'),
        (channels.get(channel_id) or {}).get('thumbnail'),
        '',
    ) or ''
    title = first(video.get('title'), src.get('title'), bf.get('title'), vid)
    channel_title = first(video.get('channel_title'), video.get('channel'), src.get('channel'), bf.get('channel'), 'YouTube')
    return {
        'video_id': vid,
        'title': title,
        'channel_title': channel_title,
        'channel_id': channel_id,
        'published_at': published,
        'url': video.get('url') or f'https://www.youtube.com/watch?v={vid}',
        'thumbnail': video.get('thumbnail') or src.get('thumb') or bf.get('thumb') or f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg',
        'duration_seconds': dur or 0,
        'view_count': view,
        'channel_thumbnail': thumb,
    }


def chunks(items, size=50):
    seq = list(items)
    for offset in range(0, len(seq), size):
        yield seq[offset:offset + size]


def fetch_videos(client, ids):
    fetched = {}
    units = 0
    key = youtube_key()
    for batch in chunks(ids):
        payload = client.get(
            YOUTUBE_API + 'videos',
            dict(part='snippet,contentDetails,statistics', id=','.join(batch), key=key),
            youtube=True,
        )
        units += 1
        for raw in payload.get('items') or []:
            snippet = raw.get('snippet') or {}
            stats = raw.get('statistics') or {}
            view = positive_int(stats.get('viewCount')) if 'viewCount' in stats else None
            fetched[raw['id']] = {
                'title': snippet.get('title') or '',
                'channel_title': snippet.get('channelTitle') or '',
                'channel_id': snippet.get('channelId') or '',
                'published_at': snippet.get('publishedAt') or '',
                'duration_seconds': duration((raw.get('contentDetails') or {}).get('duration')),
                'view_count': view,
            }
    return fetched, units


def fetch_channels(client, ids):
    fetched = {}
    units = 0
    key = youtube_key()
    for batch in chunks(ids):
        payload = client.get(
            YOUTUBE_API + 'channels',
            dict(part='snippet', id=','.join(batch), key=key),
            youtube=True,
        )
        units += 1
        for raw in payload.get('items') or []:
            thumbs = ((raw.get('snippet') or {}).get('thumbnails') or {})
            thumb = (thumbs.get('medium') or thumbs.get('high') or thumbs.get('default') or {}).get('url') or ''
            fetched[raw['id']] = {
                'title': (raw.get('snippet') or {}).get('title') or '',
                'thumbnail': thumb,
            }
    return fetched, units


def apply_fetched(row, video_info, channel_info):
    extra = video_info.get(row['video_id']) or {}
    if extra.get('view_count') is not None and row.get('view_count') is None:
        row['view_count'] = extra['view_count']
    if extra.get('published_at') and not row.get('published_at'):
        row['published_at'] = extra['published_at']
    if extra.get('duration_seconds') and not row.get('duration_seconds'):
        row['duration_seconds'] = extra['duration_seconds']
    if extra.get('channel_id') and not row.get('channel_id'):
        row['channel_id'] = extra['channel_id']
    if extra.get('channel_title') and (not row.get('channel_title') or row.get('channel_title') == 'YouTube'):
        row['channel_title'] = extra['channel_title']
    channel = channel_info.get(row.get('channel_id')) or {}
    if channel.get('thumbnail') and not row.get('channel_thumbnail'):
        row['channel_thumbnail'] = channel['thumbnail']
    return row


def compact_row(row):
    payload = {
        'video_id': row['video_id'],
        'title': row['title'],
        'channel_title': row['channel_title'],
        'published_at': row.get('published_at') or '',
        'url': row['url'],
        'thumbnail': row['thumbnail'],
        'duration_seconds': row.get('duration_seconds') or 0,
        'channel_id': row.get('channel_id') or '',
    }
    if row.get('view_count') is not None:
        payload['view_count'] = row['view_count']
    if row.get('channel_thumbnail'):
        payload['channel_thumbnail'] = row['channel_thumbnail']
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cap', type=int, default=60)
    parser.add_argument('--quota-path', default='/tmp/v2-topic-enrich-quota.json')
    args = parser.parse_args()

    local, channels, bf_videos, bf_channels, backfill = local_maps()
    files = topic_files()
    merged_by_id = {}
    updated_files = []
    for path, payload in files:
        rows = [merge_video(video, local, channels, bf_videos) for video in payload.get('videos') or []]
        updated_files.append((path, payload, rows))
        for row in rows:
            merged_by_id[row['video_id']] = row

    need_videos = [
        vid for vid, row in merged_by_id.items()
        if row.get('view_count') is None or not row.get('published_at') or not row.get('duration_seconds')
    ]
    need_channels = sorted({
        row['channel_id'] for row in merged_by_id.values()
        if row.get('channel_id') and not row.get('channel_thumbnail')
    })

    video_units = -(-len(need_videos) // 50) if need_videos else 0
    channel_units = -(-len(need_channels) // 50) if need_channels else 0
    if video_units + channel_units > args.cap:
        # Prefer video stats; trim channel batches if needed.
        max_video_units = min(video_units, args.cap)
        need_videos = need_videos[: max_video_units * 50]
        video_units = -(-len(need_videos) // 50) if need_videos else 0
        remain = args.cap - video_units
        need_channels = need_channels[: max(0, remain) * 50]
        channel_units = -(-len(need_channels) // 50) if need_channels else 0

    video_info, used_v = {}, 0
    channel_info, used_c = {}, 0
    if need_videos or need_channels:
        client = Client(interval=0.2, db=None, quota_limit=args.cap, quota_path=args.quota_path)
        if need_videos:
            video_info, used_v = fetch_videos(client, need_videos)
        if need_channels:
            channel_info, used_c = fetch_channels(client, need_channels)

    for vid, extra in video_info.items():
        row = merged_by_id.get(vid)
        if row:
            apply_fetched(row, {vid: extra}, {})
    for row in merged_by_id.values():
        apply_fetched(row, {}, channel_info)

    for path, payload, rows in updated_files:
        payload['videos'] = [compact_row(merged_by_id[row['video_id']]) for row in rows]
        payload['stats_enriched_at'] = iso_now()
        write_json(path, payload)

    stats = {
        'generated_at': iso_now(),
        'quota_units': {'videos_list': used_v, 'channels_list': used_c, 'units': used_v + used_c},
        'videos': {
            vid: {
                key: value for key, value in {
                    'view_count': row.get('view_count'),
                    'published_at': row.get('published_at') or '',
                    'duration_seconds': row.get('duration_seconds') or 0,
                    'channel_id': row.get('channel_id') or '',
                    'channel_title': row.get('channel_title') or '',
                    'channel_thumbnail': row.get('channel_thumbnail') or '',
                }.items() if value not in (None, '')
            }
            for vid, row in merged_by_id.items()
        },
    }
    write_json(STATS, stats)

    if backfill.get('channels'):
        for channel in backfill['channels']:
            extra = channel_info.get(channel.get('id')) or {}
            if extra.get('thumbnail'):
                channel['thumbnail'] = extra['thumbnail']
            for video in channel.get('videos') or []:
                row = merged_by_id.get(video.get('id'))
                info = video_info.get(video.get('id')) or {}
                src = row or {}
                if src.get('view_count') is not None or info.get('view_count') is not None:
                    video['view_count'] = first(src.get('view_count'), info.get('view_count'))
                if src.get('duration_seconds') or info.get('duration_seconds'):
                    video['duration_seconds'] = first(positive_int(src.get('duration_seconds')), positive_int(info.get('duration_seconds')))
                if (src.get('published_at') or info.get('published_at')) and not video.get('published_at'):
                    video['published_at'] = first(src.get('published_at'), info.get('published_at'))
                if extra.get('thumbnail'):
                    video['channel_thumbnail'] = extra['thumbnail']
                elif src.get('channel_thumbnail'):
                    video['channel_thumbnail'] = src['channel_thumbnail']
        write_json(BACKFILL, backfill)

    have_view = sum(1 for row in merged_by_id.values() if row.get('view_count') is not None)
    have_thumb = sum(1 for row in merged_by_id.values() if row.get('channel_thumbnail'))
    have_pub = sum(1 for row in merged_by_id.values() if row.get('published_at'))
    have_dur = sum(1 for row in merged_by_id.values() if row.get('duration_seconds'))
    print(
        f'enriched {len(merged_by_id)} videos; '
        f'views={have_view} published={have_pub} duration={have_dur} thumbs={have_thumb}; '
        f'videos.list={used_v} channels.list={used_c} units={used_v + used_c}'
    )


if __name__ == '__main__':
    main()
