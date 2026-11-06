import json
import sqlite3
import time
import re
import os
from queue import Queue, Empty
from threading import Event, Thread
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
import requests
import yaml
from .links import extract_ids, plain

UTC = timezone.utc

def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return int((parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).timestamp())

def now():
    return int(datetime.now(UTC).timestamp())

def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript('''
    CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY, kind TEXT, author TEXT, ts INTEGER, raw TEXT);
    CREATE TABLE IF NOT EXISTS windows(term TEXT, kind TEXT, start INTEGER, end INTEGER, PRIMARY KEY(term,kind,start,end));
    CREATE TABLE IF NOT EXISTS mentions(video_id TEXT, item_id TEXT, author TEXT, ts INTEGER, quote TEXT, PRIMARY KEY(video_id,item_id));
    CREATE TABLE IF NOT EXISTS metadata(video_id TEXT PRIMARY KEY, fetched INTEGER, raw TEXT);
    CREATE TABLE IF NOT EXISTS quota(ts INTEGER, units INTEGER);
    CREATE TABLE IF NOT EXISTS selections(video_id TEXT PRIMARY KEY, selected_at INTEGER);
    ''')
    return db

class Client:
    def __init__(self, interval=1.05, db=None):
        self.interval = max(0.0, interval)
        self.last = 0
        self.db = db
        self.session = requests.Session()
        self.request_deadline = 90

    def _request(self, url, params):
        session = self.session
        deadline = time.monotonic() + self.request_deadline
        cancelled = Event()
        result = Queue(maxsize=1)

        def fetch():
            # Chunk checks cannot interrupt a blocked read (or DNS/headers).
            # Keep those operations off the caller thread to bound the wait.
            try:
                with session.get(url, params=params, timeout=(10, 30), stream=True) as response:
                    if response.status_code != 200:
                        value = (response.status_code, None)
                    else:
                        body = bytearray()
                        for chunk in response.iter_content(chunk_size=1):
                            if cancelled.is_set() or time.monotonic() >= deadline:
                                raise requests.Timeout('Request deadline exceeded')
                            body.extend(chunk)
                        value = (response.status_code, json.loads(body))
                result.put((value, None))
            except Exception as error:
                result.put((None, error))

        # A stuck resolver/socket must not hold up process exit. Abandoned
        # attempts own sessions that are never reused; response cleanup runs
        # in the worker when the blocking operation returns.
        Thread(target=fetch, daemon=True).start()
        try:
            value, error = result.get(timeout=max(0, deadline - time.monotonic()))
            if time.monotonic() >= deadline:
                raise Empty
        except Empty:
            cancelled.set()
            raise requests.Timeout('Request deadline exceeded') from None
        if error is not None:
            raise error
        return value

    def get(self, url, params, youtube=False):
        for attempt in range(7):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            if youtube and self.db is not None:
                self.db.execute('INSERT INTO quota VALUES (?,1)', (now(),))
                self.db.commit()
            try:
                status, payload = self._request(url, params)
            except requests.RequestException:
                self.session.close()
                self.session = requests.Session()
                if attempt == 6:
                    raise RuntimeError('API transport failed (request details suppressed)') from None
                time.sleep(2 ** attempt)
                continue
            except ValueError:
                raise RuntimeError('API returned invalid JSON') from None
            if status == 429 or status >= 500:
                time.sleep(2 ** attempt)
                continue
            if status != 200:
                raise RuntimeError(f'API HTTP {status}; request details suppressed')
            return payload
        raise RuntimeError('API retry limit reached')

def crawl(db, config, start, end, client=None):
    client = client or Client(config['crawl']['request_interval_seconds'])
    def window(term, kind, lo, hi):
        if db.execute('SELECT 1 FROM windows WHERE term=? AND kind=? AND start<=? AND end>=?', (term, kind, lo, hi)).fetchone():
            return
        params = dict(query=term, tags=kind, numericFilters=f'created_at_i>={lo},created_at_i<{hi}', hitsPerPage=1000, page=0)
        result = client.get('https://hn.algolia.com/api/v1/search_by_date', params)
        if result['nbHits'] > 1000 or result.get('nbPages', 0) > 1:
            if hi - lo <= 1:
                raise RuntimeError('More than 1000 hits in one second; refusing to mark window complete')
            mid = (lo + hi) // 2
            window(term, kind, lo, mid)
            window(term, kind, mid, hi)
        else:
            hits = result['hits']
            if len(hits) < result['nbHits']:
                raise RuntimeError('Truncated HN response; window remains incomplete')
            with db:
                for hit in hits:
                    db.execute('INSERT OR REPLACE INTO items VALUES (?,?,?,?,?)', (hit['objectID'], kind, hit.get('author'), hit['created_at_i'], json.dumps(hit)))
        with db:
            db.execute('INSERT OR IGNORE INTO windows VALUES (?,?,?,?)', (term, kind, lo, hi))
        print(f'HN {kind} {term} {datetime.fromtimestamp(lo, UTC).date()}..{datetime.fromtimestamp(hi, UTC).date()} complete', flush=True)
    step = int(config['crawl']['window_days'] * 86400)
    if step <= 0 or start >= end:
        raise ValueError('Require positive window size and start < end')
    for lo in range(start, end, step):
        for term in ('youtube.com', 'youtu.be', 'youtube-nocookie.com'):
            for kind in ('story', 'comment'):
                window(term, kind, lo, min(lo + step, end))

