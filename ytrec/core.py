import json
import sqlite3
import time
import re
import os
from queue import Queue, Empty
from threading import Event, Thread
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import Counter
import requests
import yaml
from .links import extract_ids, plain

UTC = timezone.utc
PACIFIC = ZoneInfo('America/Los_Angeles')

def pacific_today():
    return datetime.now(PACIFIC).date().isoformat()

def load_quota(path='data/quota.json'):
    target = Path(path)
    today = pacific_today()
    try:
        value = json.loads(target.read_text())
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        value = {}
    if value.get('date') != today:
        value = {'date': today, 'units': 0}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value) + '\n')
    else:
        value = {'date': today, 'units': int(value.get('units', 0))}
    return value

def quota_remaining(limit, path='data/quota.json'):
    return max(0, int(limit) - load_quota(path)['units'])

def charge_quota(units, limit, path='data/quota.json'):
    value = load_quota(path)
    used = value['units']; units = int(units); remaining = int(limit) - used
    if used + units > int(limit):
        raise RuntimeError(f'YouTube daily quota would exceed {limit} (used={used}, need={units}, remaining={remaining}); refusing call')
    value['units'] = used + units
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value) + '\n')
    return value

def youtube_cost(url):
    path = str(url).split('?', 1)[0].rstrip('/').lower()
    for endpoint, cost in (('/search', 100), ('/videos', 1), ('/channels', 1), ('/playlistitems', 1), ('/commentthreads', 1)):
        if endpoint in path:
            return cost
    return 1

def quota_line(limit=8000, path='data/quota.json'):
    value = load_quota(path)
    return f"YouTube quota: used={value['units']} limit={limit} remaining={max(0, int(limit) - value['units'])} (Pacific date {value['date']})"

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
    def __init__(self, interval=1.05, db=None, quota_limit=8000, quota_path='data/quota.json'):
        self.interval = max(0.0, interval)
        self.last = 0
        self.db = db
        self.quota_limit = quota_limit
        self.quota_path = quota_path
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
        charged = False
        for attempt in range(7):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            if youtube and not charged:
                charge_quota(youtube_cost(url), self.quota_limit, self.quota_path)
                charged = True
                if self.db is not None:
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
                default_audio_language=snippet.get('defaultAudioLanguage') or None,
                default_language=snippet.get('defaultLanguage') or None,
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


# Language gate -------------------------------------------------------------
# Keep only zh + en. A missing/empty/`und`/`zxx` language field falls through
# to the next signal; any other primary subtag excludes the video. When both
# fields are unavailable, a title written in Hangul (incl. jamo), Devanagari,
# Arabic, Thai, or with Turkish-specific letters is excluded. German umlauts
# and ç alone are intentionally allowed.

_LANGUAGE_SCRIPT_BLOCKS = [
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0xA960, 0xA97F),  # Hangul Jamo Extended-A
    (0xD7B0, 0xD7FF),  # Hangul Jamo Extended-B
    (0xAC00, 0xD7A3),  # Hangul Syllables
    (0x0900, 0x097F),  # Devanagari
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
    (0x0E00, 0x0E7F),  # Thai
]
_LANGUAGE_SCRIPT_RE = re.compile('|'.join(f'[{chr(lo)}-{chr(hi)}]' for lo, hi in _LANGUAGE_SCRIPT_BLOCKS))
_TURKISH_LETTERS = frozenset('ĞğİıŞş')


def _title_uses_foreign_script(title):
    if not title:
        return False
    if _LANGUAGE_SCRIPT_RE.search(title):
        return True
    return any(char in _TURKISH_LETTERS for char in title)


def language_ok(default_audio_language=None, default_language=None, title=''):
    """Return True when a video passes the zh/en language gate."""
    for field in (default_audio_language, default_language):
        if not field:
            continue
        value = str(field).strip()
        if value.lower() in ('und', 'zxx'):
            continue
        primary = value.split('-', 1)[0].lower()
        if primary in ('zh', 'en'):
            return True
        return False
    return not _title_uses_foreign_script(title)


def language_gate(video):
    return language_ok(
        video.get('default_audio_language'),
        video.get('default_language'),
        video.get('title', ''),
    )


