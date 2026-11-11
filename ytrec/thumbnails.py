"""Probe YouTube image CDN thumbnails without using the Data API.

Older videos often do not have ``maxresdefault.jpg``.  Some CDN nodes answer
that URL with a 120x90 grey JPEG instead of a 404, so the site cannot rely on
an ``onerror`` handler to detect a missing large thumbnail.  This module samples
the public image CDN, records the largest real image, and stamps deployable
records with the result.  CDN failures are intentionally ignored by the refresh
path; the site still has a safe ``hqdefault`` fallback.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

THUMBNAIL_KINDS = ('maxresdefault', 'hqdefault', 'mqdefault')
DEFAULT_CACHE_PATH = 'data/thumbnails.json'
PLACEHOLDER_MAX_WIDTH = 120
READ_LIMIT = 512 * 1024
FEED_NAMES = ('picks', 'trending', 'ai', 'podcast', 'music', 'videos', 'editorial')


def thumbnail_url(video_id, kind='hqdefault'):
    return f'https://i.ytimg.com/vi/{video_id}/{kind}.jpg' if video_id else ''


def jpeg_dimensions(payload):
    """Return ``(width, height)`` from JPEG bytes, or ``None``."""
    if not payload or not payload.startswith(b'\xff\xd8'):
        return None
    offset = 2
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset + 4 <= len(payload):
        if payload[offset] != 0xFF:
            offset += 1
            continue
        marker = payload[offset + 1]
        offset += 2
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(payload):
            return None
        segment_length = int.from_bytes(payload[offset:offset + 2], 'big')
        if segment_length < 2 or offset + segment_length > len(payload):
            return None
        if marker in sof_markers and segment_length >= 7:
            height = int.from_bytes(payload[offset + 3:offset + 5], 'big')
            width = int.from_bytes(payload[offset + 5:offset + 7], 'big')
            return width, height
        offset += segment_length
    return None


def fetch_thumbnail_state(url, *, timeout=4, session=None):
    """Return ``'ok'``, ``'placeholder'``, or ``'missing'`` for one image."""
    client = session or requests
    try:
        response = client.get(url, timeout=timeout, stream=True, headers={'Range': f'bytes=0-{READ_LIMIT - 1}'})
    except requests.RequestException:
        raise
    if response.status_code not in (200, 206):
        return 'missing'
    payload = b''
    for chunk in response.iter_content(16384):
        payload += chunk
        dimensions = jpeg_dimensions(payload)
        if dimensions:
            return 'ok' if dimensions[0] > PLACEHOLDER_MAX_WIDTH else 'placeholder'
        if len(payload) >= READ_LIMIT:
            break
    return 'placeholder' if payload else 'missing'


def probe_thumbnail(video_id, *, timeout=4, session=None):
    """Prefer the largest real CDN image, falling back to ``hqdefault``."""
    if not video_id:
        return None
    for kind in THUMBNAIL_KINDS:
        url = thumbnail_url(video_id, kind)
        if fetch_thumbnail_state(url, timeout=timeout, session=session) == 'ok':
            return {'kind': kind, 'url': url}
    return {'kind': 'hqdefault', 'url': thumbnail_url(video_id, 'hqdefault')}


def _load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def _records(root):
    payloads = {}
    for name in FEED_NAMES + ('catalog', 'hn_pool'):
        path = root / f'{name}.json'
        payload = _load_json(path, None)
        if isinstance(payload, (dict, list)):
            payloads[name] = payload
    records = {}
    for payload in payloads.values():
        videos = payload if isinstance(payload, list) else payload.get('videos', [])
        for video in videos or []:
            if isinstance(video, dict) and video.get('id'):
                records.setdefault(video['id'], []).append(video)
    return payloads, records


def load_cache(path=DEFAULT_CACHE_PATH):
    payload = _load_json(path, {})
    entries = payload.get('entries') if isinstance(payload, dict) else None
    return entries if isinstance(entries, dict) else {}


def backfill_thumbnail_sizes(root='site/src/data', *, cache_path=DEFAULT_CACHE_PATH,
                             max_age_days=30, timeout=4, probe=probe_thumbnail,
                             max_network_failures=5):
    """Probe and persist verified thumbnail URLs in every deployable source.

    ``probe`` may be injected by tests.  A ``None`` or exception result means
    the CDN/network is unavailable; files are kept unchanged after a small
    number of consecutive failures so a refresh never depends on the CDN.
    """
    root = Path(root)
    payloads, records = _records(root)
    if not records:
        return {'checked': 0, 'from_cache': 0, 'updated': 0, 'network_failures': 0}

    cache = load_cache(cache_path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    checked = from_cache = network_failures = 0
    for video_id in records:
        entry = cache.get(video_id)
        checked_at = None
        if isinstance(entry, dict):
            try:
                checked_at = datetime.fromisoformat(str(entry.get('checked_at', '')).replace('Z', '+00:00'))
            except ValueError:
                checked_at = None
        if checked_at and checked_at.tzinfo and checked_at.astimezone(timezone.utc) >= cutoff:
            from_cache += 1
            continue
        try:
            result = probe(video_id, timeout=timeout)
        except Exception:
            network_failures += 1
            if network_failures >= max_network_failures:
                break
            continue
        if not result or not result.get('kind') or not result.get('url'):
            network_failures += 1
            if network_failures >= max_network_failures:
                break
            continue
        network_failures = 0
        cache[video_id] = {
            'kind': result['kind'],
            'url': result['url'],
            'checked_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        }
        checked += 1

    updated = 0
    for video_id, video_records in records.items():
        entry = cache.get(video_id)
        if not isinstance(entry, dict) or not entry.get('url') or not entry.get('kind'):
            continue
        for video in video_records:
            if video.get('thumb') == entry['url'] and video.get('thumb_kind') == entry['kind'] and video.get('thumb_verified') is True:
                continue
            video['thumb'] = entry['url']
            video['thumb_kind'] = entry['kind']
            video['thumb_verified'] = True
            updated += 1

    if updated:
        for name, payload in payloads.items():
            _write_json(root / f'{name}.json', payload)
        _write_json(cache_path, {'entries': cache})
    return {
        'checked': checked,
        'from_cache': from_cache,
        'updated': updated,
        'network_failures': network_failures,
    }
