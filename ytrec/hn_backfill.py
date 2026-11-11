"""Expand the community pool with high-recommender HN videos using videos.list only.

Reads data/aggregates.json, takes the top IDs by recommenders (then span/months),
reuses cached metadata from data/ytrec.sqlite, and fetches any missing metadata
with YouTube videos.list in batches of 50. Writes site/src/data/hn_pool.json.
"""
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .core import (
    Client,
    classic_speech_exemption,
    language_gate,
    quota_line,
    video_record,
    youtube_videos,
    iso_now,
)
from .playability import playability_reason

SHORTS_MAX_SECONDS = 60
HN_POOL_MIN_SECONDS = 480


def _cached_metadata(path='data/ytrec.sqlite'):
    db_path = Path(path)
    if not db_path.exists():
        return {}
    try:
        uri = db_path.resolve().as_uri() + '?mode=ro'
        db = sqlite3.connect(uri, uri=True)
        db.row_factory = sqlite3.Row
        cached = {}
        for row in db.execute('SELECT video_id, raw FROM metadata'):
            if not row['raw']:
                cached[row['video_id']] = None
                continue
            try:
                cached[row['video_id']] = json.loads(row['raw'])
            except json.JSONDecodeError:
                cached[row['video_id']] = None
        db.close()
        return cached
    except sqlite3.Error:
        return {}


def _is_vertical_short(raw, record):
    """Drop obvious shorts: under a minute, or player-proven vertical video."""
    if (record.get('duration_seconds') or 0) < SHORTS_MAX_SECONDS:
        return True
    player = raw.get('player') or {}
    try:
        width = int(player.get('embedWidth') or 0)
        height = int(player.get('embedHeight') or 0)
    except (TypeError, ValueError):
        width = height = 0
    if width and height and height > width:
        return True
    return False


def pool_video_record(video, raw, classic_cfg):
    """Apply the shipped HN-pool gates and return ``(record, drop_reason)``."""
    if not raw:
        return None, 'missing'
    reason = playability_reason(raw)
    if reason:
        return None, reason
    record = video_record(raw)
    if not language_gate(record):
        return None, 'language'
    if _is_vertical_short(raw, record):
        return None, 'vertical_or_short'
    duration_seconds = int(record.get('duration_seconds') or 0)
    exempt, reasons = classic_speech_exemption(raw, classic_cfg)
    if duration_seconds < HN_POOL_MIN_SECONDS and not exempt:
        return None, 'duration'
    return {
        'id': record['id'],
        'title': record['title'],
        'channel': record['channel'],
        'channel_id': record['channel_id'],
        'published_at': record['published_at'],
        'duration_seconds': duration_seconds,
        'default_audio_language': record.get('default_audio_language'),
        'default_language': record.get('default_language'),
        'view_count': record.get('view_count', 0),
        'like_count': record.get('like_count'),
        'recommenders': video.get('recommenders'),
        'months': video.get('months'),
        'span_days': video.get('span_days'),
        'first': video.get('first'),
        'last': video.get('last'),
        'quotes': video.get('quotes', []),
        'classic_speech': bool(exempt),
        **({'classic_speech_reasons': reasons} if exempt else {}),
    }, None


def backfill_hn_pool(config, limit=1000, client=None, output='site/src/data/hn_pool.json'):
    aggregates = json.loads(Path('data/aggregates.json').read_text())
    ordered = sorted(aggregates, key=lambda video: (-int(video.get('recommenders') or 0),
                                                    -float(video.get('span_days') or 0),
                                                    -int(video.get('months') or 0)))
    candidates = ordered[:limit]
    cache = _cached_metadata(config.get('database', 'data/ytrec.sqlite'))
    classic_cfg = config.get('metadata', {}).get('classic_speech', {})

    missing = []
    raw_by_id = {}
    for video in candidates:
        raw = cache.get(video['id'])
        if raw is None:
            missing.append(video['id'])
        else:
            raw_by_id[video['id']] = raw

    key = os.environ.get('YOUTUBE_' + 'API_KEY')
    fetched = {}
    fetched_count = 0
    if missing and key:
        quota_limit = config.get('metadata', {}).get('daily_quota_limit', 8000)
        client = client or Client(interval=0.05, db=None, quota_limit=quota_limit)
        for raw in youtube_videos(client, key, missing):
            fetched[raw.get('id')] = raw
        fetched_count = len(fetched)
    elif missing and not key:
        print('YOUTUBE_API_KEY missing: shipping the pool from titled cached videos only; '
              f'{len(missing)} IDs left without metadata.', file=sys.stderr)

    drops = Counter()
    selected = []
    for video in candidates:
        raw = raw_by_id.get(video['id']) or fetched.get(video['id'])
        record, reason = pool_video_record(video, raw, classic_cfg)
        if reason:
            drops[reason] += 1
            continue
        selected.append(record)

    selected.sort(key=lambda video: (-int(video['recommenders'] or 0),
                                     -float(video['span_days'] or 0),
                                     -int(video['months'] or 0)))
    payload = {
        'generated_at': iso_now(),
        'kind': 'hn_pool',
        'limit': limit,
        'count': len(selected),
        'videos': selected,
    }
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(f'HN pool: {len(selected)} videos kept (of {len(candidates)} candidates)')
    print(f'dropped_by_gate={dict(drops)} fetched_with_videos_list={fetched_count}')
    return payload


def main(argv=None):
    import argparse
    import yaml
    parser = argparse.ArgumentParser(description='Backfill the HN pool with videos.list only')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--output', default='site/src/data/hn_pool.json')
    args = parser.parse_args(argv)
    config = yaml.safe_load(Path(args.config).read_text())
    backfill_hn_pool(config, limit=args.limit, output=args.output)
    print(quota_line(config.get('metadata', {}).get('daily_quota_limit', 8000)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