def extract(db):
    with db:
        db.execute('DELETE FROM mentions')
        for row in db.execute('SELECT * FROM items'):
            hit = json.loads(row['raw'])
            text = ' '.join(str(hit.get(k) or '') for k in ('url', 'title', 'story_text', 'comment_text'))
            if not row['author'] or row['author'] == '[deleted]':
                continue
            quote = plain(hit.get('comment_text') or hit.get('story_text') or hit.get('title'))[:360]
            for vid in extract_ids(text):
                db.execute('INSERT OR IGNORE INTO mentions VALUES (?,?,?,?,?)', (vid, row['id'], row['author'], row['ts'], quote))

def aggregate(db):
    groups = {}
    for row in db.execute('SELECT * FROM mentions ORDER BY ts,item_id'):
        v = groups.setdefault(row['video_id'], dict(id=row['video_id'], people=set(), months=set(), first=row['ts'], last=row['ts'], quotes=[]))
        v['people'].add(row['author'])
        v['months'].add(datetime.fromtimestamp(row['ts'], UTC).strftime('%Y-%m'))
        v['last'] = row['ts']
        if len(v['quotes']) < 3 and row['author'] not in {q['author'] for q in v['quotes']}:
            v['quotes'].append(dict(author=row['author'], text=row['quote'], url=f"https://news.ycombinator.com/item?id={row['item_id']}"))
    for v in groups.values():
        v['recommenders'] = len(v.pop('people'))
        v['months'] = len(v['months'])
        v['span_days'] = (v['last'] - v['first']) / 86400
    return list(groups.values())

def recommendation_gates(v, c):
    return {'recommenders': v['recommenders'] < c['min_recommenders'], 'months': v['months'] < c['min_months'], 'span': v['span_days'] < c['min_span_days'], 'sources': c['sources']['enabled'] and c['sources']['min_sources'] > 1}

