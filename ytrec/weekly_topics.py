"""Incrementally top up the HN community pool from the last few days of HN.

This is intentionally not a rebuild: existing pool records, topic ids, topic
names, and lookup assignments are preserved. New videos pass the same gates as
``hn-backfill`` and are attached to existing topics by curation rules, an
optional small DeepSeek run, or nearest-centroid fallback.
"""
import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import yaml

from .build_topics import (
    _added_last_24h,
    _binary_vector,
    _cluster_centroid,
    _cosine,
    _curation_target,
    _load_editorial,
    retag_topic_lookup,
    write_topic_artifacts,
)
from .core import (
    Client,
    aggregate,
    connect,
    crawl,
    extract,
    iso_now,
    pacific_today,
    youtube_key,
    youtube_videos,
)
from .hn_backfill import _cached_metadata, pool_video_record
from .playability import (
    DEFAULT_CACHE_PATH as PLAYABILITY_CACHE_PATH,
    load_cache as load_playability_cache,
    playability_reason,
    save_cache as save_playability_cache,
)
from .thumbnails import (
    DEFAULT_CACHE_PATH as THUMBNAIL_CACHE_PATH,
    _write_json,
    load_cache as load_thumbnail_cache,
    probe_thumbnail,
)
from .zh import parse_json_response

UTC = timezone.utc
DEFAULT_DB = 'data/weekly_topics.sqlite'
NEAREST_TOPIC_MIN_SIMILARITY = 0.1
LLM_BATCH_SIZE = 8
DEEPSEEK_MODEL = 'deepseek-flash'
# Official deepseek-flash prices, CNY per 1M tokens.
# Peak is weekdays 09:00-12:00 and 14:00-18:00 Asia/Shanghai; otherwise half price.
DEEPSEEK_CNY_PER_MILLION = {
    'input_hit_offpeak': 0.02,
    'input_miss_offpeak': 1.0,
    'output_offpeak': 4.0,
    'input_hit_peak': 0.04,
    'input_miss_peak': 2.0,
    'output_peak': 8.0,
}


def _load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _quota_units_readonly(path='data/quota.json'):
    """Read today's quota without creating or updating ``data/quota.json``."""
    payload = _load_json(path, {})
    if not isinstance(payload, dict) or payload.get('date') != pacific_today():
        return 0
    try:
        return max(0, int(payload.get('units') or 0))
    except (TypeError, ValueError):
        return 0


def _quota_summary(limit, used_before, units_this_run):
    used = used_before + units_this_run
    return (f"YouTube quota: used={used} limit={limit} "
            f"remaining={max(0, int(limit) - used)} "
            f"(Pacific date {pacific_today()}; this run +{units_this_run})")



def _deepseek_is_peak(now_dt=None):
    now_dt = now_dt or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    local = now_dt.astimezone(ZoneInfo('Asia/Shanghai'))
    if local.weekday() >= 5:
        return False
    minutes = local.hour * 60 + local.minute
    return (9 * 60 <= minutes < 12 * 60) or (14 * 60 <= minutes < 18 * 60)


def _estimate_deepseek_cny(usage, now_dt=None):
    """Estimate CNY cost from a DeepSeek usage object; cache-miss if unsplit."""
    peak = _deepseek_is_peak(now_dt)
    suffix = 'peak' if peak else 'offpeak'
    rates = DEEPSEEK_CNY_PER_MILLION
    prompt = int(usage.get('prompt_tokens', 0) or 0)
    completion = int(usage.get('completion_tokens', 0) or 0)
    hit = int(usage.get('prompt_cache_hit_tokens', 0) or 0)
    miss = usage.get('prompt_cache_miss_tokens')
    if miss is None:
        miss = max(0, prompt - hit)
    else:
        miss = int(miss or 0)
    return (
        hit * rates[f'input_hit_{suffix}']
        + miss * rates[f'input_miss_{suffix}']
        + completion * rates[f'output_{suffix}']
    ) / 1_000_000


