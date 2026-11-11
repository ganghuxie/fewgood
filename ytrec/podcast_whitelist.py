"""Curated channel-whitelist feeds (podcast + music).

Podcast keeps long-form episodes (>= 25 minutes); music keeps full tracks and
sets between 3 and 120 minutes. Both reuse the same channel-resolution and
fetch pipeline and never call `search.list`.
"""
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

import requests
import yaml

from .core import (
    Client, youtube_key, youtube_videos, video_record, iso_now, write_feed,
    language_gate, podcast_display_cap, why_good_for, dedupe_channel_caps,
    _load_existing_feeds, freshness_sort_key, drop_stale_videos,
    load_fresh_feed_records, metadata_cache_days,
)

MIN_DURATION = 1500
MUSIC_MIN_DURATION = 180
MUSIC_MAX_DURATION = 7200
DEFAULT_PODCAST_CONFIG = 'config/podcast_channels.yaml'
DEFAULT_MUSIC_CONFIG = 'config/music_channels.yaml'
RSS_URL = 'https://www.youtube.com/feeds/videos.xml'
ATOM_NS = '{http://www.w3.org/2005/Atom}'
YT_NS = '{http://www.youtube.com/xml/schemas/2015}'


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


def _video_id_from_link(href):
    if not href:
        return None
    parsed = urlparse(href)
    value = (parse_qs(parsed.query).get('v') or [None])[0]
    if value:
        return value
    path = parsed.path or ''
    for prefix in ('/shorts/', '/embed/', '/live/'):
        if path.startswith(prefix):
            return path[len(prefix):].split('/', 1)[0] or None
    return None


def parse_channel_rss(xml_text):
    """Parse a YouTube Atom feed into ``{id, published_at}`` entries."""
    root = ET.fromstring(xml_text)
    entries, seen = [], set()
    for entry in root.findall(f'{ATOM_NS}entry'):
        video_id = (entry.findtext(f'{YT_NS}videoId') or '').strip() or None
        if not video_id:
            entry_id = (entry.findtext(f'{ATOM_NS}id') or '').strip()
            if entry_id.startswith('yt:video:'):
                video_id = entry_id[len('yt:video:'):]
        if not video_id:
            for link in entry.findall(f'{ATOM_NS}link'):
                video_id = _video_id_from_link(link.get('href'))
                if video_id:
                    break
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        published = (entry.findtext(f'{ATOM_NS}published') or entry.findtext(f'{ATOM_NS}updated') or '').strip() or None
        entries.append(dict(id=video_id, published_at=published))
    return entries


def normalize_rss_entries(entries):
    """Accept parser records or simple ID lists from an injected test fetcher."""
    normalized = []
    for entry in entries or []:
        if isinstance(entry, str):
            normalized.append(dict(id=entry, published_at=None))
            continue
        if isinstance(entry, (tuple, list)) and entry:
            normalized.append(dict(id=entry[0], published_at=entry[1] if len(entry) > 1 else None))
            continue
        if isinstance(entry, dict):
            video_id = entry.get('id') or entry.get('videoId') or entry.get('video_id')
            if video_id:
                normalized.append(dict(id=video_id, published_at=entry.get('published_at') or entry.get('published')))
    return normalized


def fetch_channel_rss_video_ids(channel_id, session=None, timeout=15):
    """Fetch a channel's public Atom feed; this costs zero YouTube API units."""
    response = (session or requests).get(
        RSS_URL, params={'channel_id': channel_id}, timeout=timeout,
    )
    if getattr(response, 'status_code', 200) != 200:
        raise RuntimeError(f'RSS HTTP {response.status_code}')
    return parse_channel_rss(response.text)


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
                         *, feed_name, default_min, default_max=None, display_cap=False,
                         rss_fetcher=None):
    """Fetch a curated whitelist feed via channel RSS (no `search.list`)."""
    payload, channels, minimum, maximum = _load_channels_config(config_path, default_min, default_max)
    key = youtube_key()
    client = client or Client(interval=.05, db=None, quota_limit=quota_limit)
    rss_fetcher = rss_fetcher or fetch_channel_rss_video_ids
    resolve_units = sum(
        1 for channel in channels
        if not channel.get('youtube_channel_id') and (channel.get('handle') or '').strip()
    )
    channels, unresolved = resolve_handles(channels, client=client, key=key, path=config_path, write=True)
    ids, seen, units = [], set(), resolve_units
    for channel in channels:
        cid = channel.get('youtube_channel_id')
        if not cid:
            continue
        try:
            entries = rss_fetcher(cid)
        except Exception as error:
            print(f"{feed_name.title()} channel skipped: {channel.get('name', cid)} ({error})")
            continue
        for entry in normalize_rss_entries(entries):
            vid = entry.get('id')
            if vid and vid not in seen:
                seen.add(vid)
                ids.append(vid)
    cached = load_fresh_feed_records(feed_name, root=output, cache_days=metadata_cache_days())
    pending = [vid for vid in ids if vid not in cached]
    raws = youtube_videos(client, key, pending)
    units += (len(pending) + 49) // 50 if pending else 0
    fetched_at = iso_now()
    videos = [dict(cached[vid]) for vid in ids if vid in cached]
    for raw in raws:
        record = video_record(raw)
        record['_metadata_fetched_at'] = fetched_at
        videos.append(record)
    dropped_short = dropped_long = dropped_language = 0
    filtered = []
    for record in videos:
        duration_seconds = int(record.get('duration_seconds') or 0)
        if duration_seconds < minimum:
            dropped_short += 1
            continue
        if maximum is not None and duration_seconds > maximum:
            dropped_long += 1
            continue
        if not language_gate(record):
            dropped_language += 1
            continue
        filtered.append(record)
    videos = filtered
    existing = _load_existing_feeds(feed_name, output)
    kept, dropped_channel = dedupe_channel_caps(videos, existing=existing, feed_name=feed_name)
    kept, dropped_stale = drop_stale_videos(kept)
    dropped_display = 0
    if display_cap:
        kept, dropped_display = podcast_display_cap(kept)
    kept.sort(key=lambda video: (-int(video.get('view_count') or 0), str(video.get('id', ''))))
    for rank, video in enumerate(kept, 1):
        video['why_good'] = why_good_for(video, feed_name, rank=rank)
    kept.sort(key=freshness_sort_key)
    out = dict(generated_at=iso_now(), source='curated_whitelist',
               min_duration_seconds=minimum,
               channels_configured=len(channels),
               channels_resolved=sum(1 for c in channels if c.get('youtube_channel_id')),
               unresolved=[name for name in unresolved if name],
               candidates_fetched=len(ids), dropped_short=dropped_short,
               dropped_language=dropped_language, dropped_channel=dropped_channel,
               dropped_stale=dropped_stale,
               final_count=len(kept), quota_units_approx=units,
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


def curated_podcast_feed(config_path=DEFAULT_PODCAST_CONFIG, client=None, output='site/src/data', quota_limit=8000,
                         *, rss_fetcher=None):
    return curated_channel_feed(
        config_path, client=client, output=output, quota_limit=quota_limit,
        feed_name='podcast', default_min=MIN_DURATION, display_cap=True,
        rss_fetcher=rss_fetcher,
    )


def curated_music_feed(config_path=DEFAULT_MUSIC_CONFIG, client=None, output='site/src/data', quota_limit=8000,
                       *, rss_fetcher=None):
    return curated_channel_feed(
        config_path, client=client, output=output, quota_limit=quota_limit,
        feed_name='music', default_min=MUSIC_MIN_DURATION, default_max=MUSIC_MAX_DURATION,
        rss_fetcher=rss_fetcher,
    )