# Per-channel dedupe --------------------------------------------------------
# A channel may contribute at most one video per UTC calendar day and at most
# three videos in any rolling 7-day window across the whole site pool.

def _channel_priority(feed_name):
    if feed_name in ('community', 'videos'):
        return 0
    if feed_name == 'ai':
        return 1
    return 2


def _video_view(video):
    try:
        return int(video.get('view_count') or 0)
    except (TypeError, ValueError):
        return 0


def _published_utc(video):
    value = video.get('published_at')
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


# Freshness gate -----------------------------------------------------------
# Editorial feeds that curate "new" content (AI, podcast, music) keep only
# items published within 30 days and rank the last 7 days above 7-30 day
# items. Community classics (e.g. Sugar, 2009) never pass through this gate.

FRESHNESS_MAX_DAYS = 30
FRESHNESS_RECENT_DAYS = 7


def published_at_dt(video):
    """Parse a record's `published_at` as an aware UTC datetime, else None."""
    value = video.get('published_at')
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _freshness_now(now=None):
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    return reference.astimezone(UTC)


def within_freshness_window(video, now=None, max_days=FRESHNESS_MAX_DAYS):
    """Return True when a video is no older than `max_days`; missing dates fail."""
    published = published_at_dt(video)
    if published is None:
        return False
    return (_freshness_now(now) - published).total_seconds() <= max_days * 86400


def freshness_bucket(video, now=None):
    """0 = published in the last 7 days, 1 = 7-30 days, 2 = older or missing."""
    published = published_at_dt(video)
    if published is None:
        return 2
    age_days = (_freshness_now(now) - published).total_seconds() / 86400
    if age_days <= FRESHNESS_RECENT_DAYS:
        return 0
    if age_days <= FRESHNESS_MAX_DAYS:
        return 1
    return 2


def freshness_sort_key(video, now=None):
    """Recency-first ordering, then view count and id tiebreaks."""
    return (freshness_bucket(video, now=now), -_video_view(video), str(video.get('id', '')))


def drop_stale_videos(videos, now=None):
    """Drop records outside the freshness window and return the dropped count."""
    kept = [video for video in videos if within_freshness_window(video, now=now)]
    return kept, len(videos) - len(kept)


class _ChannelBudget:
    def __init__(self):
        self.dates = {}
        self.times = {}

    def _exceeds_window(self, times, timestamp):
        combined = sorted(times + [timestamp])
        left = 0
        for right in range(len(combined)):
            while combined[right] - combined[left] >= 7 * 86400:
                left += 1
            if right - left + 1 > 3:
                return True
        return False

    def admit(self, channel_id, published_at):
        if not channel_id or published_at is None:
            return True
        if published_at.date() in self.dates.get(channel_id, set()):
            return False
        timestamp = published_at.timestamp()
        if self._exceeds_window(self.times.get(channel_id, []), timestamp):
            return False
        self.dates.setdefault(channel_id, set()).add(published_at.date())
        self.times.setdefault(channel_id, []).append(timestamp)
        return True


def dedupe_channel_caps(videos, existing=(), feed_name='trending'):
    """Drop candidate videos that exceed per-channel day/7-day budgets.

    `existing` is an iterable of ``(video, feed_name)`` pairs already kept by
    other feeds; those videos are counted toward the budget but never dropped.
    Returns ``(kept, dropped)`` with `kept` in the original `videos` order.
    """
    budget = _ChannelBudget()
    existing_sorted = sorted(existing, key=lambda pair: (_channel_priority(pair[1]), -_video_view(pair[0]), str(pair[0].get('id', ''))))
    for video, _feed in existing_sorted:
        budget.admit(video.get('channel_id'), _published_utc(video))
    order = sorted(range(len(videos)), key=lambda index: (-_video_view(videos[index]), str(videos[index].get('id', ''))))
    keep = set()
    dropped = 0
    for index in order:
        video = videos[index]
        if budget.admit(video.get('channel_id'), _published_utc(video)):
            keep.add(index)
        else:
            dropped += 1
    return [videos[index] for index in range(len(videos)) if index in keep], dropped