def duration(value):
    match = re.fullmatch(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?', value or '')
    return sum(int(n or 0) * factor for n, factor in zip(match.groups(), (86400,3600,60,1))) if match else 0

# These feeds deliberately use the public YouTube API directly rather than the
# community SQLite cache: their windows are short and the committed JSON is the
# deployable artifact.
YOUTUBE_API = 'https://www.googleapis.com/youtube/v3/'

def iso_now():
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def youtube_key():
    key = os.environ.get('YOUTUBE_' + 'API_KEY')
    if not key:
        raise RuntimeError('Set the provider credential to refresh YouTube feeds')
    return key

def video_record(raw):
    snippet = raw.get('snippet', {})
    stats = raw.get('statistics', {})
    return dict(id=raw['id'], title=snippet.get('title', ''), channel=snippet.get('channelTitle', ''),
                channel_id=snippet.get('channelId', ''), published_at=snippet.get('publishedAt', ''),
                duration_seconds=duration(raw.get('contentDetails', {}).get('duration')),
                view_count=int(stats.get('viewCount', 0)),
                like_count=int(stats['likeCount']) if stats.get('likeCount') is not None else None)

def landscape_video(raw):
    """Return whether a video has player dimensions proving it is landscape."""
    player = raw.get('player', {})
    width, height = player.get('embedWidth'), player.get('embedHeight')
    try:
        return bool(width and height and float(width) > float(height))
    except (TypeError, ValueError):
        return False

def write_feed(name, payload, root='site/src/data'):
    target = Path(root) / f'{name}.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return target

def youtube_videos(client, key, ids):
    found = []
    for offset in range(0, len(ids), 50):
        response = client.get(YOUTUBE_API + 'videos', dict(part='snippet,contentDetails,statistics,player', maxWidth=640, maxHeight=640, id=','.join(ids[offset:offset+50]), key=key), youtube=True)
        found.extend(response.get('items', []))
    return found

def trending_feed(client=None, output='site/src/data'):
    """Fetch recent medium/long popularity pages, keeping landscape videos."""
    key = youtube_key(); client = client or Client(interval=.05, db=None)
    after = (datetime.now(UTC) - timedelta(days=30)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    seen_ids, id_buckets, searches, quota_video_batches = set(), {}, 0, 0
    records = []
    buckets = [{'name': bucket, 'token': None, 'pages': 0, 'done': False}
               for bucket in ('medium', 'long')]

    def fetch_page(bucket):
        nonlocal searches, quota_video_batches
        params = dict(part='id', type='video', videoDuration=bucket['name'], order='viewCount',
                      publishedAfter=after, maxResults=50, key=key)
        if bucket['token']:
            params['pageToken'] = bucket['token']
        response = client.get(YOUTUBE_API + 'search', params, youtube=True)
        searches += 1
        bucket['pages'] += 1
        page_ids = [item['id']['videoId'] for item in response.get('items', [])
                    if item.get('id', {}).get('videoId')]
        new_ids = [video_id for video_id in page_ids if video_id not in seen_ids]
        seen_ids.update(new_ids)
        for video_id in new_ids:
            id_buckets[video_id] = bucket['name']
        if new_ids:
            records.extend(youtube_videos(client, key, new_ids))
            quota_video_batches += (len(new_ids) + 49) // 50
        bucket['token'] = response.get('nextPageToken')
        bucket['done'] = not bucket['token']

    def accepted():
        videos = []
        dropped_short = dropped_vertical = 0
        for item in records:
            if duration(item.get('contentDetails', {}).get('duration')) < 60:
                dropped_short += 1
            elif not landscape_video(item):
                dropped_vertical += 1
            else:
                videos.append(video_record(item))
        videos.sort(key=lambda v: (-v['view_count'], v['id']))
        return videos, dropped_short, dropped_vertical

    # Give both API duration buckets a small, predictable base budget.
    for _ in range(2):
        for bucket in buckets:
            if not bucket['done']:
                fetch_page(bucket)
                videos, dropped_short, dropped_vertical = accepted()
                if len(videos) >= 100:
                    break
        if len(videos) >= 100:
            break

    # If the base budget is short, spend one more search page on the bucket
    # with fewer landscape keepers. This caps search.list at five calls.
    if len(videos) < 100 and searches < 5:
        available = [bucket for bucket in buckets if not bucket['done']]
        if available:
            keepers = {bucket['name']: 0 for bucket in buckets}
            for item in records:
                if duration(item.get('contentDetails', {}).get('duration')) >= 60 and landscape_video(item):
                    keepers[id_buckets.get(item.get('id'), available[0]['name'])] += 1
            bucket = min(available, key=lambda b: (keepers[b['name']], b['name']))
            fetch_page(bucket)
            videos, dropped_short, dropped_vertical = accepted()

    payload = dict(generated_at=iso_now(), window_days=30, exclude_shorts_under_seconds=60,
                   candidates_fetched=len(records), dropped_short=dropped_short,
                   dropped_vertical=dropped_vertical, landscape_only=True,
                   video_duration_buckets=['medium', 'long'], final_count=len(videos[:100]),
                   quota_units_approx=searches * 100 + quota_video_batches, videos=videos[:100])
    write_feed('trending', payload, output)
    print(f"Trending: {len(payload['videos'])} landscape videos from {payload['candidates_fetched']} candidates; dropped {payload['dropped_short']} short and {payload['dropped_vertical']} vertical/unknown; approximate YouTube quota units: {payload['quota_units_approx']}")
    return payload

def _normal(value):
    return re.sub(r'[^a-z0-9]', '', (value or '').lower())

def resolve_ai_channels(seed='config/ai_accounts_seed.yaml', output='config/ai_channels.yaml', client=None, search_cap=40):
    key = youtube_key(); client = client or Client(interval=.05, db=None)
    accounts = yaml.safe_load(Path(seed).read_text()).get('accounts', [])
    channels, searches, cheap = [], 0, 0
    for account in accounts:
        item = None; via = None
        try:
            response = client.get(YOUTUBE_API + 'channels', dict(part='snippet', forHandle=account['x'], key=key), youtube=True); cheap += 1
            item = (response.get('items') or [None])[0]; via = 'forHandle' if item else None
            if not item and searches < search_cap:
                response = client.get(YOUTUBE_API + 'search', dict(part='snippet', type='channel', q=account['name'], maxResults=5, key=key), youtube=True); searches += 1
                options = response.get('items', [])
                # Prefer an exact normalized title, otherwise the first API result.
                item = next((x for x in options if _normal(x.get('snippet', {}).get('channelTitle')) == _normal(account['name'])), options[0] if options else None)
                via = 'search' if item else None
        except RuntimeError as error:
            print(f"AI channel skipped: {account['name']} ({error})")
        if item:
            channel_id = item.get('id', {}).get('channelId') if isinstance(item.get('id'), dict) else item.get('id')
            if channel_id:
                channels.append(dict(name=account['name'], x=account['x'], youtube_channel_id=channel_id,
                                     youtube_title=item.get('snippet', {}).get('title', item.get('snippet', {}).get('channelTitle', account['name'])), resolved_via=via))
    # Deduplicate cases where a company and product resolve to the same channel.
    seen = set(); channels = [c for c in channels if not (c['youtube_channel_id'] in seen or seen.add(c['youtube_channel_id']))]
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(yaml.safe_dump({'channels': channels}, allow_unicode=True, sort_keys=False))
    print(f"AI channels: {len(channels)} resolved; approximate YouTube quota units: {cheap + searches * 100}")
    return channels

def ai_feed(channels_file='config/ai_channels.yaml', client=None, output='site/src/data'):
    key = youtube_key(); client = client or Client(interval=.05, db=None)
    channels = yaml.safe_load(Path(channels_file).read_text()).get('channels', [])
    cutoff = datetime.now(UTC) - timedelta(days=7); ids, units = [], 0
    for channel in channels:
        try:
            response = client.get(YOUTUBE_API + 'channels', dict(part='contentDetails', id=channel['youtube_channel_id'], key=key), youtube=True); units += 1
            items = response.get('items', [])
            uploads = items[0]['contentDetails']['relatedPlaylists']['uploads'] if items else None
            if not uploads: continue
            response = client.get(YOUTUBE_API + 'playlistItems', dict(part='snippet,contentDetails', playlistId=uploads, maxResults=50, key=key), youtube=True); units += 1
            for item in response.get('items', []):
                published = item.get('contentDetails', {}).get('videoPublishedAt') or item.get('snippet', {}).get('publishedAt')
                vid = item.get('contentDetails', {}).get('videoId')
                if vid and published and datetime.fromisoformat(published.replace('Z', '+00:00')) >= cutoff: ids.append(vid)
        except RuntimeError as error:
            print(f"AI channel skipped: {channel['name']} ({error})")
    raws = youtube_videos(client, key, list(dict.fromkeys(ids))); units += (len(set(ids)) + 49) // 50
    videos = [v for v in map(video_record, raws) if v['duration_seconds'] >= 60]
    videos.sort(key=lambda v: (-v['view_count'], v['id']))
    payload = dict(generated_at=iso_now(), window_days=7, exclude_shorts_under_seconds=60,
                   quota_units_approx=units, channels_used=len(channels), videos=videos)
    write_feed('ai', payload, output)
    print(f"AI: {len(videos)} videos from {len(channels)} channels; approximate YouTube quota units: {units}")
    return payload

def metadata_gates(raw, c, at):
    if not raw or raw.get('status', {}).get('privacyStatus') != 'public' or raw.get('status', {}).get('uploadStatus') != 'processed':
        return {'metadata_unavailable': True, 'publish_age': False, 'duration': False}
    try:
        age = at - stamp(raw['snippet']['publishedAt'])
    except (KeyError, ValueError):
        age = -1
    return {'metadata_unavailable': False, 'publish_age': age < c['min_publish_age_days'] * 86400, 'duration': duration(raw.get('contentDetails', {}).get('duration')) < c['min_duration_seconds']}

def enrich(db, config, videos, refresh=False, client=None):
    pending = []
    for v in videos:
        if any(recommendation_gates(v, config['recommendation']).values()):
            continue
        cached = db.execute('SELECT fetched FROM metadata WHERE video_id=?', (v['id'],)).fetchone()
        if refresh or not cached or cached['fetched'] < now() - config['metadata']['cache_days'] * 86400:
            pending.append(v['id'])
    if not pending:
        return
    key = os.environ.get('YOUTUBE_' + 'API_KEY')
    if not key:
        raise RuntimeError('Set the provider credential to enrich eligible candidates')
    client = client or Client(db=db)
    initial = db.execute('SELECT coalesce(sum(units),0) FROM quota').fetchone()[0]
    for offset in range(0, len(pending), 50):
        used = db.execute('SELECT coalesce(sum(units),0) FROM quota').fetchone()[0] - initial
        # Reserve enough budget for the bounded retry loop.
        if used + 7 > config['metadata']['max_units_per_run']:
            raise RuntimeError('Quota budget reached; rerun to resume cached batches')
        batch = pending[offset:offset+50]
        result = client.get('https://www.googleapis.com/youtube/v3/videos', dict(part='snippet,contentDetails,statistics,status', id=','.join(batch), key=key), youtube=True)
        found = {item['id']: item for item in result['items']}
        with db:
            for vid in batch:
                db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?,?)', (vid, now(), json.dumps(found.get(vid))))
        print(f'YouTube cached {len(batch)} IDs; approximate units tracked in SQLite', flush=True)

def report(db, config, videos, output='reports'):
    at = now()
    cached = {r['video_id']: json.loads(r['raw']) for r in db.execute('SELECT * FROM metadata')}
    drops = Counter()
    selected = []
    candidates = 0
    for v in videos:
        gates = recommendation_gates(v, config['recommendation'])
        drops.update(k for k, failed in gates.items() if failed)
        if any(gates.values()):
            continue
        candidates += 1
        gates = metadata_gates(cached.get(v['id']), config['metadata'], at)
        drops.update(k for k, failed in gates.items() if failed)
        if any(gates.values()):
            continue
        raw = cached[v['id']]
        db.execute('INSERT OR IGNORE INTO selections VALUES (?,?)', (v['id'], at))
        selected_at = db.execute('SELECT selected_at FROM selections WHERE video_id=?', (v['id'],)).fetchone()[0]
        selected.append(dict(v, title=raw['snippet']['title'], channel=raw['snippet']['channelTitle'], duration_seconds=duration(raw['contentDetails']['duration']), selected_at=selected_at))
    db.commit()
    what_if = []
    for people in (5,10,20,30,50):
        for months in (6,12,24,36,48):
            for span in (365,):
                eligible = [v for v in videos if v['recommenders'] >= people and v['months'] >= months and v['span_days'] >= span and not (config['recommendation']['sources']['enabled'] and config['recommendation']['sources']['min_sources'] > 1)]
                known = [v for v in eligible if v['id'] in cached]
                what_if.append(dict(recommenders=people, months=months, span_days=span, candidates=len(eligible), cached=len(known), selected_with_cached_metadata=sum(not any(metadata_gates(cached[v['id']], config['metadata'], at).values()) for v in known), unknown_metadata=len(eligible)-len(known)))
    summary = dict(generated_at=at, hn_items=dict(db.execute('SELECT kind,count(*) FROM items GROUP BY kind').fetchall()), distinct_video_ids=len(videos), mentions=db.execute('SELECT count(*) FROM mentions').fetchone()[0], distinct_video_recommender_pairs=db.execute('SELECT count(*) FROM (SELECT DISTINCT video_id,author FROM mentions)').fetchone()[0], recommender_histogram=dict(Counter(v['recommenders'] for v in videos)), recommendation_candidates=candidates, dropped_by_gate={k:drops[k] for k in ('recommenders','months','span','sources','metadata_unavailable','publish_age','duration')}, final_selected=len(selected), quota_units=db.execute('SELECT coalesce(sum(units),0) FROM quota').fetchone()[0], what_if=what_if, criteria=config)
    Path(output).mkdir(parents=True, exist_ok=True)
    Path(output, 'report.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    lines = ['# Pipeline report', '', f'Final selected: {len(selected)} (all configured gates applied).', f'Recommendation candidates: {candidates}', f'HN items: {summary["hn_items"]}', f'Distinct videos: {len(videos)}; mentions: {summary["mentions"]}', f'Recommender histogram: {summary["recommender_histogram"]}', f'Dropped by gate (independent, overlapping): {summary["dropped_by_gate"]}', f'Approximate cumulative quota units: {summary["quota_units"]}', '', 'What-if uses cached metadata only; unknowns are not counted as selected.', '', '| People | Months | Span days | Candidates | Cached selected | Unknown |', '|---|---|---|---|---|---|']
    lines += [f'| {r["recommenders"]} | {r["months"]} | {r["span_days"]} | {r["candidates"]} | {r["selected_with_cached_metadata"]} | {r["unknown_metadata"]} |' for r in what_if]
    Path(output, 'report.md').write_text('\n'.join(lines) + '\n')
    Path('site/src/data').mkdir(parents=True, exist_ok=True)
    Path('site/src/data/videos.json').write_text(json.dumps(dict(videos=selected, summary=summary), ensure_ascii=False))
    print('\n'.join(lines[:10]))
    return summary
