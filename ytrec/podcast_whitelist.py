"""Curated channel-whitelist feeds (podcast + music).

Podcast keeps long-form episodes (>= 25 minutes); music keeps full tracks and
sets between 3 and 120 minutes. Both reuse the same channel-resolution and
fetch pipeline and never call `search.list`.
"""
from pathlib import Path
import yaml

from .core import (
    Client, youtube_key, youtube_videos, video_record, iso_now, write_feed,
    language_gate, podcast_display_cap, why_good_for, dedupe_channel_caps,
    _load_existing_feeds,
)

MIN_DURATION = 1500
MUSIC_MIN_DURATION = 180
MUSIC_MAX_DURATION = 7200
DEFAULT_PODCAST_CONFIG = 'config/podcast_channels.yaml'
DEFAULT_MUSIC_CONFIG = 'config/music_channels.yaml'


def _load_channels_config(path, default_min, default_max=None):
    payload = yaml.safe_load(Path(path).read_text()) or {}
    channels = payload.get('channels') or []
    minimum = int(payload.get('min_duration_seconds') or default_min)
    maximum_value = payload.get('max_duration_seconds')
    maximum = int(maximum_value) if maximum_value is not None else default_max
    return payload, channels, minimum, maximum


def load_podcast_channels(path=DEFAULT_PODCAST_CONFIG):
    payload, channels, minimum, _maximum = _load_channels_config(path, MIN_DURATION)
    return payload, channels, minimum


def load_music_channels(path=DEFAULT_MUSIC_CONFIG):
    payload, channels, minimum, maximum = _load_channels_config(path, MUSIC_MIN_DURATION, MUSIC_MAX_DURATION)
    return payload, channels, minimum, maximum


def duration_in_bounds(duration_seconds, minimum, maximum=None):
    """Return True when a duration falls within the configured feed bounds."""
    value = int(duration_seconds or 0)
    return value >= minimum and (maximum is None or value <= maximum)


def resolve_handles(channels, client=None, key=None, path=DEFAULT_PODCAST_CONFIG, write=True):
    """Fill youtube_channel_id via channels.list forHandle only (1 unit each)."""
    key = key or youtube_key()
    client = client or Client(interval=.05, db=None, quota_limit=8000)
    unresolved = []
    for channel in channels:
        if channel.get('youtube_channel_id'):
            continue
        handle = (channel.get('handle') or '').lstrip('@').strip()
        if not handle:
            unresolved.append(channel.get('name'))
            continue
        try:
            response = client.get(
                'https://www.googleapis.com/youtube/v3/channels',
                dict(part='snippet', forHandle=handle, key=key),
                youtube=True,
            )
        except RuntimeError:
            unresolved.append(channel.get('name'))
            continue
        item = (response.get('items') or [None])[0]
        if not item:
            unresolved.append(channel.get('name'))
            continue
        title = (item.get('snippet') or {}).get('title') or ''
        name = channel.get('name') or ''
        name_cjk = {ch for ch in name if '一' <= ch <= '鿿'}
        title_cjk = {ch for ch in title if '一' <= ch <= '鿿'}
        if name_cjk and title_cjk and len(name_cjk & title_cjk) < 2:
            unresolved.append(channel.get('name'))
            continue
        channel['youtube_channel_id'] = item.get('id')
        channel['youtube_title'] = title
        channel['resolved_via'] = 'forHandle'
    unresolved = [channel.get('name') for channel in channels if not channel.get('youtube_channel_id')]
    if write:
        raw = yaml.safe_load(Path(path).read_text()) or {}
        raw['channels'] = channels
        Path(path).write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False))
    return channels, unresolved


def curated_channel_feed(config_path, client=None, output='site/src/data', quota_limit=8000,
                         *, feed_name, default_min, default_max=None, display_cap=False):
    """Fetch a curated whitelist feed via channel uploads (no `search.list`)."""
    payload, channels, minimum, maximum = _load_channels_config(config_path, default_min, default_max)
    key = youtube_key()
    client = client or Client(interval=.05, db=None, quota_limit=quota_limit)
    channels, unresolved = resolve_handles(channels, client=client, key=key, path=config_path, write=True)
    ids, units = [], 0
    for channel in channels:
        cid = channel.get('youtube_channel_id')
        if not cid:
            continue
        try:
            response = client.get(
                'https://www.googleapis.com/youtube/v3/channels',
                dict(part='contentDetails', id=cid, key=key), youtube=True)
            units += 1
        except RuntimeError:
            continue
        items = response.get('items') or []
        uploads = ((items[0].get('contentDetails') or {}).get('relatedPlaylists') or {}).get('uploads') if items else None
        if not uploads:
            continue
        try:
            response = client.get(
                'https://www.googleapis.com/youtube/v3/playlistItems',
                dict(part='contentDetails', playlistId=uploads, maxResults=50, key=key), youtube=True)
            units += 1
        except RuntimeError:
            continue
        for item in response.get('items') or []:
            vid = (item.get('contentDetails') or {}).get('videoId')
            if vid:
                ids.append(vid)
    unique = list(dict.fromkeys(ids))
    raws = youtube_videos(client, key, unique)
    units += (len(unique) + 49) // 50 if unique else 0
    videos = []
    dropped_short = dropped_long = dropped_language = 0
    for raw in raws:
        record = video_record(raw)
        if record['duration_seconds'] < minimum:
            dropped_short += 1
            continue
        if maximum is not None and record['duration_seconds'] > maximum:
            dropped_long += 1
            continue
        if not language_gate(record):
            dropped_language += 1
            continue
        videos.append(record)
    existing = _load_existing_feeds(feed_name, output)
    kept, dropped_channel = dedupe_channel_caps(videos, existing=existing, feed_name=feed_name)
    dropped_display = 0
    if display_cap:
        kept, dropped_display = podcast_display_cap(kept)
    kept.sort(key=lambda video: (-int(video.get('view_count') or 0), str(video.get('id', ''))))
    for rank, video in enumerate(kept, 1):
        video['why_good'] = why_good_for(video, feed_name, rank=rank)
    out = dict(generated_at=iso_now(), source='curated_whitelist',
               min_duration_seconds=minimum,
               channels_configured=len(channels),
               channels_resolved=sum(1 for c in channels if c.get('youtube_channel_id')),
               unresolved=[name for name in unresolved if name],
               candidates_fetched=len(unique), dropped_short=dropped_short,
               dropped_language=dropped_language, dropped_channel=dropped_channel,
               final_count=len(kept), quota_units_approx=units + len(channels),
               videos=kept)
    if maximum is not None:
        out['max_duration_seconds'] = maximum
        out['dropped_long'] = dropped_long
    if display_cap:
        out['dropped_podcast_display_cap'] = dropped_display
    write_feed(feed_name, out, output)
    label = feed_name.title()
    print(f"{label} (curated): {len(kept)} videos from {out['channels_resolved']} channels; unresolved={out['unresolved']}")
    return out


def curated_podcast_feed(config_path=DEFAULT_PODCAST_CONFIG, client=None, output='site/src/data', quota_limit=8000):
    return curated_channel_feed(
        config_path, client=client, output=output, quota_limit=quota_limit,
        feed_name='podcast', default_min=MIN_DURATION, display_cap=True,
    )


def curated_music_feed(config_path=DEFAULT_MUSIC_CONFIG, client=None, output='site/src/data', quota_limit=8000):
    return curated_channel_feed(
        config_path, client=client, output=output, quota_limit=quota_limit,
        feed_name='music', default_min=MUSIC_MIN_DURATION, default_max=MUSIC_MAX_DURATION,
    )