def apply_channel_caps_pool(feed_videos):
    """Apply channel caps across every feed at once (whole-site rebuild)."""
    budget = _ChannelBudget()
    entries = []
    for name, videos in feed_videos.items():
        for index, video in enumerate(videos):
            entries.append((name, index, video))
    entries.sort(key=lambda entry: (_channel_priority(entry[0]), -_video_view(entry[2]), str(entry[2].get('id', ''))))
    kept = {name: set() for name in feed_videos}
    dropped = {name: 0 for name in feed_videos}
    for name, index, video in entries:
        if budget.admit(video.get('channel_id'), _published_utc(video)):
            kept[name].add(index)
        else:
            dropped[name] += 1
    return (
        {name: [video for index, video in enumerate(feed_videos[name]) if index in kept[name]] for name in feed_videos},
        dropped,
    )


def podcast_display_cap(videos, top_n=20, per_channel=2):
    """Keep the visible top-20 podcast list at most `per_channel` per channel."""
    ordered = sorted(videos, key=lambda video: (-_video_view(video), str(video.get('id', ''))))
    kept = []
    dropped = 0
    counts = {}
    for video in ordered:
        channel = video.get('channel_id') or ''
        if len(kept) < top_n and counts.get(channel, 0) >= per_channel:
            dropped += 1
            continue
        kept.append(video)
        counts[channel] = counts.get(channel, 0) + 1
    return kept, dropped


def _load_existing_feeds(exclude, root='site/src/data'):
    existing = []
    for name in ('trending', 'ai', 'podcast', 'music', 'videos'):
        if name == exclude:
            continue
        path = Path(root) / f'{name}.json'
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for video in payload.get('videos', []):
            existing.append((video, name))
    return existing


def _feed_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def metadata_cache_days(path='config.yaml'):
    """Read ``metadata.cache_days`` without making feed refreshes depend on it."""
    try:
        payload = yaml.safe_load(Path(path).read_text()) or {}
        return max(0, int((payload.get('metadata') or {}).get('cache_days', 30)))
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return 30


def load_fresh_feed_records(feed_name, root='site/src/data', cache_days=None, at=None):
    """Return cached video records whose metadata is still within ``cache_days``.

    The feed's ``generated_at`` is the fallback timestamp for records written
    before per-record metadata timestamps were introduced. Records are copied
    and stamped with ``_metadata_fetched_at`` so later refreshes can age them
    independently instead of treating every record as freshly fetched.
    """
    path = Path(root) / f'{feed_name}.json'
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    fallback = _feed_timestamp(payload.get('generated_at'))
    reference = at or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    cutoff = reference.astimezone(UTC) - timedelta(days=metadata_cache_days() if cache_days is None else max(0, int(cache_days)))
    fresh = {}
    for video in payload.get('videos', []):
        video_id = video.get('id')
        if not video_id:
            continue
        fetched = _feed_timestamp(video.get('_metadata_fetched_at') or video.get('metadata_fetched_at') or video.get('fetched_at')) or fallback
        if fetched is None or fetched < cutoff:
            continue
        record = dict(video)
        record['_metadata_fetched_at'] = fetched.isoformat().replace('+00:00', 'Z')
        fresh[video_id] = record
    return fresh


# why_good + picks ----------------------------------------------------------

def why_good_for(video, section='trending', rank=None):
    """Build an honest Chinese reason string (≤40 chars) from real fields."""
    section = section or 'trending'
    if section in ('community', 'videos'):
        recommenders = video.get('recommenders')
        if recommenders is None:
            return None
        recommenders = int(recommenders)
        span = video.get('span_days')
        if isinstance(span, (int, float)) and span >= 365:
            years = max(1, int(round(span / 365.25)))
            return f'{recommenders} 位 HN 用户跨 {years} 年反复推荐'
        months = video.get('months')
        if months:
            return f'{recommenders} 位 HN 用户跨 {int(months)} 个月反复推荐'
        return f'{recommenders} 位 HN 用户反复推荐'
    if section == 'ai':
        channel = str(video.get('channel') or '').strip()
        if not channel:
            return 'AI 前沿精选频道本周新片'
        budget = 40 - len('AI 前沿精选频道 ') - len(' 本周新片')
        if len(channel) > budget:
            channel = channel[:budget].rstrip()
        return f'AI 前沿精选频道 {channel} 本周新片'
    if rank is None:
        return None
    return f'近 30 天同类长视频播放第 {int(rank)}'


