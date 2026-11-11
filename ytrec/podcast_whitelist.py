"""Curated channel-whitelist feeds (podcast + music).

Podcast keeps long-form episodes (>= 25 minutes); music keeps full tracks and
sets between 3 and 120 minutes. Both reuse the same channel-resolution and
fetch pipeline and never call `search.list`.
"""
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET
import os
from collections import Counter

import requests
import yaml

from .core import (
    Client, youtube_key, youtube_videos, video_record, iso_now,
    write_feed_if_not_sharply_smaller,
    language_gate, podcast_display_cap, why_good_or_existing, dedupe_channel_caps,
    _load_existing_feeds, freshness_sort_key, drop_stale_videos,
    load_fresh_feed_records, metadata_cache_days,
    visible_language_blocked, content_type_blocked, is_official_short_promo,
)
from .playability import playability_reason
from .sources import channels_for_topic

MIN_DURATION = 1500
MUSIC_MIN_DURATION = 180
MUSIC_MAX_DURATION = 7200
EDITORIAL_MIN_DURATION = 240
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


def _fetch_channel_rss_entries(channel_id, session=None, timeout=15):
    response = (session or requests).get(
        RSS_URL, params={'channel_id': channel_id}, timeout=timeout,
    )
    if getattr(response, 'status_code', 200) != 200:
        raise RuntimeError(f'RSS HTTP {response.status_code}')
    return parse_channel_rss(response.text)


def fetch_channel_rss_video_ids(channel_id, session=None, timeout=15, *, client=None, key=None):
    """Fetch a channel's public Atom feed, with an optional API fallback.

    The RSS request itself costs zero YouTube API units. When an API client is
    supplied and the feed fails or has no entries, the shared helper falls back
    to the channel's uploads playlist.
    """
    if client is None:
        return _fetch_channel_rss_entries(channel_id, session=session, timeout=timeout)
    entries, _units = fetch_channel_video_ids(
        channel_id,
        rss_fetcher=lambda cid: _fetch_channel_rss_entries(cid, session=session, timeout=timeout),
        client=client,
        key=key,
    )
    return entries


def _playlist_entries(client, key, uploads_playlist_id):
    response = client.get(
        'https://www.googleapis.com/youtube/v3/playlistItems',
        dict(part='snippet,contentDetails', playlistId=uploads_playlist_id, maxResults=50, key=key),
        youtube=True,
    )
    entries = []
    for item in response.get('items') or []:
        snippet = item.get('snippet') or {}
        details = item.get('contentDetails') or {}
        video_id = details.get('videoId') or (snippet.get('resourceId') or {}).get('videoId')
        if not video_id:
            continue
        published_at = details.get('videoPublishedAt') or snippet.get('publishedAt')
        entries.append(dict(id=video_id, published_at=published_at))
    return entries


def _fallback_uploads_entries(client, key, channel_id):
    """Read uploads via playlistItems, deriving ``UU…`` for UC channel IDs."""
    units = 0
    uploads_playlist_id = 'UU' + channel_id[2:] if channel_id.startswith('UC') else None
    if uploads_playlist_id:
        units += 1
        try:
            return _playlist_entries(client, key, uploads_playlist_id), units
        except Exception as error:
            print(f"Uploads playlist lookup failed for channel {channel_id}: {error}")

    units += 1
    try:
        response = client.get(
            'https://www.googleapis.com/youtube/v3/channels',
            dict(part='contentDetails', id=channel_id, key=key),
            youtube=True,
        )
        item = (response.get('items') or [None])[0] or {}
        uploads_playlist_id = ((item.get('contentDetails') or {}).get('relatedPlaylists') or {}).get('uploads')
        if not uploads_playlist_id:
            return [], units
        units += 1
        return _playlist_entries(client, key, uploads_playlist_id), units
    except Exception as error:
        print(f"Uploads playlist resolution failed for channel {channel_id}: {error}")
        return [], units


def fetch_channel_video_ids(channel_id, *, rss_fetcher=None, client=None, key=None, feed_name=None):
    """Return ``(entries, fallback_units)`` using RSS before paid API fallback."""
    rss_fetcher = rss_fetcher or fetch_channel_rss_video_ids
    try:
        entries = normalize_rss_entries(rss_fetcher(channel_id))
        if entries:
            return entries, 0
        reason = 'RSS returned no parseable entries'
    except Exception as error:
        reason = f'RSS failed: {error}'

    if client is None:
        raise RuntimeError(reason)
    key = key or os.environ.get('YOUTUBE_API_KEY')
    label = f'{feed_name.title()} ' if feed_name else ''
    print(f"{label}RSS fallback: channel={channel_id}; reason={reason}")
    return _fallback_uploads_entries(client, key, channel_id)


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