def _window_aggregates(config, days, db_path, client=None, now_dt=None):
    """Crawl one recent HN window in a dedicated database and aggregate it."""
    now_dt = now_dt or datetime.now(UTC)
    if days <= 0:
        raise ValueError('--days must be positive')
    db = connect(db_path)
    try:
        with db:
            db.execute('DELETE FROM items')
            db.execute('DELETE FROM windows')
            db.execute('DELETE FROM mentions')
        start = int((now_dt - timedelta(days=days)).timestamp())
        end = int(now_dt.timestamp())
        crawl(db, config, start, end, client=client)
        extract(db)
        return aggregate(db)
    finally:
        db.close()


def _new_candidates(aggregates, pool_ids):
    candidates = []
    seen = set()
    for video in aggregates:
        video_id = video.get('id')
        if not video_id or video_id in pool_ids or video_id in seen:
            continue
        seen.add(video_id)
        candidates.append(video)
    candidates.sort(key=lambda video: (-int(video.get('recommenders') or 0),
                                       -float(video.get('span_days') or 0),
                                       -int(video.get('months') or 0),
                                       int(video.get('first') or 0)))
    return candidates


def _metadata_for_candidates(candidates, config, youtube_client=None):
    """Fetch only uncached candidate metadata, after enforcing both quota caps."""
    cache = _cached_metadata(config.get('database', 'data/ytrec.sqlite'))
    raw_by_id = {}
    missing = []
    for video in candidates:
        raw = cache.get(video['id'])
        if raw is None:
            missing.append(video['id'])
        else:
            raw_by_id[video['id']] = raw

    metadata_cfg = config.get('metadata', {})
    daily_limit = int(metadata_cfg.get('daily_quota_limit',
                                       config.get('youtube', {}).get('daily_quota_limit', 8000)))
    per_run_limit = int(metadata_cfg.get('max_units_per_run', 1000))
    batches = (len(missing) + 49) // 50
    used_before = _quota_units_readonly()
    remaining = max(0, daily_limit - used_before)
    if batches > per_run_limit:
        raise RuntimeError(
            f'weekly-topics needs {batches} YouTube videos.list units, above '
            f'metadata.max_units_per_run={per_run_limit}; refusing to write anything'
        )
    if batches > remaining:
        raise RuntimeError(
            f'weekly-topics needs {batches} YouTube videos.list units, but only '
            f'{remaining} remain under the {daily_limit}-unit daily quota; refusing to write anything'
        )

    fetched = {}
    if missing:
        key = youtube_key()
        client = youtube_client or Client(interval=0.05, db=None, quota_limit=daily_limit)
        for raw in youtube_videos(client, key, missing):
            if raw.get('id'):
                fetched[raw['id']] = raw
        raw_by_id.update(fetched)
    return raw_by_id, {
        'batches': batches,
        'missing': len(missing),
        'fetched': len(fetched),
        'cached': len(candidates) - len(missing),
        'daily_limit': daily_limit,
        'used_before': used_before,
        'per_run_limit': per_run_limit,
    }


def _select_pool_videos(candidates, raw_by_id, config):
    classic_cfg = config.get('metadata', {}).get('classic_speech', {})
    drops = Counter()
    selected = []
    for video in candidates:
        record, reason = pool_video_record(video, raw_by_id.get(video['id']), classic_cfg)
        if reason:
            drops[reason] += 1
            continue
        selected.append(record)
    selected.sort(key=lambda video: (-int(video.get('recommenders') or 0),
                                     -float(video.get('span_days') or 0),
                                     -int(video.get('months') or 0),
                                     int(video.get('first') or 0)))
    return selected, drops


def _curation_partition(videos, topic_ids):
    curated = {}
    unmatched = []
    fallback_only = set()
    for video in videos:
        matched, target = _curation_target(video)
        if matched and target is None:
            fallback_only.add(video['id'])
        elif matched and target in topic_ids:
            curated[video['id']] = target
        else:
            unmatched.append(video)
    return curated, unmatched, fallback_only


