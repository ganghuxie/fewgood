"""Shared playability checks for every video the site links in-site.

YouTube can keep a video in feeds while making it unplayable in an embed
(private, not processed, embedding disabled, deleted, or blocked in most
regions).  The pure predicate below is used by the feed writers, the offline
backfill, and tests.  Status lookups use ``videos.list`` (1 unit per 50 ids)
and are cached under ``data/`` so normal refreshes do not re-pay for ids that
were already checked recently.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
REGION_MOST_THRESHOLD = 100
PLAYABILITY_REASONS = (
    'missing',
    'not_public',
    'not_processed',
    'not_embeddable',
    'region_restricted',
)
DEFAULT_CACHE_PATH = 'data/playability.json'
FEED_NAMES = ('picks', 'trending', 'ai', 'podcast', 'music', 'videos', 'editorial')
REPORT_IDS = ('Pb5olIPO62g',)


def _as_bool(value):
    if value is True:
        return True
    if value is False:
        return False
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == 'true':
            return True
        if lowered == 'false':
            return False
    return None


def playability_reason(raw, *, region_threshold=REGION_MOST_THRESHOLD):
    """Return a drop reason for an unplayable ``videos.list`` item, else None.

    Region rule: a video is effectively unavailable when it is blocked in at
    least ``region_threshold`` countries, or when its ``allowed`` allowlist is
    smaller than that threshold (so most regions are blocked).  A video
    blocked in only one or two countries is kept.
    """
    if not raw or not raw.get('id'):
        return 'missing'
    status = raw.get('status')
    if isinstance(status, dict):
        privacy = status.get('privacyStatus')
        if privacy is not None and privacy != 'public':
            return 'not_public'
        upload = status.get('uploadStatus')
        if upload is not None and upload != 'processed':
            return 'not_processed'
        if _as_bool(status.get('embeddable')) is False:
            return 'not_embeddable'
    region = (raw.get('contentDetails') or {}).get('regionRestriction') or {}
    blocked = region.get('blocked')
    if isinstance(blocked, list) and len(blocked) >= region_threshold:
        return 'region_restricted'
    allowed = region.get('allowed')
    if isinstance(allowed, list) and len(allowed) < region_threshold:
        return 'region_restricted'
    return None


def is_playable(raw, *, region_threshold=REGION_MOST_THRESHOLD):
    return playability_reason(raw, region_threshold=region_threshold) is None


def filter_playable(videos, reasons):
    """Drop records whose id has a truthy reason; return ``(kept, Counter)``."""
    kept = []
    dropped = Counter()
    for video in videos or []:
        reason = reasons.get(video.get('id')) if isinstance(video, dict) else None
        if reason:
            dropped[reason] += 1
        else:
            kept.append(video)
    return kept, dropped


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_cache(path=DEFAULT_CACHE_PATH):
    """Load ``{video_id: {checked_at, reason}}``; corrupt/missing cache is empty."""
    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    entries = payload.get('entries') if isinstance(payload, dict) and isinstance(payload.get('entries'), dict) else payload
    if not isinstance(entries, dict):
        return {}
    cache = {}
    for video_id, entry in entries.items():
        if isinstance(entry, dict) and 'reason' in entry:
            cache[str(video_id)] = entry
    return cache


def save_cache(cache, path=DEFAULT_CACHE_PATH):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'entries': cache}, ensure_ascii=False, indent=2) + '\n')


def check_playability(client, key, ids, *, cache_path=DEFAULT_CACHE_PATH,
                      cache_days=30, force=False, quota_limit=8000,
                      return_stats=False):
    """Fetch status for uncached ids in batches of 50 and return reasons.

    A cached result is valid for ``cache_days`` (the same metadata cache
    window used by feeds).  The cache stores both playable (reason=None) and
    rejected ids, so daily refreshes only pay for genuinely new ids.
    """
    from .core import YOUTUBE_API, iso_now

    unique = []
    seen = set()
    for video_id in ids or []:
        if video_id and video_id not in seen:
            seen.add(video_id)
            unique.append(video_id)

    cache = load_cache(cache_path)
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=max(0, int(cache_days)))
    reasons = {}
    pending = []
    for video_id in unique:
        entry = cache.get(video_id)
        checked = _parse_timestamp(entry.get('checked_at')) if isinstance(entry, dict) else None
        if (not force and isinstance(entry, dict) and 'reason' in entry
                and checked is not None and checked >= cutoff):
            reasons[video_id] = entry.get('reason')
        else:
            pending.append(video_id)

    if not pending:
        stats = {'requested': len(unique), 'from_cache': len(unique), 'fetched': 0, 'batches': 0}
        return (reasons, stats) if return_stats else reasons

    fetched = {}
    for offset in range(0, len(pending), 50):
        batch = pending[offset:offset + 50]
        response = client.get(
            YOUTUBE_API + 'videos',
            dict(part='status,contentDetails', id=','.join(batch), key=key),
            youtube=True,
        )
        if not isinstance(response, dict) or 'items' not in response:
            raise RuntimeError('YouTube status response was malformed; keeping existing listings')
        found = {item.get('id'): item for item in (response.get('items') or []) if item.get('id')}
        checked_at = iso_now()
        for video_id in batch:
            reason = playability_reason(found.get(video_id))
            fetched[video_id] = {'checked_at': checked_at, 'reason': reason}
            reasons[video_id] = reason

    if fetched:
        cache.update(fetched)
        save_cache(cache, cache_path)
    stats = {
        'requested': len(unique),
        'from_cache': len(unique) - len(pending),
        'fetched': len(pending),
        'batches': (len(pending) + 49) // 50,
    }
    return (reasons, stats) if return_stats else reasons


def _load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def _collect_listed_ids(feeds, catalog, pool, topics, extra_ids=()):
    ordered = []
    seen = set()

    def add(video_id):
        if video_id and video_id not in seen:
            seen.add(video_id)
            ordered.append(video_id)

    for payload in feeds.values():
        for video in payload.get('videos', []) if isinstance(payload, dict) else []:
            add(video.get('id'))
    for video in catalog if isinstance(catalog, list) else []:
        add(video.get('id'))
    for video in (pool or {}).get('videos', []) if isinstance(pool, dict) else []:
        add(video.get('id'))
    for topic in (topics or {}).get('topics', []) if isinstance(topics, dict) else []:
        for video_id in topic.get('video_ids', []) if isinstance(topic, dict) else []:
            add(video_id)
    for video_id in extra_ids:
        add(video_id)
    return ordered


def backfill_playability(root='site/src/data', *, cache_path=DEFAULT_CACHE_PATH,
                         cache_days=30, force=False, client=None, key=None,
                         quota_limit=8000, rebuild=False, dry_run=False,
                         topics_yaml='config/topics.yaml', extra_ids=()):
    """Remove unplayable ids from every deployable source and derived pool.

    The writes intentionally use the direct feed writer (not the 50% refresh
    guard): this is an explicit playability cleanup.  If the status lookup
    raises, or if every listed id would be removed, nothing is written.
    """
    from .core import Client, iso_now, quota_line, write_feed, youtube_key
    from .offline import rebuild_offline
    from .build_topics import build_topics

    root = Path(root)
    feeds = {}
    for name in FEED_NAMES:
        path = root / f'{name}.json'
        if path.exists():
            payload = _load_json(path, None)
            if isinstance(payload, dict):
                feeds[name] = payload
    catalog = _load_json(root / 'catalog.json', [])
    pool = _load_json(root / 'hn_pool.json', None)
    topics = _load_json(root / 'topics.json', None)
    lookup = _load_json(root / 'topic_lookup.json', {})

    report_ids = tuple(dict.fromkeys((*REPORT_IDS, *extra_ids)))
    listed_ids = _collect_listed_ids(feeds, catalog, pool, topics)
    check_ids = list(listed_ids)
    seen = set(check_ids)
    for video_id in report_ids:
        if video_id not in seen:
            check_ids.append(video_id)
            seen.add(video_id)

    if not check_ids:
        return {
            'listed_ids': 0, 'checked_ids': 0, 'removed_ids': 0,
            'by_reason': {}, 'quota_units_approx': 0,
            'pb5olipo62g': {'listed': False, 'reason': None, 'removed': False},
        }

    key = key or youtube_key()
    client = client or Client(interval=.05, db=None, quota_limit=quota_limit)
    reasons, stats = check_playability(
        client, key, check_ids, cache_path=cache_path, cache_days=cache_days,
        force=force, quota_limit=quota_limit, return_stats=True,
    )

    listed = set(listed_ids)
    removed_ids = {video_id for video_id in listed_ids if reasons.get(video_id)}
    if len(listed) > 1 and len(removed_ids) == len(listed):
        raise RuntimeError('every listed video failed the playability check; keeping existing data')
    removed_by_reason = Counter(reasons[video_id] for video_id in removed_ids)
    pb_reason = reasons.get('Pb5olIPO62g')
    pb_listed = 'Pb5olIPO62g' in listed

    summary = {
        'listed_ids': len(listed_ids),
        'checked_ids': len(check_ids),
        'removed_ids': len(removed_ids),
        'by_reason': dict(removed_by_reason),
        'quota_units_approx': stats['batches'],
        'cached_ids': stats['from_cache'],
        'fetched_ids': stats['fetched'],
        'pb5olipo62g': {
            'listed': pb_listed,
            'reason': pb_reason,
            'removed': bool(pb_listed and pb_reason),
        },
    }
    if dry_run:
        return summary

    for name, payload in feeds.items():
        kept, _dropped = filter_playable(payload.get('videos', []), reasons)
        payload['videos'] = kept
        write_feed(name, payload, root)

    if isinstance(pool, dict):
        kept, _dropped = filter_playable(pool.get('videos', []), reasons)
        pool['videos'] = kept
        pool['count'] = len(kept)
        write_feed('hn_pool', pool, root)

    if not rebuild:
        if isinstance(topics, dict):
            for topic in topics.get('topics', []):
                if isinstance(topic, dict):
                    topic['video_ids'] = [video_id for video_id in topic.get('video_ids', [])
                                          if video_id not in removed_ids]
            _write_json(root / 'topics.json', topics)
        if isinstance(lookup, dict):
            filtered_lookup = {video_id: topic for video_id, topic in lookup.items()
                               if video_id not in removed_ids}
            _write_json(root / 'topic_lookup.json', filtered_lookup)

    if rebuild:
        rebuild_offline(root=str(root))
        if (root / 'hn_pool.json').exists():
            build_topics(pool_path=str(root / 'hn_pool.json'), output_dir=str(root),
                         yaml_path=topics_yaml)

    return summary


def format_summary(summary):
    reasons = ','.join(f'{name}={count}' for name, count in sorted(summary['by_reason'].items())) or 'none'
    pb = summary['pb5olipo62g']
    pb_text = f"not listed ({pb['reason']})" if pb['reason'] else 'not listed'
    if pb['listed']:
        pb_text = f"removed ({pb['reason']})" if pb['removed'] else 'kept'
    return (f"Playability: listed={summary['listed_ids']} checked={summary['checked_ids']} "
            f"removed={summary['removed_ids']} by_reason={reasons} "
            f"cached={summary.get('cached_ids', 0)} fetched={summary.get('fetched_ids', 0)} "
            f"Pb5olIPO62g={pb_text}")


def main(argv=None):
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description='Backfill unplayable videos from deployable data')
    parser.add_argument('--root', default='site/src/data')
    parser.add_argument('--cache-path', default=DEFAULT_CACHE_PATH)
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--no-rebuild', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    config = yaml.safe_load(Path(args.config).read_text()) or {}
    limit = config.get('metadata', {}).get('daily_quota_limit', 8000)
    summary = backfill_playability(
        root=args.root, cache_path=args.cache_path,
        cache_days=config.get('metadata', {}).get('cache_days', 30),
        force=args.force, quota_limit=limit, rebuild=not args.no_rebuild,
        dry_run=args.dry_run,
    )
    print(format_summary(summary))
    from .core import quota_line
    print(quota_line(limit))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