def _curated_feed_from_channels(channels, *, feed_name, minimum, maximum=None, display_cap=False,
                               client=None, output='site/src/data', quota_limit=8000,
                               rss_fetcher=None, config_path=None):
    """Shared fetch/write path for every curated channel feed."""
    key = youtube_key()
    client = client or Client(interval=.05, db=None, quota_limit=quota_limit)
    rss_fetcher = rss_fetcher or fetch_channel_rss_video_ids
    resolve_units = sum(
        1 for channel in channels
        if not channel.get('youtube_channel_id') and (channel.get('handle') or '').strip()
    )
    unresolved = [channel.get('name') for channel in channels if not channel.get('youtube_channel_id')]
    if config_path and resolve_units:
        channels, unresolved = resolve_handles(
            channels, client=client, key=key, path=config_path, write=True,
        )
    else:
        unresolved = [name for name in unresolved if name]
    ids, seen, units = [], set(), resolve_units
    for channel in channels:
        cid = channel.get('youtube_channel_id')
        if not cid:
            continue
        try:
            entries, fallback_units = fetch_channel_video_ids(
                cid, rss_fetcher=rss_fetcher, client=client, key=key, feed_name=feed_name,
            )
        except Exception as error:
            print(f"{feed_name.title()} channel skipped: {channel.get('name', cid)} ({error})")
            continue
        units += fallback_units
        for entry in entries:
            vid = entry.get('id')
            if vid and vid not in seen:
                seen.add(vid)
                ids.append(vid)
    cached = load_fresh_feed_records(feed_name, root=output, cache_days=metadata_cache_days())
    pending = [vid for vid in ids if vid not in cached]
    raws = youtube_videos(client, key, pending)
    units += (len(pending) + 49) // 50 if pending else 0
    found_ids = {raw.get('id') for raw in raws if raw.get('id')}
    dropped_playability = Counter()
    dropped_playability['missing'] += sum(1 for vid in pending if vid not in found_ids)
    fetched_at = iso_now()
    videos = [dict(cached[vid]) for vid in ids if vid in cached]
    for raw in raws:
        reason = playability_reason(raw)
        if reason:
            dropped_playability[reason] += 1
            continue
        record = video_record(raw)
        record['_metadata_fetched_at'] = fetched_at
        videos.append(record)
    dropped_short = dropped_long = dropped_language = 0
    dropped_content_type = dropped_visible_language = dropped_official_short = 0
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
        if visible_language_blocked(record):
            dropped_visible_language += 1
            continue
        blocked, _reason = content_type_blocked(record, feed_name)
        if blocked:
            dropped_content_type += 1
            continue
        if is_official_short_promo(record, feed_name):
            dropped_official_short += 1
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
        video['why_good'] = why_good_or_existing(video, feed_name, rank=rank)
    kept.sort(key=freshness_sort_key)
    out = dict(generated_at=iso_now(), source='curated_whitelist',
               min_duration_seconds=minimum,
               channels_configured=len(channels),
               channels_resolved=sum(1 for c in channels if c.get('youtube_channel_id')),
               unresolved=[name for name in unresolved if name],
               candidates_fetched=len(ids), dropped_short=dropped_short,
               dropped_language=dropped_language, dropped_channel=dropped_channel,
               dropped_stale=dropped_stale,
               dropped_content_type=dropped_content_type,
               dropped_visible_language=dropped_visible_language,
               dropped_official_short=dropped_official_short,
               final_count=len(kept), quota_units_approx=units,
               videos=kept)
    for reason, count in dropped_playability.items():
        out[f'dropped_{reason}'] = count
    if maximum is not None:
        out['max_duration_seconds'] = maximum
        out['dropped_long'] = dropped_long
    if display_cap:
        out['dropped_podcast_display_cap'] = dropped_display
    out = write_feed_if_not_sharply_smaller(feed_name, out, output)
    label = feed_name.title()
    print(f"{label} (curated): {len(out.get('videos', []))} videos from {out.get('channels_resolved', 0)} channels; unresolved={out.get('unresolved', [])}")
    return out


def curated_channel_feed(config_path, client=None, output='site/src/data', quota_limit=8000,
                         *, feed_name, default_min, default_max=None, display_cap=False,
                         rss_fetcher=None, sources_file=None):
    """Fetch a curated whitelist feed via channel RSS (no `search.list`)."""
    payload, channels, minimum, maximum = _load_channels_config(config_path, default_min, default_max)
    if sources_file is None and Path(config_path).resolve() in (Path(DEFAULT_PODCAST_CONFIG).resolve(), Path(DEFAULT_MUSIC_CONFIG).resolve()):
        sources_file = 'config/sources.yaml'
    if sources_file:
        channels = channels_for_topic(feed_name, channels, path=sources_file)
    return _curated_feed_from_channels(
        channels, feed_name=feed_name, minimum=minimum, maximum=maximum,
        display_cap=display_cap, client=client, output=output,
        quota_limit=quota_limit, rss_fetcher=rss_fetcher, config_path=config_path,
    )


def curated_podcast_feed(config_path=DEFAULT_PODCAST_CONFIG, client=None, output='site/src/data', quota_limit=8000,
                         *, rss_fetcher=None, sources_file=None):
    return curated_channel_feed(
        config_path, client=client, output=output, quota_limit=quota_limit,
        feed_name='podcast', default_min=MIN_DURATION, display_cap=True,
        rss_fetcher=rss_fetcher, sources_file=sources_file,
    )


def curated_editorial_feed(client=None, output='site/src/data', quota_limit=8000,
                           *, rss_fetcher=None, sources_file='config/sources.yaml'):
    """Fetch the active editorial/science channels from sources.yaml."""
    channels = channels_for_topic('editorial', (), path=sources_file)
    return _curated_feed_from_channels(
        channels, feed_name='editorial', minimum=EDITORIAL_MIN_DURATION,
        client=client, output=output, quota_limit=quota_limit,
        rss_fetcher=rss_fetcher,
    )


def curated_music_feed(config_path=DEFAULT_MUSIC_CONFIG, client=None, output='site/src/data', quota_limit=8000,
                       *, rss_fetcher=None, sources_file=None):
    return curated_channel_feed(
        config_path, client=client, output=output, quota_limit=quota_limit,
        feed_name='music', default_min=MUSIC_MIN_DURATION, default_max=MUSIC_MAX_DURATION,
        rss_fetcher=rss_fetcher, sources_file=sources_file,
    )