def _llm_prompt(videos, topics):
    topic_rows = [{'id': topic['id'], 'name_zh': topic.get('name_zh'),
                   'keywords': (topic.get('keywords') or [])[:8]}
                  for topic in topics]
    video_rows = []
    for video in videos:
        quote = ''
        for item in video.get('quotes') or []:
            quote = str(item.get('text') or '')[:240]
            if quote:
                break
        video_rows.append({
            'id': video['id'],
            'title': video.get('title') or '',
            'channel': video.get('channel') or '',
            'context': quote,
        })
    return (
        'Assign each YouTube video to at most one existing topic. '
        'Return strict JSON: {"assignments":{"<video_id>":"<topic_id>"}}. '
        'Use null when no existing topic fits. Never invent a topic id.\n'
        f'Topics: {json.dumps(topic_rows, ensure_ascii=False)}\n'
        f'Videos: {json.dumps(video_rows, ensure_ascii=False)}'
    )


def _empty_llm_stats(cap):
    return {
        'model': DEEPSEEK_MODEL,
        'cap': cap,
        'calls': 0,
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'total_tokens': 0,
        'estimated_cost_cny': 0.0,
        'invalid_topic_ids': 0,
        'invalid_video_ids': 0,
        'skipped': None,
        'errors': [],
    }



def _request_topic_llm(prompt, post):
    """Call deepseek-flash in non-thinking mode; keys stay in the environment."""
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        raise RuntimeError('Set DEEPSEEK_API_KEY to assign topics with DeepSeek')
    payload = {
        'model': DEEPSEEK_MODEL,
        'temperature': 0.2,
        'response_format': {'type': 'json_object'},
        'thinking': {'type': 'disabled'},
        'messages': [{'role': 'user', 'content': prompt}],
    }
    response = post('https://api.deepseek.com/chat/completions', headers={
        'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
    }, json=payload, timeout=90)
    response.raise_for_status()
    body = response.json()
    content = body.get('choices', [{}])[0].get('message', {}).get('content', '')
    usage = body.get('usage') or {}
    return parse_json_response(content), {
        'prompt_tokens': int(usage.get('prompt_tokens', 0) or 0),
        'completion_tokens': int(usage.get('completion_tokens', 0) or 0),
        'total_tokens': int(usage.get('total_tokens', 0) or 0),
        'prompt_cache_hit_tokens': int(usage.get('prompt_cache_hit_tokens', 0) or 0),
        'prompt_cache_miss_tokens': int(usage.get('prompt_cache_miss_tokens', 0) or 0)
            if usage.get('prompt_cache_miss_tokens') is not None else None,
    }


def llm_assignments(videos, topics, cap=30, post=None):
    """Return ``{video_id: topic_id}`` and token/cost stats for unmatched videos."""
    cap = max(0, int(cap))
    stats = _empty_llm_stats(cap)
    if not videos or cap == 0:
        stats['skipped'] = 'empty' if not videos else 'cap'
        return {}, stats
    if not os.environ.get('DEEPSEEK_API_KEY'):
        stats['skipped'] = 'missing_key'
        return {}, stats

    topic_ids = {topic['id'] for topic in topics}
    assignments = {}
    post = post or requests.post
    eligible = videos[:cap * LLM_BATCH_SIZE]
    for offset in range(0, len(eligible), LLM_BATCH_SIZE):
        if stats['calls'] >= cap:
            break
        batch = eligible[offset:offset + LLM_BATCH_SIZE]
        batch_ids = {video['id'] for video in batch}
        stats['calls'] += 1
        try:
            result, usage = _request_topic_llm(_llm_prompt(batch, topics), post)
        except Exception as error:
            stats['errors'].append(type(error).__name__)
            break
        prompt_tokens = int(usage.get('prompt_tokens', 0) or 0)
        completion_tokens = int(usage.get('completion_tokens', 0) or 0)
        total_tokens = int(usage.get('total_tokens', 0) or 0)
        stats['prompt_tokens'] += prompt_tokens
        stats['completion_tokens'] += completion_tokens
        stats['total_tokens'] += total_tokens or prompt_tokens + completion_tokens
        stats['estimated_cost_cny'] += _estimate_deepseek_cny(usage)
        values = result.get('assignments') if isinstance(result, dict) else None
        if values is None and isinstance(result, dict):
            values = result
        if not isinstance(values, dict):
            stats['errors'].append('invalid_json_shape')
            continue
        for video_id, topic_id in values.items():
            if video_id not in batch_ids:
                stats['invalid_video_ids'] += 1
                continue
            if topic_id is None:
                continue
            if topic_id not in topic_ids:
                stats['invalid_topic_ids'] += 1
                continue
            assignments[video_id] = topic_id
    return assignments, stats