# 今日精选 duration + source rules ------------------------------------------
# Every pick must run at least 8 minutes; missing duration counts as 0 and is
# excluded. Official/brand promotional clips are additionally rejected below
# 3 minutes as belt-and-suspenders on top of the 8-minute gate.

PICKS_MIN_DURATION_SECONDS = 480
PICKS_OFFICIAL_MIN_DURATION_SECONDS = 180

_PICKS_OFFICIAL_TITLE_RE = re.compile(
    r'\b(?:official(?:\s+(?:video|trailer|music\s*video|audio|lyric|visualizer|mv))?|trailer|music\s*video|m\/?v)\b',
    re.IGNORECASE,
)
_PICKS_OFFICIAL_CHANNEL_RE = re.compile(r'\bofficial\b', re.IGNORECASE)
_PICKS_OFFICIAL_CJK = ('官方',)


def is_official_brand_clip(video):
    """Detect official/brand promotional clips from title or channel name."""
    title = str(video.get('title') or '')
    channel = str(video.get('channel') or '')
    if any(marker in title for marker in _PICKS_OFFICIAL_CJK) or any(marker in channel for marker in _PICKS_OFFICIAL_CJK):
        return True
    if _PICKS_OFFICIAL_CHANNEL_RE.search(channel):
        return True
    return bool(_PICKS_OFFICIAL_TITLE_RE.search(title))


def build_picks(feeds, generated_at=None, limit=10):
    """Generate the 今日精选 feed (≤10) from community, AI and curated podcast."""
    groups = {}
    for key, source_label in (('community', '社区推荐'), ('ai', 'AI前沿'), ('podcast', '播客')):
        feed = feeds.get(key) or {}
        videos = []
        for video in feed.get('videos', []):
            duration_seconds = int(video.get('duration_seconds') or 0)
            if duration_seconds < PICKS_MIN_DURATION_SECONDS:
                continue
            if duration_seconds < PICKS_OFFICIAL_MIN_DURATION_SECONDS and is_official_brand_clip(video):
                continue
            why = video.get('why_good') or why_good_for(video, key)
            if not why:
                continue
            videos.append(dict(video, why_good=why, source=key))
        if key == 'community':
            videos.sort(key=lambda item: (-int(item.get('recommenders') or 0), -int(item.get('months') or 0)))
        else:
            videos, _dropped = drop_stale_videos(videos)
            videos.sort(key=freshness_sort_key)
        groups[key] = (videos, source_label)
    quotas = {'community': 4, 'ai': 4, 'podcast': 2}
    picked = []
    seen = set()
    used = {key: 0 for key in groups}
    cursor = {key: 0 for key in groups}
    order = ('community', 'ai', 'podcast')
    while len(picked) < limit:
        progressed = False
        for key in order:
            if used[key] >= quotas[key]:
                continue
            videos, _label = groups[key]
            while cursor[key] < len(videos):
                candidate = videos[cursor[key]]
                cursor[key] += 1
                if candidate['id'] in seen:
                    continue
                seen.add(candidate['id'])
                picked.append(dict(candidate, pick_source=groups[key][1]))
                used[key] += 1
                progressed = True
                break
        if not progressed:
            break
    for key in order:
        if len(picked) >= limit:
            break
        videos, _label = groups[key]
        while cursor[key] < len(videos) and len(picked) < limit:
            candidate = videos[cursor[key]]
            cursor[key] += 1
            if candidate['id'] in seen:
                continue
            seen.add(candidate['id'])
            picked.append(dict(candidate, pick_source=groups[key][1]))
    return dict(generated_at=generated_at or iso_now(), kind='picks', limit=limit,
                mix=quotas, videos=picked)

def youtube_videos(client, key, ids):
    found = []
    for offset in range(0, len(ids), 50):
        response = client.get(YOUTUBE_API + 'videos', dict(part='snippet,contentDetails,statistics,player', maxWidth=640, maxHeight=640, id=','.join(ids[offset:offset+50]), key=key), youtube=True)
        found.extend(response.get('items', []))
    return found

