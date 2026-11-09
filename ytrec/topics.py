"""Local, fixture-first publisher for reusable Space topics.  It never calls YouTube."""
import argparse
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FIELDS = ('topic_id', 'canonical_name', 'status', 'generated_at', 'videos', 'source')


def normalize(value):
    value = unicodedata.normalize('NFC', str(value or ''))
    value = ' '.join(value.split())
    if not value or len(value) > 80 or re.search(r'[\x00-\x1f\x7f]|https?://|<[^>]*>', value, re.I):
        raise ValueError('invalid topic input')
    return value


def slug(value):
    # Keep language names intentionally distinct; no general synonym inference.
    special = {'C++': 'c-plus-plus', 'C#': 'c-sharp'}
    if value in special:
        return special[value]
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', value)).strip('-') or 'topic'


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as out:
            json.dump(value, out, ensure_ascii=False, indent=2, sort_keys=True)
            out.write('\n')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def read_json(path, fallback):
    try: return json.loads(Path(path).read_text(encoding='utf8'))
    except (OSError, json.JSONDecodeError): return fallback


def now_iso(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def fresh(payload, ttl_days):
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(payload['generated_at'].replace('Z', '+00:00')) < timedelta(days=ttl_days)
    except (KeyError, ValueError, TypeError): return False


def aliases(path):
    raw = read_json(path, {'aliases': {}}).get('aliases', {})
    return {normalize(key): normalize(value) for key, value in raw.items()}


class Lock:
    def __init__(self, path): self.path, self.held = Path(path), False
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY); self.held = True
        except FileExistsError: return False
        return True
    def __exit__(self, *unused):
        if self.held:
            os.close(self.fd)
            try: self.path.unlink()
            except FileNotFoundError: pass


def quota_ok(cfg, quota_path):
    # legacy accounting remains a local guard until it is migrated.
    # Do not call core.load_quota here: its date rollover writes quota.json.
    # Topic dry-runs must be entirely non-mutating.
    legacy = int(read_json(quota_path, {'units': 0}).get('units', 0))
    legacy_ok = legacy <= int(cfg['legacy_daily_limit']) - int(cfg['reserve_legacy_units'])
    return legacy_ok and int(cfg['search_calls_used']) <= int(cfg['search_call_cap']) - int(cfg['reserve_search_calls']) and int(cfg['other_units_used']) <= int(cfg['other_unit_cap']) - int(cfg['reserve_other_units'])


def fixture_videos(fixtures, canonical, retries):
    """Simulated uploads playlist + videos.list results; fixture only, no requests."""
    rows = read_json(Path(fixtures) / 'fake-api' / 'uploads.json', {'topics': {}}).get('topics', {}).get(canonical, [])
    attempts = 0
    while True:
        attempts += 1
        if isinstance(rows, dict) and rows.get('retryable') and attempts <= retries:
            continue
        if isinstance(rows, dict): rows = rows.get('videos', [])
        videos, seen = [], set()
        for row in rows:
            vid = row.get('video_id') or row.get('id')
            if vid and vid not in seen:
                seen.add(vid); videos.append({'video_id': vid, 'title': row.get('title', ''),
                    'channel_title': row.get('channel_title', ''), 'published_at': row.get('published_at', ''),
                    'url': 'https://www.youtube.com/watch?v=' + vid})
        return videos, attempts


def run(queue, fixtures, out_dir, index_path, status_path, cfg, dry_run=False):
    queue_rows = read_json(queue, {'pending_topics': []}).get('pending_topics', [])
    amap = aliases(Path(fixtures) / 'aliases.json' if fixtures else ROOT / 'data/topic-aliases.json')
    published, statuses, writes = [], [], []
    claimed = set()
    for request in queue_rows[:int(cfg['batch_size'])]:
        try: canonical = amap.get(normalize(request.get('topic', '')), normalize(request.get('topic', '')))
        except ValueError: continue
        ident = slug(canonical); destination = Path(out_dir) / f'{ident}.json'
        if ident in claimed:
            continue
        claimed.add(ident)
        old = read_json(destination, {})
        if fresh(old, int(cfg['metadata_ttl_days'])):
            payload = old; status = 'ready'
        elif not quota_ok(cfg, cfg['quota_path']):
            payload = {'topic_id': ident, 'canonical_name': canonical, 'status': 'quota_deferred', 'generated_at': now_iso(), 'videos': []}; status = 'quota_deferred'
        else:
            videos, attempts = fixture_videos(fixtures, canonical, int(cfg['max_retries']))
            status = 'ready' if videos else 'empty'
            payload = {'topic_id': ident, 'canonical_name': canonical, 'status': status, 'generated_at': now_iso(), 'videos': videos, 'source': 'curated_uploads_fixture'}
            # fixture retry accounting is separate from legacy quota state.
            cfg['other_units_used'] += attempts
        payload = {key: payload[key] for key in PUBLIC_FIELDS if key in payload}
        published.append({'topic_id': ident, 'canonical_name': canonical, 'status': status, 'generated_at': payload.get('generated_at', '')})
        statuses.append({'topic_id': ident, 'status': status, 'video_count': len(payload.get('videos', [])), 'generated_at': payload.get('generated_at', '')})
        writes.append((destination, payload))
    index = {'generated_at': now_iso(), 'topics': published}
    status_doc = {'generated_at': now_iso(), 'topics': statuses, 'summary': {'ready': sum(x['status']=='ready' for x in statuses), 'empty': sum(x['status']=='empty' for x in statuses), 'quota_deferred': sum(x['status']=='quota_deferred' for x in statuses)}}
    writes += [(Path(index_path), index), (Path(status_path), status_doc)]
    if dry_run:
        for path, _ in writes: print(f'would write {path}')
    else:
        for path, payload in writes: atomic_json(path, payload)
    return index, status_doc


def main(argv=None):
    parser = argparse.ArgumentParser(description='Publish local Space topic fixtures without network access')
    parser.add_argument('--dry-run', action='store_true'); parser.add_argument('--fixtures', type=Path, default=ROOT/'tests/fixtures/v2')
    parser.add_argument('--queue', type=Path); parser.add_argument('--lock', type=Path); parser.add_argument('--out-dir', type=Path)
    args = parser.parse_args(argv)
    all_cfg = yaml.safe_load((ROOT/'config.yaml').read_text()) or {}; cfg = dict(all_cfg.get('topics', {}))
    cfg.setdefault('metadata_ttl_days', 30); cfg.setdefault('max_retries', 2); cfg.setdefault('batch_size', 5)
    cfg.setdefault('legacy_daily_limit', 8000); cfg.setdefault('reserve_legacy_units', 3500); cfg.setdefault('search_call_cap', 100); cfg.setdefault('reserve_search_calls', 35); cfg.setdefault('other_unit_cap', 10000); cfg.setdefault('reserve_other_units', 2000); cfg['search_calls_used'] = 0; cfg['other_units_used'] = 0
    cfg['quota_path'] = str(ROOT/'data/quota.json')
    queue = args.queue or args.fixtures/'pending-topics.json'; out_dir = args.out_dir or ROOT/'site/public/topics'
    lock = args.lock or ROOT/cfg.get('lock_path', 'data/topic-refresh.lock')
    with Lock(lock) as acquired:
        if not acquired:
            print('topic-refresh lock held; exiting cleanly'); return 0
        run(queue, args.fixtures, out_dir, ROOT/'site/src/data/topics/index.json', out_dir/'status.json', cfg, args.dry_run)
    return 0

if __name__ == '__main__': main()