def _nearest_topic(video, centroids, topic_ids):
    if not topic_ids:
        return None, 0.0
    if not centroids:
        return sorted(topic_ids)[0], 0.0
    doc = _binary_vector({**video, 'quotes': []})
    fallback_topic = sorted(centroids)[0]
    if not doc:
        return fallback_topic, 0.0
    nearest = max(sorted(centroids), key=lambda topic_id: _cosine(doc, centroids[topic_id]))
    return nearest, _cosine(doc, centroids[nearest])


def apply_topic_assignments(pool, new_videos, topics_payload, lookup, editorial,
                            curated, llm_map, fallback_only, now_dt=None):
    """Append new ids to existing topics and return updated artifacts + diagnostics."""
    topics = topics_payload.get('topics') or []
    topic_by_id = {topic['id']: topic for topic in topics}
    topic_ids = set(topic_by_id)
    pool_by_id = {video['id']: video for video in pool if video.get('id')}
    centroids = {}
    for topic in topics:
        videos = [pool_by_id[video_id] for video_id in topic.get('video_ids', [])
                  if video_id in pool_by_id]
        centroid = _cluster_centroid(videos)
        if centroid:
            centroids[topic['id']] = centroid

    decisions = {}
    append_allowed = {}
    for video in new_videos:
        video_id = video['id']
        if video_id in curated:
            decisions[video_id] = curated[video_id]
            append_allowed[video_id] = True
            continue
        if video_id not in fallback_only and llm_map.get(video_id) in topic_ids:
            decisions[video_id] = llm_map[video_id]
            append_allowed[video_id] = True
            continue
        topic_id, similarity = _nearest_topic(video, centroids, topic_ids)
        if topic_id:
            decisions[video_id] = topic_id
            append_allowed[video_id] = (
                video_id not in fallback_only and similarity >= NEAREST_TOPIC_MIN_SIMILARITY
            )

    updated_lookup = dict(lookup)
    updated_lookup.update(decisions)
    metadata = {video['id']: video for video in pool if video.get('id')}
    metadata.update({video['id']: video for video in new_videos if video.get('id')})
    metadata.update({video['id']: video for video in editorial if video.get('id')})
    updated_lookup, retagged_count = retag_topic_lookup(updated_lookup, metadata)
    retag_dropped = set(decisions) - set(updated_lookup)

    additions = {}
    for video in new_videos:
        video_id = video['id']
        topic_id = decisions.get(video_id)
        if (not topic_id or not append_allowed.get(video_id)
                or updated_lookup.get(video_id) != topic_id):
            continue
        topic = topic_by_id[topic_id]
        if video_id not in topic.setdefault('video_ids', []):
            topic['video_ids'].append(video_id)
        channel_id = video.get('channel_id')
        if channel_id and channel_id not in topic.setdefault('source_channel_ids', []):
            topic['source_channel_ids'].append(channel_id)
        additions.setdefault(topic_id, []).append(video)

    now_dt = now_dt or datetime.now(UTC)
    combined_pool = list(pool) + list(new_videos)
    for topic in topics:
        topic['added_last_24h'] = _added_last_24h(
            topic['id'], editorial, combined_pool, updated_lookup, now=now_dt,
        )
    topics_payload['generated_at'] = (now_dt.astimezone(UTC).replace(microsecond=0)
                                      .isoformat().replace('+00:00', 'Z'))
    topics_payload['count'] = len(topics)
    return topics_payload, updated_lookup, {
        'additions': additions,
        'decisions': decisions,
        'retag_dropped': sorted(retag_dropped),
        'retagged_count': retagged_count,
        'fallback_only': sorted(fallback_only),
        'weak_assignments': sorted(
            video_id for video_id, topic_id in decisions.items()
            if not append_allowed.get(video_id)
        ),
    }