def windowed_viewcount_feed(name, client=None, output='site/src/data', *, query=None,
                            category_id=None, landscape_only=True, quota_limit=8000):
    """Fetch five six-day popularity windows shared by editorial feeds."""
    key = youtube_key(); client = client or Client(interval=.05, db=None, quota_limit=quota_limit)
    end = datetime.now(UTC).replace(microsecond=0)
    candidate_ids = set()
    searches = 0
    for window in range(5):
        window_end = end - timedelta(days=window * 6)
        window_start = window_end - timedelta(days=6)
        for bucket in ('medium', 'long'):
            params = dict(part='id', type='video', videoDuration=bucket, order='viewCount',
                          publishedAfter=window_start.isoformat().replace('+00:00', 'Z'),
                          publishedBefore=window_end.isoformat().replace('+00:00', 'Z'),
                          maxResults=50, key=key)
            if query:
                params['q'] = query
            if category_id:
                params['videoCategoryId'] = category_id
            response = client.get(YOUTUBE_API + 'search', params, youtube=True)
            searches += 1
            candidate_ids.update(item['id']['videoId'] for item in response.get('items', [])
                                 if item.get('id', {}).get('videoId'))

    records = youtube_videos(client, key, sorted(candidate_ids))
    quota_video_batches = (len(candidate_ids) + 49) // 50 if candidate_ids else 0

    def accepted():
        videos = []
        dropped_short = dropped_vertical = dropped_language = 0
        for item in records:
            if duration(item.get('contentDetails', {}).get('duration')) < 60:
                dropped_short += 1
            elif landscape_only and not landscape_video(item):
                dropped_vertical += 1
            else:
                record = video_record(item)
                if language_gate(record):
                    videos.append(record)
                else:
                    dropped_language += 1
        videos, dropped_channel = dedupe_channel_caps(videos, _load_existing_feeds(name, output), feed_name=name)
        videos.sort(key=lambda v: (-v['view_count'], v['id']))
        return videos, dropped_short, dropped_vertical, dropped_language, dropped_channel

    videos, dropped_short, dropped_vertical, dropped_language, dropped_channel = accepted()
    dropped_podcast = 0
    if name == 'podcast':
        videos, dropped_podcast = podcast_display_cap(videos)
    final_videos = videos[:100]
    if name in ('trending', 'podcast', 'music'):
        for rank, video in enumerate(final_videos, 1):
            video['why_good'] = why_good_for(video, name, rank=rank)
    published = [video['published_at'] for video in final_videos if video['published_at']]

    payload = dict(generated_at=iso_now(), window_days=30, exclude_shorts_under_seconds=60,
                   window_size_days=6, windows=5,
                   candidates_fetched=len(candidate_ids), dropped_short=dropped_short,
                   dropped_vertical=dropped_vertical, dropped_language=dropped_language,
                   dropped_channel=dropped_channel, landscape_only=landscape_only,
                   video_duration_buckets=['medium', 'long'], final_count=len(final_videos),
                   quota_units_approx=searches * 100 + quota_video_batches,
                   videos=final_videos)
    if dropped_podcast:
        payload['dropped_podcast_display_cap'] = dropped_podcast
    if published:
        payload['publish_date_span'] = {'min': min(published), 'max': max(published)}
    if query:
        payload['query'] = query
    if category_id:
        payload['video_category_id'] = category_id
    write_feed(name, payload, output)
    print(f"{name.title()}: {len(payload['videos'])} videos from {payload['candidates_fetched']} candidates across {payload['windows']} {payload['window_size_days']}-day windows; approximate YouTube quota units: {payload['quota_units_approx']}")
    print(quota_line(quota_limit))
    return payload

def trending_feed(client=None, output='site/src/data', quota_limit=8000):
    """Fetch five six-day medium/long popularity windows, keeping landscape videos."""
    return windowed_viewcount_feed('trending', client, output, landscape_only=True, quota_limit=quota_limit)

def podcast_feed(client=None, output='site/src/data', quota_limit=8000):
    """Fetch popular long-form podcast videos without adding extra searches."""
    return windowed_viewcount_feed('podcast', client, output, query='podcast', landscape_only=True, quota_limit=quota_limit)

def music_feed(client=None, output='site/src/data', quota_limit=8000):
    """Fetch popular music-category videos in the same bounded windows."""
    return windowed_viewcount_feed('music', client, output, category_id='10', landscape_only=True, quota_limit=quota_limit)