def record_playability(candidates, raw_by_id, cache_path=PLAYABILITY_CACHE_PATH):
    """Cache the gate result already computed from fetched metadata; no refetch."""
    cache = load_playability_cache(cache_path)
    checked_at = iso_now()
    for video in candidates:
        cache[video['id']] = {
            'checked_at': checked_at,
            'reason': playability_reason(raw_by_id.get(video['id'])),
        }
    save_playability_cache(cache, cache_path)
    return len(candidates)


def probe_new_thumbnails(videos, cache_path=THUMBNAIL_CACHE_PATH, probe=None, write=True):
    """Probe only new ids and update their records; placeholders never drop a video."""
    cache = load_thumbnail_cache(cache_path)
    probe = probe or probe_thumbnail
    checked = from_cache = network_failures = 0
    changed = False
    for video in videos:
        video_id = video.get('id')
        if not video_id:
            continue
        entry = cache.get(video_id)
        if not (isinstance(entry, dict) and entry.get('kind') and entry.get('url')):
            try:
                result = probe(video_id)
            except Exception:
                network_failures += 1
                continue
            if not result or not result.get('kind') or not result.get('url'):
                network_failures += 1
                continue
            entry = {
                'kind': result['kind'],
                'url': result['url'],
                'checked_at': iso_now(),
            }
            cache[video_id] = entry
            checked += 1
            changed = True
        else:
            from_cache += 1
        video['thumb'] = entry['url']
        video['thumb_kind'] = entry['kind']
        video['thumb_verified'] = True
    if changed and write:
        _write_json(cache_path, {'entries': cache})
    return {'checked': checked, 'from_cache': from_cache,
            'network_failures': network_failures}


def _per_topic_summary(additions):
    summary = {}
    for topic_id, videos in additions.items():
        summary[topic_id] = {
            'count': len(videos),
            'samples': [video.get('title') or video.get('id') for video in videos[:3]],
        }
    return summary


def _commit_paths():
    return [
        'site/src/data/hn_pool.json',
        'site/src/data/topics.json',
        'site/src/data/topic_lookup.json',
        'site/public/hn_pool.json',
        'site/public/topics.json',
        'site/public/topic_lookup.json',
        'site/public/catalog.json',
        'site/public/search-index.json',
        'site/src/data/catalog.json',
        'config/topics.yaml',
        'data/playability.json',
        'data/thumbnails.json',
    ]


def _commit_and_push(no_commit, no_push):
    if no_commit:
        return {'committed': False, 'pushed': False, 'changed': None,
                'reason': 'no_commit'}
    paths = [path for path in _commit_paths() if Path(path).exists()]
    changed = subprocess.run(
        ['git', 'status', '--porcelain', '--', *paths],
        text=True, stdout=subprocess.PIPE, check=True,
    ).stdout.strip()
    if not changed:
        return {'committed': False, 'pushed': False, 'changed': False,
                'reason': 'no_changes'}
    subprocess.run(['git', 'add', *paths], check=True)
    message = f"data: weekly topics {datetime.now(UTC):%F}"
    subprocess.run(['git', 'commit', '-m', message], check=True)
    pushed = False
    if not no_push:
        subprocess.run(['git', 'push', 'origin', 'HEAD'], check=True)
        pushed = True
    return {'committed': True, 'pushed': pushed, 'changed': True,
            'reason': None}


def run_weekly_topics(config, *, days=7, dry_run=False, write=None, no_commit=False,
                      no_push=False, llm_cap=30, root='site/src/data',
                      yaml_path='config/topics.yaml', db_path=DEFAULT_DB,
                      algolia_client=None, youtube_client=None, deepseek_post=None,
                      playability_cache_path=PLAYABILITY_CACHE_PATH,
                      thumbnail_cache_path=THUMBNAIL_CACHE_PATH,
                      build=True, now_dt=None):
    """Run the incremental weekly pipeline and return a serializable summary."""
    if write is False:
        dry_run = True
    now_dt = now_dt or datetime.now(UTC)
    root = Path(root)
    pool_path = root / 'hn_pool.json'
    topics_path = root / 'topics.json'
    lookup_path = root / 'topic_lookup.json'
    pool_payload = _load_json(pool_path, None)
    topics_payload = _load_json(topics_path, None)
    lookup = _load_json(lookup_path, None)
    if not isinstance(pool_payload, dict) or not isinstance(pool_payload.get('videos'), list):
        raise RuntimeError(f'Missing or invalid {pool_path}')
    if not isinstance(topics_payload, dict) or not isinstance(topics_payload.get('topics'), list):
        raise RuntimeError(f'Missing or invalid {topics_path}')
    if not isinstance(lookup, dict):
        raise RuntimeError(f'Missing or invalid {lookup_path}')

    pool = pool_payload['videos']
    pool_ids = {video.get('id') for video in pool if video.get('id')}
    working_db = ':memory:' if dry_run else db_path
    aggregates = _window_aggregates(config, days, working_db,
                                    client=algolia_client, now_dt=now_dt)
    candidates = _new_candidates(aggregates, pool_ids)
    raw_by_id, fetch_stats = _metadata_for_candidates(candidates, config, youtube_client)
    new_videos, drops = _select_pool_videos(candidates, raw_by_id, config)
    editorial = _load_editorial(root=str(root))
    topic_ids = {topic['id'] for topic in topics_payload['topics']}
    curated, unmatched, fallback_only = _curation_partition(new_videos, topic_ids)
    llm_map, llm_stats = llm_assignments(unmatched, topics_payload['topics'],
                                         cap=llm_cap, post=deepseek_post)
    topics_payload, lookup, topic_diagnostics = apply_topic_assignments(
        pool, new_videos, topics_payload, lookup, editorial,
        curated, llm_map, fallback_only, now_dt=now_dt,
    )

    thumbnail_stats = {'checked': 0, 'from_cache': 0, 'network_failures': 0}
    if new_videos:
        thumbnail_stats = probe_new_thumbnails(
            new_videos, cache_path=thumbnail_cache_path, write=not dry_run,
        )

    summary = {
        'candidates': len(candidates),
        'new_videos': len(new_videos),
        'dropped_by_gate': dict(drops),
        'fetched_batches': fetch_stats['batches'],
        'fetched_ids': fetch_stats['fetched'],
        'cached_ids': fetch_stats['cached'],
        'quota_line': _quota_summary(fetch_stats['daily_limit'],
                                     fetch_stats['used_before'], fetch_stats['batches']),
        'deepseek': llm_stats,
        'per_topic': _per_topic_summary(topic_diagnostics['additions']),
        'weak_assignments': topic_diagnostics['weak_assignments'],
        'retag_dropped': topic_diagnostics['retag_dropped'],
        'thumbnails': thumbnail_stats,
        'dry_run': bool(dry_run),
        'wrote': False,
        'commit': {'committed': False, 'pushed': False, 'reason': 'dry_run' if dry_run else None},
    }
    if not new_videos:
        summary['commit']['reason'] = 'no_new_videos'
        return summary
    if dry_run:
        return summary

    pool_payload['generated_at'] = iso_now()
    pool_payload['count'] = len(pool) + len(new_videos)
    pool_payload['videos'] = list(pool) + list(new_videos)
    _write_json(pool_path, pool_payload)
    write_topic_artifacts(topics_payload, lookup, output_dir=str(root), yaml_path=yaml_path)
    record_playability(candidates, raw_by_id, cache_path=playability_cache_path)
    summary['wrote'] = True

    if build:
        subprocess.run(['npm', 'run', 'build'], cwd='site', check=True)
        from .crawl_links import crawl_dist
        broken = crawl_dist('site/dist')
        if broken:
            for item in broken[:100]:
                print(item)
            raise RuntimeError(f'{len(broken)} broken internal link(s) after build; refusing to commit')
        summary['link_check'] = '0 broken links'
        summary['commit'] = _commit_and_push(no_commit, no_push)
        print(f"Weekly topics wrote {len(new_videos)} new videos; commit={summary['commit']}")
    else:
        summary['commit'] = {'committed': False, 'pushed': False, 'changed': True,
                             'reason': 'build_skipped'}
    return summary