def _feed_channel_ids(root='site/src/data'):
    ids = set()
    for name in ('trending', 'ai', 'podcast', 'music', 'videos'):
        path = Path(root) / f'{name}.json'
        if not path.exists():
            continue
        for video in json.loads(path.read_text()).get('videos', []):
            if video.get('channel_id'):
                ids.add(video['channel_id'])
    return sorted(ids)

def channels_feed(client=None, output='site/src/data', quota_limit=8000):
    """Build a small channel catalogue from channels already present in feeds."""
    key = youtube_key(); client = client or Client(interval=.05, db=None, quota_limit=quota_limit)
    channel_ids = _feed_channel_ids(output)
    channels, units = [], 0
    for offset in range(0, len(channel_ids), 50):
        response = client.get(YOUTUBE_API + 'channels', dict(part='snippet,statistics,contentDetails', id=','.join(channel_ids[offset:offset + 50]), key=key), youtube=True)
        units += 1
        for raw in response.get('items', []):
            snippet = raw.get('snippet', {}); uploads = raw.get('contentDetails', {}).get('relatedPlaylists', {}).get('uploads')
            channels.append(dict(id=raw['id'], title=snippet.get('title', ''), thumbnail=snippet.get('thumbnails', {}).get('medium', {}).get('url') or snippet.get('thumbnails', {}).get('default', {}).get('url', ''), subscriber_count=int(raw.get('statistics', {}).get('subscriberCount', 0)), uploads_playlist_id=uploads, videos=[]))
    for channel in channels:
        if not channel['uploads_playlist_id']:
            continue
        response = client.get(YOUTUBE_API + 'playlistItems', dict(part='snippet,contentDetails', playlistId=channel['uploads_playlist_id'], maxResults=50, key=key), youtube=True)
        units += 1
        for item in response.get('items', []):
            snippet, details = item.get('snippet', {}), item.get('contentDetails', {})
            video_id = details.get('videoId') or snippet.get('resourceId', {}).get('videoId')
            if video_id:
                channel['videos'].append(dict(id=video_id, title=snippet.get('title', ''), published_at=details.get('videoPublishedAt') or snippet.get('publishedAt', ''), thumb=snippet.get('thumbnails', {}).get('medium', {}).get('url') or snippet.get('thumbnails', {}).get('default', {}).get('url', '')))
    payload = dict(generated_at=iso_now(), channels=channels, quota_units_approx=units)
    write_feed('channels', payload, output)
    print(f"Channels: {len(channels)} channels; approximate YouTube quota units: {units}")
    print(quota_line(quota_limit))
    return payload

def _normal(value):
    return re.sub(r'[^a-z0-9]', '', (value or '').lower())

def resolve_ai_channels(seed='config/ai_accounts_seed.yaml', output='config/ai_channels.yaml', client=None, search_cap=40, quota_limit=8000):
    key = youtube_key(); client = client or Client(interval=.05, db=None, quota_limit=quota_limit)
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
    print(quota_line(quota_limit))
    return channels