def format_summary(summary):
    deepseek = summary.get('deepseek') or {}
    lines = [
        (f"Weekly topics: candidates={summary['candidates']} "
         f"new_videos={summary['new_videos']} dry_run={summary['dry_run']}"),
        f"dropped_by_gate={summary['dropped_by_gate'] or {}}",
        (f"videos.list batches={summary['fetched_batches']} "
         f"fetched={summary['fetched_ids']} cached={summary['cached_ids']}"),
        summary['quota_line'],
        (f"DeepSeek: calls={deepseek.get('calls', 0)} "
         f"tokens={deepseek.get('total_tokens', 0)} "
         f"(prompt={deepseek.get('prompt_tokens', 0)}, "
         f"completion={deepseek.get('completion_tokens', 0)}) "
         f"estimated_cost_cny={deepseek.get('estimated_cost_cny', 0.0):.6f} "
         f"invalid_topic_ids={deepseek.get('invalid_topic_ids', 0)}"
         + (f" skipped={deepseek['skipped']}" if deepseek.get('skipped') else '')),
    ]
    if summary['per_topic']:
        lines.append('New videos by topic:')
        for topic_id, row in sorted(summary['per_topic'].items()):
            lines.append(f"- {topic_id}: {row['count']} (samples: {' | '.join(row['samples'])})")
    if summary.get('weak_assignments'):
        lines.append(f"Lookup-only weak assignments: {', '.join(summary['weak_assignments'])}")
    if summary.get('retag_dropped'):
        lines.append(f"Retagged non-classic lookups: {', '.join(summary['retag_dropped'])}")
    if summary['dry_run']:
        lines.append('Dry run: no JSON, cache, build, crawl, or commit changes written.')
    elif not summary['new_videos']:
        lines.append('No new videos passed the gates; nothing changed and nothing was committed.')
    else:
        commit = summary.get('commit') or {}
        if commit.get('committed'):
            lines.append('Committed' + (' and pushed.' if commit.get('pushed') else ' (push skipped).'))
        else:
            lines.append(f"No commit: {commit.get('reason') or 'no changes'}.")
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Top up HN community topics from recent mentions')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-commit', action='store_true')
    parser.add_argument('--no-push', action='store_true')
    parser.add_argument('--llm-cap', type=int, default=30)
    args = parser.parse_args(argv)
    if args.days <= 0:
        parser.error('--days must be positive')
    if args.llm_cap < 0:
        parser.error('--llm-cap must be zero or positive')
    config = yaml.safe_load(Path(args.config).read_text()) or {}

    if args.dry_run:
        summary = run_weekly_topics(
            config, days=args.days, dry_run=True, no_commit=True, no_push=True,
            llm_cap=args.llm_cap,
        )
        print(format_summary(summary))
        return 0

    log = Path('logs') / f"weekly-topics-{datetime.now(UTC):%Y%m%d}.log"
    log.parent.mkdir(exist_ok=True)
    summary = None
    try:
        with log.open('a', encoding='utf8') as handle, redirect_stdout(handle), redirect_stderr(handle):
            print(f'=== weekly-topics {datetime.now(UTC).isoformat()} ===')
            summary = run_weekly_topics(
                config, days=args.days, no_commit=args.no_commit,
                no_push=args.no_push, llm_cap=args.llm_cap,
            )
            print(format_summary(summary))
    except Exception:
        print(f'Weekly topics failed; see {log}', file=sys.stderr)
        raise
    print(format_summary(summary))
    print(f'Weekly topics log: {log}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