def ai_feed(channels_file='config/ai_channels.yaml', client=None, output='site/src/data', quota_limit=8000,
            *, rss_fetcher=None):
    from .podcast_whitelist import (
        fetch_channel_rss_video_ids, normalize_rss_entries,
    )
    key = youtube_key(); client = client or Client(interval=.05, db=None, quota_limit=quota_limit)
    rss_fetcher = rss_fetcher or fetch_channel_rss_video_ids
    channels = yaml.safe_load(Path(channels_file).read_text()).get('channels', [])
    cutoff = datetime.now(UTC) - timedelta(days=FRESHNESS_MAX_DAYS)
    discovered, units = {}, 0
    for channel in channels:
        channel_id = channel.get('youtube_channel_id')
        if not channel_id:
            continue
        try:
            entries = rss_fetcher(channel_id)
        except Exception as error:
            print(f"AI channel skipped: {channel.get('name', channel_id)} ({error})")
            continue
        for entry in normalize_rss_entries(entries):
            vid = entry.get('id')
            published = _feed_timestamp(entry.get('published_at'))
            if vid and (published is None or published >= cutoff):
                discovered[vid] = entry.get('published_at')
    ids = list(discovered)
    cached = load_fresh_feed_records('ai', root=output, cache_days=metadata_cache_days())
    pending = [vid for vid in ids if vid not in cached]
    raws = youtube_videos(client, key, pending); units += (len(pending) + 49) // 50 if pending else 0
    fetched_at = iso_now()
    videos = [dict(cached[vid]) for vid in ids if vid in cached]
    for raw in raws:
        record = video_record(raw)
        record['_metadata_fetched_at'] = fetched_at
        videos.append(record)
    videos = [v for v in videos if int(v.get('duration_seconds') or 0) >= 60]
    dropped_language = sum(1 for v in videos if not language_gate(v))
    videos = [v for v in videos if language_gate(v)]
    videos, dropped_stale = drop_stale_videos(videos)
    videos, dropped_channel = dedupe_channel_caps(videos, _load_existing_feeds('ai', output), feed_name='ai')
    for video in videos:
        video['why_good'] = why_good_for(video, 'ai')
    videos.sort(key=freshness_sort_key)
    payload = dict(generated_at=iso_now(), window_days=FRESHNESS_MAX_DAYS, exclude_shorts_under_seconds=60,
                   quota_units_approx=units, channels_used=len(channels), dropped_language=dropped_language,
                   dropped_channel=dropped_channel, dropped_stale=dropped_stale, videos=videos)
    write_feed('ai', payload, output)
    print(f"AI: {len(videos)} videos from {len(channels)} channels; approximate YouTube quota units: {units}")
    print(quota_line(quota_limit))
    return payload

def metadata_gates(raw, c, at):
    if not raw or raw.get('status', {}).get('privacyStatus') != 'public' or raw.get('status', {}).get('uploadStatus') != 'processed':
        return {'metadata_unavailable': True, 'publish_age': False, 'duration': False}
    try:
        age = at - stamp(raw['snippet']['publishedAt'])
    except (KeyError, ValueError):
        age = -1
    return {'metadata_unavailable': False, 'publish_age': age < c['min_publish_age_days'] * 86400, 'duration': duration(raw.get('contentDetails', {}).get('duration')) < c['min_duration_seconds']}

def _contains_phrase(value, phrase):
    """Case-insensitive phrase matching with word-ish edges for names."""
    return bool(re.search(r'(?<![\w])' + re.escape(phrase) + r'(?![\w])', value or '', re.IGNORECASE))

def classic_speech_exemption(raw, classic_cfg):
    """Return exemption eligibility and the rule codes that make it eligible."""
    if not classic_cfg or not classic_cfg.get('enabled'):
        return False, []
    snippet = raw.get('snippet', {})
    title, channel = snippet.get('title', ''), snippet.get('channelTitle', '')
    title_lower, channel_lower = title.lower(), channel.lower()
    speakers = classic_cfg.get('famous_speakers', [])
    channels = classic_cfg.get('univ_museum_channels', [])
    keywords = classic_cfg.get('speech_title_keywords', [])
    famous = any(_contains_phrase(f'{title} {channel}', speaker) for speaker in speakers)
    univ_museum = any(str(name).lower() in channel_lower for name in channels)
    speech_title = any(str(keyword).lower() in title_lower for keyword in keywords)
    long_enough = duration(raw.get('contentDetails', {}).get('duration')) >= classic_cfg.get('min_duration_seconds', 1200)
    classic_demo = ('mother of all demos' in title_lower or 'engelbart' in title_lower) and famous
    reasons = []
    if speech_title and (famous or univ_museum):
        reasons.append('A_speech')
    if univ_museum and long_enough:
        reasons.append('B_channel_duration')
    if famous and long_enough:
        reasons.append('C_speaker_duration')
    if classic_demo:
        reasons.append('D_classic_demo')
    return bool(reasons), reasons

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
    client = client or Client(db=db, quota_limit=config.get('metadata', {}).get('daily_quota_limit', 8000))
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
        snippet = raw.get('snippet', {})
        if not language_ok(snippet.get('defaultAudioLanguage'), snippet.get('defaultLanguage'), snippet.get('title', '')):
            drops['language'] += 1
            continue
        max_upload_age_years = config['metadata'].get('max_upload_age_years', 0)
        try:
            upload_age = at - stamp(raw['snippet']['publishedAt'])
        except (KeyError, ValueError):
            upload_age = 0
        over_upload_age = max_upload_age_years and upload_age >= max_upload_age_years * 365.25 * 86400
        exempt, classic_reasons = classic_speech_exemption(raw, config['metadata'].get('classic_speech', {}))
        if over_upload_age and not exempt:
            drops['max_upload_age'] += 1
            continue
        db.execute('INSERT OR IGNORE INTO selections VALUES (?,?)', (v['id'], at))
        selected_at = db.execute('SELECT selected_at FROM selections WHERE video_id=?', (v['id'],)).fetchone()[0]
        selected.append(dict(v, title=snippet.get('title', ''), channel=snippet.get('channelTitle', ''), channel_id=snippet.get('channelId', ''), published_at=snippet.get('publishedAt', ''), default_audio_language=snippet.get('defaultAudioLanguage') or None, default_language=snippet.get('defaultLanguage') or None, duration_seconds=duration(raw['contentDetails']['duration']), selected_at=selected_at, classic_speech=bool(over_upload_age and exempt), **({'classic_speech_reasons': classic_reasons} if over_upload_age and exempt else {})))
    for record in selected:
        record['why_good'] = why_good_for(record, 'community')
    db.commit()
    what_if = []
    for people in (5,10,20,30,50):
        for months in (6,12,24,36,48):
            for span in (365,):
                eligible = [v for v in videos if v['recommenders'] >= people and v['months'] >= months and v['span_days'] >= span and not (config['recommendation']['sources']['enabled'] and config['recommendation']['sources']['min_sources'] > 1)]
                known = [v for v in eligible if v['id'] in cached]
                what_if.append(dict(recommenders=people, months=months, span_days=span, candidates=len(eligible), cached=len(known), selected_with_cached_metadata=sum(not any(metadata_gates(cached[v['id']], config['metadata'], at).values()) for v in known), unknown_metadata=len(eligible)-len(known)))
    summary = dict(generated_at=at, hn_items=dict(db.execute('SELECT kind,count(*) FROM items GROUP BY kind').fetchall()), distinct_video_ids=len(videos), mentions=db.execute('SELECT count(*) FROM mentions').fetchone()[0], distinct_video_recommender_pairs=db.execute('SELECT count(*) FROM (SELECT DISTINCT video_id,author FROM mentions)').fetchone()[0], recommender_histogram=dict(Counter(v['recommenders'] for v in videos)), recommendation_candidates=candidates, dropped_by_gate={k:drops[k] for k in ('recommenders','months','span','sources','metadata_unavailable','publish_age','duration','max_upload_age','language')}, final_selected=len(selected), quota_units=db.execute('SELECT coalesce(sum(units),0) FROM quota').fetchone()[0], what_if=what_if, criteria=config)
    Path(output).mkdir(parents=True, exist_ok=True)
    Path(output, 'report.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    lines = ['# Pipeline report', '', f'Final selected: {len(selected)} (all configured gates applied).', f'Recommendation candidates: {candidates}', f'HN items: {summary["hn_items"]}', f'Distinct videos: {len(videos)}; mentions: {summary["mentions"]}', f'Recommender histogram: {summary["recommender_histogram"]}', f'Dropped by gate (independent, overlapping): {summary["dropped_by_gate"]}', f'Approximate cumulative quota units: {summary["quota_units"]}', '', 'What-if uses cached metadata only; unknowns are not counted as selected.', '', '| People | Months | Span days | Candidates | Cached selected | Unknown |', '|---|---|---|---|---|---|']
    lines += [f'| {r["recommenders"]} | {r["months"]} | {r["span_days"]} | {r["candidates"]} | {r["selected_with_cached_metadata"]} | {r["unknown_metadata"]} |' for r in what_if]
    Path(output, 'report.md').write_text('\n'.join(lines) + '\n')
    Path('site/src/data').mkdir(parents=True, exist_ok=True)
    Path('site/src/data/videos.json').write_text(json.dumps(dict(videos=selected, summary=summary), ensure_ascii=False))
    print('\n'.join(lines[:10]))
    return summary
