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
from .playability import playability_reason
from .scoring import (
    channel_median_views,
    has_chapters_from_description,
    load_source_rows,
    score_video,
)
from .sources import channels_for_topic

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
    content = raw.get('contentDetails', {}) or {}
    caption = content.get('caption')
    return dict(id=raw['id'], title=snippet.get('title', ''), channel=snippet.get('channelTitle', ''),
                channel_id=snippet.get('channelId', ''), published_at=snippet.get('publishedAt', ''),
                default_audio_language=snippet.get('defaultAudioLanguage') or None,
                default_language=snippet.get('defaultLanguage') or None,
                duration_seconds=duration(content.get('duration')),
                view_count=int(stats.get('viewCount', 0)),
                like_count=int(stats['likeCount']) if stats.get('likeCount') is not None else None,
                comment_count=int(stats['commentCount']) if stats.get('commentCount') is not None else None,
                has_captions=(str(caption).strip().lower() == 'true') if caption is not None else None,
                has_chapters=has_chapters_from_description(snippet.get('description', '')))

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


def _count_field(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def write_feed_if_not_sharply_smaller(name, payload, root='site/src/data', *, pre_cap_count=None):
    """Write a feed unless the refresh would sharply shrink an existing one.

    An empty refresh, or one below 50% of the previously written candidate
    count, is treated as a discovery outage. `pre_cap_count` (or a payload's
    `pre_cap_count` field) lets an intentional display cap shrink the written
    feed without looking like a failed refresh; the guard compares the
    pre-cap candidates instead of the capped output. The previous payload is
    returned without touching the file when the guard trips.
    """
    target = Path(root) / f'{name}.json'
    previous = None
    previous_videos = []
    try:
        previous = json.loads(target.read_text())
        if isinstance(previous, dict) and isinstance(previous.get('videos'), list):
            previous_videos = previous['videos']
    except (OSError, json.JSONDecodeError, TypeError):
        pass

    new_videos = payload.get('videos') if isinstance(payload, dict) else None
    new_count = len(new_videos) if isinstance(new_videos, list) else 0
    prev_count = len(previous_videos)
    declared_pre_cap = pre_cap_count
    if declared_pre_cap is None and isinstance(payload, dict):
        declared_pre_cap = payload.get('pre_cap_count')
    new_candidate_count = max(new_count, _count_field(declared_pre_cap))
    prev_candidate_count = prev_count
    if isinstance(previous, dict):
        prev_candidate_count = max(prev_count, _count_field(previous.get('pre_cap_count')))
    if prev_count > 0:
        if new_count == 0:
            reason = 'refresh produced no videos'
        elif new_candidate_count < 0.5 * prev_candidate_count:
            reason = 'below 50% of previous feed'
        else:
            reason = None
        if reason:
            print(
                f"WARNING: kept previous {name} feed: new_count={new_count}, "
                f"prev_count={prev_count}, reason={reason}"
            )
            return previous

    write_feed(name, payload, root)
    return payload


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

# Visible-title language net ------------------------------------------------
# YouTube sometimes tags subtitled foreign dramas/MVs as English.  A language
# code alone therefore is not enough.  Count script characters so a single
# borrowed glyph in an English/Chinese title does not trip the gate, while a
# title actually written in one of these scripts does.
_VISIBLE_LANGUAGE_SCRIPT_BLOCKS = _LANGUAGE_SCRIPT_BLOCKS + [
    (0x0980, 0x09FF),  # Bengali
    (0x1000, 0x109F),  # Myanmar
    (0xA9E0, 0xA9FF),  # Myanmar Extended-A
    (0xAA60, 0xAA7F),  # Myanmar Extended-B
]
_VISIBLE_LANGUAGE_SCRIPT_RE = re.compile(
    '|'.join(f'[{chr(lo)}-{chr(hi)}]' for lo, hi in _VISIBLE_LANGUAGE_SCRIPT_BLOCKS)
)
_VIETNAMESE_LETTERS = frozenset('ăâêôơưđĂÂÊÔƠƯĐ')
_VIETNAMESE_MIN_CHARS = 2
_VISIBLE_SCRIPT_MIN_CHARS = 3
_PORTUGUESE_ACCENT_RE = re.compile(r'[ãõÃÕ]')
_PORTUGUESE_FUNCTION_RE = re.compile(
    r'\b(?:não|nao|uma|dos|das|para|com|você|voce|porque|sobre|isso|'
    r'aqui|mais|muito|muita|pelo|pela|pelos|pelas|nós|nos|é|são|sao|'
    r'está|esta|estão|estao|tem|têm|foi|vai|seu|sua|seus|suas)\b',
    re.IGNORECASE,
)


def _title_uses_foreign_script(title):
    if not title:
        return False
    if _LANGUAGE_SCRIPT_RE.search(title):
        return True
    return any(char in _TURKISH_LETTERS for char in title)


def _title_uses_visible_foreign_language(title):
    """Return True when a title is substantially written in a blocked script.

    Unlike the legacy language gate this is a conservative visible-title net:
    three script characters (or two Vietnamese-specific letters) are required,
    so English/Chinese titles with one borrowed glyph stay eligible.
    """
    if not title:
        return False
    if len(_VISIBLE_LANGUAGE_SCRIPT_RE.findall(title)) >= _VISIBLE_SCRIPT_MIN_CHARS:
        return True
    vietnamese = sum(
        1 for char in title
        if char in _VIETNAMESE_LETTERS or 0x1EA0 <= ord(char) <= 0x1EF9
    )
    return vietnamese >= _VIETNAMESE_MIN_CHARS


def _uses_portuguese(video):
    """Conservative Portuguese detection for visible titles and metadata."""
    if not isinstance(video, dict):
        title = str(video or '')
    else:
        title = str(video.get('title') or '')
        for key in ('default_audio_language', 'default_language'):
            value = str(video.get(key) or '').strip().lower()
            if value.startswith('pt'):
                return True
    # A lone ç is shared with French and is intentionally not enough.
    if _PORTUGUESE_ACCENT_RE.search(title):
        return True
    words = {
        match.group(0).lower()
        for match in _PORTUGUESE_FUNCTION_RE.finditer(title)
    }
    return len(words) >= 2


def visible_language_reason(video, section=None):
    """Return why a visible title fails the language net, or an empty string."""
    title = video.get('title', '') if isinstance(video, dict) else str(video or '')
    if _title_uses_visible_foreign_language(title):
        return 'visible_language'
    # Music has its own curated lane; leave its current filter behavior intact.
    if str(section or '').lower() == 'music':
        return ''
    if _uses_portuguese(video):
        return 'portuguese'
    return ''


def visible_language_blocked(video, section=None):
    """Visible-title language net; accepts a video dict or a title string."""
    return bool(visible_language_reason(video, section))


def visible_language_gate(video):
    return not visible_language_blocked(video)


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
    if feed_name == 'podcast':
        return 2
    if feed_name == 'music':
        return 3
    if feed_name == 'editorial':
        return 4
    return 5


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
AI_FEED_DISPLAY_CAP = 40
AI_MIN_DURATION_SECONDS = 8 * 60

_AI_PROMO_TITLE_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:live|pregame|premiere|trailer|livestream)(?![A-Za-z0-9])',
    re.IGNORECASE,
)


def ai_title_promo_blocked(video):
    """AI-only title ban for live/pregame/premiere/trailer promotions."""
    title = str(video.get('title') or '')
    return bool(_AI_PROMO_TITLE_RE.search(title))


def filter_ai_duration_and_promo_titles(videos):
    """Apply the approved AI 8-minute + promo-title gates.

    Returns ``(kept, dropped_short, dropped_promo_title)``.  Missing duration
    counts as zero, so it fails the 8-minute gate.
    """
    kept, dropped_short, dropped_promo_title = [], 0, 0
    for video in videos:
        if int(video.get('duration_seconds') or 0) < AI_MIN_DURATION_SECONDS:
            dropped_short += 1
            continue
        if ai_title_promo_blocked(video):
            dropped_promo_title += 1
            continue
        kept.append(video)
    return kept, dropped_short, dropped_promo_title


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


COMMUNITY_CLASSIC_DAYS = 730


def is_community_classic(video, now=None):
    """Return whether a community/HN pick predates the two-year cutoff."""
    if not isinstance(video, dict):
        return False
    source = str(video.get('source') or '')
    pick_source = str(video.get('pick_source') or '')
    if source != 'community' and pick_source != '社区推荐':
        return False
    published = published_at_dt(video)
    if published is None:
        return False
    age_seconds = (_freshness_now(now) - published).total_seconds()
    return age_seconds > COMMUNITY_CLASSIC_DAYS * 86400


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


def cap_ai_feed_display(videos, *, now=None, sources=None, cap=AI_FEED_DISPLAY_CAP):
    """Keep the highest-scored AI videos and return ``(kept, dropped)``.

    Candidates must already have passed every AI eligibility gate. Ranking
    uses the existing v1 scorer with channel medians, then the existing
    freshness key as a stable tie-break. The returned list is recency-first
    because the cap decides which videos stay, not the tab's display order.
    """
    videos = list(videos)
    limit = max(0, int(cap))
    at = _freshness_now(now)
    if len(videos) <= limit:
        return sorted(videos, key=lambda video: freshness_sort_key(video, now=at)), 0
    if limit == 0:
        return [], len(videos)

    source_rows = load_source_rows(sources)
    medians = channel_median_views(videos, now=at)
    ranked = []
    for video in videos:
        channel_id = str(video.get('channel_id') or '')
        result = score_video(
            video, channel_median_views=medians.get(channel_id),
            now=at, sources=source_rows, section='ai',
        )
        ranked.append(((-float(result),) + freshness_sort_key(video, now=at), video))
    ranked.sort(key=lambda pair: pair[0])
    kept = [video for _rank_key, video in ranked[:limit]]
    return sorted(kept, key=lambda video: freshness_sort_key(video, now=at)), len(videos) - limit


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


def channel_display_cap(videos, per_channel=2, order_key=None):
    """Keep at most ``per_channel`` visible videos from any one channel.

    When ``order_key`` is supplied, higher-priority videos (for example more
    viewed trending items) are kept first; otherwise the incoming order is
    preserved. Returned videos stay in their incoming order.
    """
    kept, dropped_videos = _channel_display_cap_split(
        videos, per_channel=per_channel, order_key=order_key,
    )
    return kept, len(dropped_videos)


def _channel_display_cap_split(videos, per_channel=2, order_key=None):
    videos = list(videos)
    limit = max(0, int(per_channel))
    if limit == 0:
        return [], videos
    order = list(range(len(videos)))
    if order_key is not None:
        order.sort(key=lambda index: order_key(videos[index]))
    counts, keep, dropped = {}, set(), []
    for index in order:
        video = videos[index]
        channel = str(video.get('channel_id') or video.get('channel') or '')
        if not channel:
            keep.add(index)
            continue
        if counts.get(channel, 0) >= limit:
            dropped.append(video)
            continue
        counts[channel] = counts.get(channel, 0) + 1
        keep.add(index)
    return [video for index, video in enumerate(videos) if index in keep], dropped


def interleave_by_channel(videos, channel_key='channel_id'):
    """Round-robin videos by channel while preserving each channel's rank order."""
    buckets, channel_order = {}, []
    for video in videos:
        channel = str(video.get(channel_key) or video.get('channel') or '')
        if channel not in buckets:
            buckets[channel] = []
            channel_order.append(channel)
        buckets[channel].append(video)
    positions = {channel: 0 for channel in channel_order}
    interleaved = []
    while len(interleaved) < len(videos):
        progressed = False
        for channel in channel_order:
            position = positions[channel]
            if position >= len(buckets[channel]):
                continue
            interleaved.append(buckets[channel][position])
            positions[channel] = position + 1
            progressed = True
        if not progressed:
            break
    return interleaved


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

WHY_GOOD_BANNED_PATTERNS = ('本周新片', '近30天播放', '近 30 天同类', '播放第')


def why_good_is_honest(value):
    """True when a stored reason is non-empty and not metadata paraphrased as a reason."""
    text = str(value or '').strip()
    return bool(text) and not any(pattern in text for pattern in WHY_GOOD_BANNED_PATTERNS)


def _channel_reason(prefix, channel, suffix, fallback):
    channel = str(channel or '').strip()
    if not channel:
        return fallback
    budget = 40 - len(prefix) - len(suffix)
    if budget < 1:
        return fallback
    if len(channel) > budget:
        channel = channel[:budget].rstrip().rstrip(' ,，、:：-')
    return f'{prefix}{channel}{suffix}' if channel else fallback


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
        return _channel_reason(
            '来自 AI 策展频道「', video.get('channel'), '」',
            '来自 AI 策展频道的近期长视频',
        )
    if section in ('podcast', 'music'):
        return _channel_reason(
            '来自策展频道「', video.get('channel'), '」',
            '来自策展频道的近期长视频',
        )
    return _channel_reason(
        '来自频道「', video.get('channel'), '」的近期长视频',
        '来自频道的近期长视频',
    )


def why_good_or_existing(video, section='trending', rank=None):
    """Keep an honest stored reason; replace banned metadata or fill a missing one."""
    existing = video.get('why_good')
    if why_good_is_honest(existing):
        return existing
    return why_good_for(video, section, rank=rank)


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
_PICKS_OFFICIAL_VENDOR_RE = re.compile(
    r'openai|nvidia|hyundai|bambu\s*lab|nintendo|'
    r'(?<![A-Za-z0-9])(?:tesla|samsung|google|microsoft|amazon|sony|intel|amd|'
    r'qualcomm|adobe|canon|nikon|dji|xiaomi|huawei|oneplus|lenovo|dell|asus|'
    r'acer|logitech|razer|corsair|apple)(?![A-Za-z0-9])',
    re.IGNORECASE,
)


def is_official_brand_clip(video):
    """Detect official/brand promotional clips from title or channel name."""
    title = str(video.get('title') or '')
    channel = str(video.get('channel') or '')
    if any(marker in title for marker in _PICKS_OFFICIAL_CJK) or any(marker in channel for marker in _PICKS_OFFICIAL_CJK):
        return True
    if _PICKS_OFFICIAL_VENDOR_RE.search(channel):
        return True
    if _PICKS_OFFICIAL_CHANNEL_RE.search(channel):
        return True
    return bool(_PICKS_OFFICIAL_TITLE_RE.search(title))


OFFICIAL_SHORT_MAX_SECONDS = 180

_OBVIOUS_PROMO_TITLE_RE = re.compile(
    r'\b(?:trailer|teaser|launch\s+video|official\s+(?:music\s+)?(?:video|mv)|'
    r'promo|promotional|commercial|advertisement)\b',
    re.IGNORECASE,
)


def is_official_short_promo(video, section=None):
    """Return True for an official/brand clip shorter than three minutes."""
    if int(video.get('duration_seconds') or 0) >= OFFICIAL_SHORT_MAX_SECONDS:
        return False
    if not is_official_brand_clip(video):
        return False
    if str(section or '').lower() in ('community', 'videos'):
        # Community/HN is recommender-driven; only strip an obvious short
        # trailer/promo, never a normal short talk or performance.
        return bool(_OBVIOUS_PROMO_TITLE_RE.search(str(video.get('title') or '')))
    return True


# Content-type filter -------------------------------------------------------
# Dramas/TV episodes, variety/news, trailers, full-episode reuploads, kids
# cartoons, and scripted episode factories are not editorial recommendations.
# Science/tech/documentary/talk channels are explicitly protected so the
# heuristics stay conservative around the content this site wants to keep.

_CONTENT_TYPE_ALLOW_CHANNEL_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:veritasium|mark\s+rober|kurzgesagt|linus\s+tech\s+tips|'
    r'3blue1brown|computerphile|numberphile|pbs\s+space\s+time|pbs\s+eons|ted|tedx|'
    r'stanford|mit\s+opencourseware|mit\s+csail|y\s+combinator|a16z|sequoia\s+capital)'
    r'(?![A-Za-z0-9])',
    re.IGNORECASE,
)
_CONTENT_FULL_EPISODE_RE = re.compile(
    r'\bfull[\s-]*(?:episode|movie|movies|film)\b|\bnigerian\s+movies?\b',
    re.IGNORECASE,
)
_CONTENT_TRAILER_RE = re.compile(
    r'\b(?:official\s+)?(?:trailer|teaser)\b|\b(?:launch|overview)\s+(?:video|trailer)\b',
    re.IGNORECASE,
)
_CONTENT_PROMO_TITLE_RE = re.compile(
    r'\b(?:promo|promotional|product\s+(?:video|demo)|launch\s+video|'
    r'advertisement|commercial)\b',
    re.IGNORECASE,
)
_CONTENT_NEWS_CHANNEL_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:cnn|itv\s+news|9\s*news(?:\s+australia)?|ms\s+now|'
    r'fox\s+business|dw\s+news|fox\s+news|msnbc|bbc\s+news|sky\s+news|abc\s+news|'
    r'cbs\s+news|nbc\s+news|al\s+jazeera|reuters)(?![A-Za-z0-9])',
    re.IGNORECASE,
)
_CONTENT_POLITICS_RE = re.compile(
    r'\b(?:midterms?|midterm\s+elections?|election\s+(?:day|results?|rout|losses?|night)|'
    r'blue\s+tsunami|trump|biden|harris|democrats?|republicans?|'
    r'senate\s+(?:race|majority)|house\s+(?:race|majority)|voter\s+fraud)\b',
    re.IGNORECASE,
)
_CONTENT_VARIETY_CHANNEL_RE = re.compile(
    r'jimmy\s+kimmel|the\s+tonight\s+show|tonight\s+show\s+starring|'
    r'late\s+night\s+with\s+seth\s+meyers|saturday\s+night\s+live|\bsnl\b|'
    r'the\s+daily\s+show|last\s*week\s*tonight',
    re.IGNORECASE,
)
_CONTENT_DRAMA_CHANNEL_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:har\s+pal\s+geo|green\s+tv|laser\s+vision|natok|geo\s+tv|'
    r'geo\s+entertainment|hum\s+tv|ary\s+digital|zee\s+tv|star\s+plus|star\s+jalsha|'
    r'colors\s+tv|sony\s+(?:tv|entertainment)|sab\s+tv|taarak\s+mehta|'
    r'upin\s*&\s*ipin)(?![A-Za-z0-9])',
    re.IGNORECASE,
)
_CONTENT_SCRIPTED_CHANNEL_RE = re.compile(r'dhar\s+mann', re.IGNORECASE)
_CONTENT_KIDS_RE = re.compile(
    r'cocomelon|nursery\s+rhymes|kids\s+songs|dc\s*kids|kids\s+cartoons?|'
    r'cartoon\s+full\s+episode',
    re.IGNORECASE,
)
_CONTENT_TV_EPISODE_RE = re.compile(r'\b(?:ep|episode)\.?\s*#?\s*\d+\b', re.IGNORECASE)
_CONTENT_DRAMA_TITLE_RE = re.compile(
    r'\bnatok\b|\bdrama\b|\bepisode\b.{0,40}\b(?:eng|english)?\s*sub\b',
    re.IGNORECASE,
)
_CONTENT_OFFICIAL_MV_RE = re.compile(
    r'\bofficial\s+(?:music\s+)?(?:video|mv)\b|\bofficial\s+visuali[sz]er\b|'
    r'\bmusic\s+video\b|\bm\/?v\b',
    re.IGNORECASE,
)

# Trending-only entertainment cleanup. These are title/channel rules, never
# video ids. The science/tech allow-list above runs first so explainers and
# talks are not caught by broad words such as "sketch" or "flex".
_CONTENT_PRANK_VLOG_CHANNEL_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:faze\s+(?:rug|kay|adapt|sway|teeqo)|jake\s+paul|'
    r'logan\s+paul|bryce\s+hall|david\s+dobrik)(?![A-Za-z0-9])',
    re.IGNORECASE,
)
_CONTENT_PRANK_VLOG_TITLE_RE = re.compile(
    r'\bprank(?:s|ed|ing)?\b|'
    r'\b(?:vlog|vlogging)\s*[-:]?\s*prank\b|\bprank\s*[-:]?\s*(?:vlog|vlogging)\b|'
    r'\bi\s+(?:bought|got)\s+(?:my|a)\s+dream\s+(?:car|house)\b|'
    r'\b(?:car|house)\s+flex\b|\bdream\s+(?:car|house)\s+(?:tour|reveal)\b',
    re.IGNORECASE,
)
_CONTENT_PARODY_TITLE_RE = re.compile(
    r'\bYTP\b|\byoutube\s+poop\b|\btry\s+not\s+to\s+laugh\b|'
    r'\bparody\s+(?:edit|compilation|video|dub)\b|\bedit(?:ed)?\s+parody\b',
    re.IGNORECASE,
)
_CONTENT_SKIT_CHANNEL_RE = re.compile(
    r'(?<![A-Za-z0-9])samspedy(?![A-Za-z0-9])',
    re.IGNORECASE,
)
_CONTENT_SKIT_TITLE_RE = re.compile(
    r'\bskit\b|\bsketch\b|\bshort[\s-]+drama\b|\bmini[\s-]?drama\b|'
    r'\bcomedy\s+(?:skit|sketch|short|video)\b',
    re.IGNORECASE,
)
_CONTENT_HINDI_SONG_RE = re.compile(
    r'\bbollywood\b|'
    r'\b(?:hindi|tamil|telugu|punjabi|marathi|malayalam|kannada|bengali|'
    r'gujarati|urdu|bhojpuri|rajasthani)\s+(?:[A-Za-z]+\s+){0,3}songs?\b|'
    r'\bsongs?\b.{0,30}\b(?:hindi|tamil|telugu|punjabi|marathi|malayalam|'
    r'kannada|bengali|gujarati|urdu|bhojpuri|rajasthani)\b',
    re.IGNORECASE,
)

# Trending brand-collab films use a small documented marker list rather than
# treating every "x" in a science/tech title as a collaboration.
_CONTENT_BRAND_COLLAB_X_BRANDS = (
    r'dhl|fedex|ups|usps|amazon|walmart|target|nike|adidas|puma|'
    r'coca[- ]?cola|pepsi|mcdonald\'?s|starbucks|spotify|apple|samsung|'
    r'google|microsoft|meta|sony|nintendo|disney|netflix|airbnb|uber|lyft|'
    r'doordash|red\s+bull'
)
_CONTENT_BRAND_COLLAB_PRESENTED_BRANDS = (
    r'dhl|fedex|ups|usps|amazon|walmart|target|nike|adidas|puma|'
    r'coca[- ]?cola|pepsi|mcdonald\'?s|starbucks|spotify|apple|samsung|'
    r'google|microsoft|meta|sony|nintendo|disney|netflix|airbnb|uber|lyft|'
    r'doordash'
)
_CONTENT_BRAND_COLLAB_RE = re.compile(
    rf'\b(?:{_CONTENT_BRAND_COLLAB_X_BRANDS})\s*[x×]\s*[A-Z0-9]|'
    rf'\b(?:presented\s+by|in\s+partnership\s+with)\s+'
    rf'(?:{_CONTENT_BRAND_COLLAB_PRESENTED_BRANDS})\b|'
    r'\bbranded\s+content\b|\bbrand\s+collab(?:oration)?\b',
    re.IGNORECASE,
)

# Entertainment challenge/fidget/confession factories. Keep this list small
# and documented; explainers and real documentaries stay outside it.
_CONTENT_ENTERTAINMENT_CHANNEL_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:mr\s*beast|mrbeast|zhc|og\s+crew|quantastic|'
    r'beast\s+react|airrack|stokes\s+twins|brent\s+rivera|ben\s+azelart|'
    r'rebecca\s+zamolo|preston|unspeakable)(?![A-Za-z0-9])',
    re.IGNORECASE,
)
_CONTENT_ENTERTAINMENT_TITLE_RE = re.compile(
    r'\btrapped\s+my\s+(?:wife|girlfriend|husband|boyfriend|mom|dad)\b|'
    r'\bconfession\s+booth\b|\b2\s+truths?\s+(?:and|&)\s+1\s+lie\b|'
    r'\bfidget\s+toys?\b|\bsquish(?:y|ies)\b',
    re.IGNORECASE,
)
_CONTENT_MOVIE_REVIEW_RE = re.compile(
    r'\b(?:movie|film)\s+review\b|\breview\s+of\s+(?:the\s+)?(?:movie|film)\b|'
    r'影评|影評',
    re.IGNORECASE,
)
_CONTENT_INDIC_FAN_EDIT_CHANNEL_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:editzz?|fan\s*edits?|fanedit)(?![A-Za-z0-9])',
    re.IGNORECASE,
)
_CONTENT_INDIC_ENGLISH_SENTENCE_RE = re.compile(
    r'\b(?:the|and|how|why|what|when|where|this|that|with|from|for|of|to|in|on|'
    r'is|are|was|were|you|your|i|we|they)\b',
    re.IGNORECASE,
)

# Music keeps performances and music-artist interviews; actor/film promo chats
# are not tracks and are filtered in the music lane only.
_MUSIC_KEEP_RE = re.compile(
    r'\ba\s+colors\s+(?:show|interview)\b|\btiny\s+desk\b|\blive\s+lounge\b|'
    r'\bessential\s+mix\b|\bbig\s+weekend\b|\bkexp\b|\bboiler\s+room\b|'
    r'\bfull\s+performance\b|\bconcert\b|\blive\b',
    re.IGNORECASE,
)
_MUSIC_NON_MUSIC_INTERVIEW_RE = re.compile(
    r'\brate\s*(?:&|and|or)\s*slate\b|\bunpopular\s+opinions\b|'
    r'\bbed[-\s]?breaking\s+scenes?\b|\bwrap\s+gifts?\b|'
    r'\b(?:film|movie|tv)\s+(?:promo|press|junket)\b|'
    r'\b(?:actor|actress)(?:es)?\s+interviews?\b|'
    r'\b(?:olivia\s+colman|jenna\s+ortega)\b.{0,100}\binterview\b',
    re.IGNORECASE,
)


TRENDING_MIN_RESULTS = 30
_TRENDING_RESTORE_SEVERITY = {
    'event_cap': 0,
    'channel_display_cap': 0,
    'trailer': 1,
    'promo': 1,
    'brand_promo': 2,
    'language': 3,
    'visible_language': 3,
    'entertainment': 4,
    'brand_collab': 4,
    'movie_review': 4,
    'indic_romanized': 4,
    'parody_edit': 5,
    'prank_vlog': 5,
    'comedy_skit': 5,
    'hindi_song': 5,
    'portuguese': 5,
    'drama_tv': 6,
    'full_episode': 6,
    'kids': 6,
    'scripted_drama': 6,
}

_EVENT_TYPE_RE = re.compile(
    r'\b(?:crash(?:es|ed)?|collision|attack(?:ed|s)?|shooting|explosion|blast|'
    r'fire|earthquake|hurricane|typhoon|flood|derailment|hostage|rescue|'
    r'protest|riot|lawsuit|indictment|verdict|election|war|strike|blackout|'
    r'meltdown|outage|hack)(?:s|ed|ing)?\b',
    re.IGNORECASE,
)
_EVENT_ENTITY_STOPWORDS = frozenset('''
    about after again before breaking could deadly details every from full how
    into just live more most new news over should some still such that their
    there these they this those update video videos watch what when where which
    while will with would why
'''.split())


def _event_signatures(video):
    title = str(video.get('title') or '')
    entities = {
        match.group(0)
        for match in re.finditer(r"(?<![A-Za-z0-9])[A-Z][A-Za-z0-9'’-]{4,}(?![A-Za-z0-9])", title)
        if match.group(0).lower() not in _EVENT_ENTITY_STOPWORDS
    }
    event_types = {match.group(0).lower() for match in _EVENT_TYPE_RE.finditer(title)}
    return {(entity.lower(), event_type) for entity in entities for event_type in event_types}


def cap_same_event(videos, per_event=2):
    """Cap same-entity/same-event-type clusters, keeping the highest-viewed items.

    A cluster requires both a distinctive proper-noun entity (at least five
    characters) and an explicit event-type word. Generic title words never form
    a cluster on their own.
    """
    videos = list(videos)
    if len(videos) < 2:
        return videos, []
    groups = {}
    for index, video in enumerate(videos):
        for signature in _event_signatures(video):
            groups.setdefault(signature, []).append(index)
    dropped = set()
    for signature in sorted(groups):
        candidates = [index for index in groups[signature] if index not in dropped]
        if len(candidates) <= max(0, int(per_event)):
            continue
        ordered = sorted(
            candidates,
            key=lambda index: (-_video_view(videos[index]), str(videos[index].get('id', ''))),
        )
        dropped.update(ordered[max(0, int(per_event)):])
    kept = [video for index, video in enumerate(videos) if index not in dropped]
    dropped_videos = [video for index, video in enumerate(videos) if index in dropped]
    return kept, dropped_videos


def content_type_blocked(video, section=None):
    """Return ``(blocked, reason)`` for non-editorial content types.

    Community/HN feeds are intentionally left alone; callers can apply the
    short official-trailer rule there separately.
    """
    section = str(section or 'trending').lower()
    if section in ('community', 'videos'):
        return False, ''
    title = str(video.get('title') or '')
    channel = str(video.get('channel') or '')
    if not title and not channel:
        return False, ''
    if _CONTENT_TYPE_ALLOW_CHANNEL_RE.search(channel):
        return False, ''
    if _CONTENT_FULL_EPISODE_RE.search(title):
        return True, 'full_episode'
    if _CONTENT_TRAILER_RE.search(title):
        return True, 'trailer'

    if section == 'music':
        # Music keeps tracks/MVs and curated concerts; only clear promos go.
        if _MUSIC_KEEP_RE.search(title):
            return False, ''
        if _MUSIC_NON_MUSIC_INTERVIEW_RE.search(title):
            return True, 'non_music_interview'
        if _CONTENT_PROMO_TITLE_RE.search(title):
            return True, 'promo'
        return False, ''

    if section == 'podcast':
        if _CONTENT_DRAMA_CHANNEL_RE.search(channel) or _CONTENT_SCRIPTED_CHANNEL_RE.search(channel):
            return True, 'drama_tv'
        if _CONTENT_KIDS_RE.search(title) or _CONTENT_KIDS_RE.search(channel):
            return True, 'kids'
        return False, ''

    if section == 'ai':
        if _CONTENT_PROMO_TITLE_RE.search(title):
            return True, 'promo'
        return False, ''

    if _CONTENT_NEWS_CHANNEL_RE.search(channel):
        return True, 'news'
    if _CONTENT_VARIETY_CHANNEL_RE.search(channel):
        return True, 'variety'
    if _CONTENT_DRAMA_CHANNEL_RE.search(channel):
        return True, 'drama_tv'
    if _CONTENT_SCRIPTED_CHANNEL_RE.search(channel):
        return True, 'scripted_drama'
    if _CONTENT_KIDS_RE.search(title) or _CONTENT_KIDS_RE.search(channel):
        return True, 'kids'
    if _CONTENT_DRAMA_TITLE_RE.search(title):
        return True, 'drama_tv'
    if section == 'trending':
        if _CONTENT_TV_EPISODE_RE.search(title):
            return True, 'tv_episode'
        if _CONTENT_OFFICIAL_MV_RE.search(title):
            return True, 'official_mv'
        if _CONTENT_POLITICS_RE.search(title):
            return True, 'news'
        if _CONTENT_PRANK_VLOG_CHANNEL_RE.search(channel) or _CONTENT_PRANK_VLOG_TITLE_RE.search(title):
            return True, 'prank_vlog'
        if _CONTENT_PARODY_TITLE_RE.search(title):
            return True, 'parody_edit'
        if _CONTENT_SKIT_CHANNEL_RE.search(channel) or _CONTENT_SKIT_TITLE_RE.search(title):
            return True, 'comedy_skit'
        if _CONTENT_MOVIE_REVIEW_RE.search(title):
            return True, 'movie_review'
        if (
            _CONTENT_INDIC_FAN_EDIT_CHANNEL_RE.search(channel)
            and title.count('|') >= 2
            and len(_CONTENT_INDIC_ENGLISH_SENTENCE_RE.findall(title)) < 2
        ):
            return True, 'indic_romanized'
        if _CONTENT_ENTERTAINMENT_CHANNEL_RE.search(channel) or _CONTENT_ENTERTAINMENT_TITLE_RE.search(title):
            return True, 'entertainment'
        if _CONTENT_BRAND_COLLAB_RE.search(title):
            return True, 'brand_collab'
        if _CONTENT_HINDI_SONG_RE.search(title):
            return True, 'hindi_song'
        # Official vendor channels' short/mid corporate films (e.g. Hyundai
        # "30 Years of Scale, Trust and Progress") are ads, even if >3 minutes.
        if _PICKS_OFFICIAL_VENDOR_RE.search(channel) and int(video.get('duration_seconds') or 0) < 15 * 60:
            return True, 'brand_promo'
    return False, ''


def trending_quality_reason(video, now=None):
    """Return the first trending quality-filter reason for a video."""
    visible_reason = visible_language_reason(video, section='trending')
    if visible_reason:
        return visible_reason
    if not language_gate(video):
        return 'language'
    blocked, reason = content_type_blocked(video, 'trending')
    return reason if blocked else ''


def _trending_restore_key(item):
    reason, video = item
    severity = _TRENDING_RESTORE_SEVERITY.get(reason, 7)
    return (severity, -_video_view(video), str(video.get('id', '')))


def filter_trending_quality(videos, *, now=None, minimum=TRENDING_MIN_RESULTS, per_channel=None):
    """Apply trending quality rules, then restore the least-bad items to a floor.

    Returns ``(kept, dropped_reasons, restored_count, restored_reasons)``. The
    dropped counts describe the original filter result; restored items are
    counted separately so callers can report both numbers honestly.
    """
    kept, dropped = [], []
    for video in videos:
        reason = trending_quality_reason(video, now=now)
        if reason:
            dropped.append((reason, video))
        else:
            kept.append(video)
    kept, event_dropped = cap_same_event(kept)
    dropped.extend(('event_cap', video) for video in event_dropped)
    if per_channel is not None:
        kept, channel_dropped = _channel_display_cap_split(
            kept, per_channel=per_channel,
            order_key=lambda video: (-_video_view(video), str(video.get('id', ''))),
        )
        dropped.extend(('channel_display_cap', video) for video in channel_dropped)
    dropped_reasons = Counter(reason for reason, _video in dropped)
    restored_reasons = Counter()
    if len(kept) < max(0, int(minimum)):
        need = max(0, int(minimum)) - len(kept)
        for reason, video in sorted(dropped, key=_trending_restore_key)[:need]:
            kept.append(video)
            restored_reasons[reason] += 1
    return kept, dropped_reasons, sum(restored_reasons.values()), restored_reasons


# Same-id channels listed under both AI and podcast use a topic-fit gate for
# the AI column. Keep this explicit list in one place so it can be extended.
# Matching is case-insensitive and uses ASCII alphanumeric word-ish edges, so
# short tokens such as "AI" do not match inside "said" or "maintain".
AI_TOPIC_KEYWORDS = (
    'AI', 'A.I.', 'AGI', 'LLM', 'LLMs', 'GPT', 'ChatGPT', 'Claude', 'Gemini',
    'Grok', 'OpenAI', 'Anthropic', 'DeepMind', 'Mistral', 'machine learning',
    'deep learning', 'neural net', 'neural nets', 'neural network',
    'neural networks', 'language model', 'language models', 'foundation model',
    'foundation models', 'transformer', 'alignment', 'agentic',
    'artificial intelligence',
)


def _keyword_pattern(keyword):
    parts = [re.escape(part) for part in str(keyword).split()]
    escaped = r'\s+'.join(parts)
    return rf'(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])'


AI_TOPIC_RE = re.compile('|'.join(_keyword_pattern(keyword) for keyword in AI_TOPIC_KEYWORDS), re.IGNORECASE)


def dual_topic_channel_ids(sources=None):
    """Return channel ids that sources.yaml lists under both AI and podcast."""
    ids = set()
    for row in load_source_rows(sources):
        if not isinstance(row, dict) or row.get('type') not in (None, 'channel'):
            continue
        topics = {str(topic).lower() for topic in (row.get('topics') or [])}
        if not {'ai', 'podcast'} <= topics:
            continue
        channel_id = str(row.get('external_id') or row.get('youtube_channel_id') or '')
        if channel_id:
            ids.add(channel_id)
    return ids


def matches_ai_topic_keywords(video):
    """Return whether a video title or description matches the AI topic list."""
    snippet = video.get('snippet') or {}
    text = '\n'.join(str(value or '') for value in (
        video.get('title'), snippet.get('title'),
        video.get('description'), snippet.get('description'),
    ))
    return bool(AI_TOPIC_RE.search(text))


def is_ai_topic_video(video, dual_channel_ids=None):
    """Apply the AI-topic gate only to channels that are AI+podcast dual-listed."""
    channel_id = str(video.get('channel_id') or (video.get('snippet') or {}).get('channelId') or '')
    ids = dual_topic_channel_ids() if dual_channel_ids is None else dual_channel_ids
    if channel_id not in ids:
        return True
    return matches_ai_topic_keywords(video)


def filter_ai_topic_videos(videos, dual_channel_ids=None):
    """Drop non-AI items from dual-listed channels and return the dropped count."""
    ids = dual_topic_channel_ids() if dual_channel_ids is None else dual_channel_ids
    kept = [video for video in videos if is_ai_topic_video(video, ids)]
    return kept, len(videos) - len(kept)


def build_picks(feeds, generated_at=None, limit=10, now=None, sources=None):
    """Generate the 今日精选 feed (≤10) from scored per-column candidates."""
    limit = max(0, min(10, int(limit)))
    at = now or datetime.now(UTC)
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    at = at.astimezone(UTC)
    source_rows = load_source_rows(sources)
    dual_channel_ids = dual_topic_channel_ids(source_rows)
    labels = {'community': '社区推荐', 'ai': 'AI前沿', 'podcast': '播客', 'editorial': '科学教育'}
    groups = {}

    for key in ('community', 'ai', 'podcast', 'editorial'):
        videos = []
        for video in (feeds.get(key) or {}).get('videos') or []:
            if key == 'ai' and not is_ai_topic_video(video, dual_channel_ids):
                continue
            if not language_gate(video):
                continue
            if key != 'community' and visible_language_blocked(video, key):
                continue
            if key != 'community':
                blocked, _reason = content_type_blocked(video, key)
                if blocked:
                    continue
            if key == 'ai' and ai_title_promo_blocked(video):
                continue
            duration_seconds = int(video.get('duration_seconds') or 0)
            if duration_seconds < PICKS_MIN_DURATION_SECONDS:
                continue
            if duration_seconds < PICKS_OFFICIAL_MIN_DURATION_SECONDS and is_official_brand_clip(video):
                continue
            existing_why = video.get('why_good')
            if why_good_is_honest(existing_why):
                why = existing_why
            elif existing_why or key in ('community', 'ai', 'editorial'):
                why = why_good_for(video, key)
            else:
                why = None
            if not why and key != 'editorial':
                continue
            videos.append(dict(video, why_good=why or '', source=key))
        if key != 'community':
            videos, _dropped = drop_stale_videos(videos, now=at)
            videos.sort(key=lambda item: freshness_sort_key(item, now=at))
        if key == 'editorial':
            for rank, video in enumerate(sorted(videos, key=lambda item: (-_video_view(item), str(item.get('id', '')))), 1):
                video['why_good'] = why_good_or_existing(video, 'editorial', rank=rank)
        groups[key] = videos

    medians = channel_median_views(
        [video for key in ('community', 'ai', 'podcast', 'editorial') for video in groups[key]],
        now=at,
    )
    quotas = {'community': 4, 'ai': 4, 'podcast': 2}
    order = ('community', 'ai', 'podcast')
    picked, seen = [], set()
    used = {key: 0 for key in order}
    channel_picks = {}

    def score_candidate(candidate, key):
        channel_id = str(candidate.get('channel_id') or '')
        return score_video(
            candidate, channel_median_views=medians.get(channel_id),
            already_picked_from_channel=channel_picks.get(channel_id, 0),
            now=at, sources=source_rows, section=key,
        )

    def accept(candidate, key, result):
        channel_id = str(candidate.get('channel_id') or '')
        seen.add(candidate.get('id'))
        if channel_id:
            channel_picks[channel_id] = channel_picks.get(channel_id, 0) + 1
        accepted = dict(candidate, pick_source=labels[key], score=float(result),
                        score_parts=dict(result.parts))
        accepted['community_classic'] = is_community_classic(accepted, now=at)
        picked.append(accepted)

    def select_best(key):
        best = None
        for candidate in groups[key]:
            if candidate.get('id') in seen:
                continue
            result = score_candidate(candidate, key)
            if result.excluded:
                continue
            rank_key = (-float(result),) + freshness_sort_key(candidate, now=at)
            if best is None or rank_key < best[0]:
                best = (rank_key, candidate, result)
        if best is None:
            return False
        _rank_key, candidate, result = best
        accept(candidate, key, result)
        return True

    while len(picked) < limit:
        progressed = False
        for key in order:
            if used[key] >= quotas[key]:
                continue
            if select_best(key):
                used[key] += 1
                progressed = True
        if not progressed:
            break

    for key in order:
        while len(picked) < limit and select_best(key):
            pass

    editorial_cursor = 0
    editorial = groups['editorial']
    while len(picked) < limit and editorial_cursor < len(editorial):
        candidate = editorial[editorial_cursor]
        editorial_cursor += 1
        if candidate.get('id') in seen:
            continue
        result = score_candidate(candidate, 'editorial')
        if result.excluded:
            continue
        accept(candidate, 'editorial', result)

    return dict(generated_at=generated_at or iso_now(), kind='picks', limit=limit,
                mix=quotas, videos=picked)

def youtube_videos(client, key, ids):
    found = []
    for offset in range(0, len(ids), 50):
        response = client.get(YOUTUBE_API + 'videos', dict(part='snippet,contentDetails,statistics,player,status', maxWidth=640, maxHeight=640, id=','.join(ids[offset:offset+50]), key=key), youtube=True)
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
    found_ids = {item.get('id') for item in records if item.get('id')}
    dropped_playability = Counter()
    dropped_playability['missing'] += len(candidate_ids - found_ids)
    trending_dropped_reasons = Counter()
    trending_restored_for_min = 0
    trending_restored_reasons = Counter()

    def accepted():
        nonlocal trending_dropped_reasons, trending_restored_for_min, trending_restored_reasons
        videos = []
        dropped_short = dropped_vertical = dropped_language = 0
        dropped_content_type = dropped_visible_language = dropped_official_short = 0
        quality_ready = []
        for item in records:
            reason = playability_reason(item)
            if reason:
                dropped_playability[reason] += 1
            elif duration(item.get('contentDetails', {}).get('duration')) < 60:
                dropped_short += 1
            elif landscape_only and not landscape_video(item):
                dropped_vertical += 1
            else:
                record = video_record(item)
                if is_official_short_promo(record, name):
                    dropped_official_short += 1
                    continue
                quality_ready.append(record)
        if name == 'trending':
            (videos, trending_dropped_reasons,
             trending_restored_for_min, trending_restored_reasons) = filter_trending_quality(
                quality_ready, per_channel=2,
            )
            dropped_language = trending_dropped_reasons.get('language', 0)
            dropped_visible_language = (
                trending_dropped_reasons.get('visible_language', 0)
                + trending_dropped_reasons.get('portuguese', 0)
            )
            dropped_content_type = sum(
                count for reason, count in trending_dropped_reasons.items()
                if reason not in (
                    'language', 'visible_language', 'portuguese',
                    'event_cap', 'channel_display_cap',
                )
            )
        else:
            for record in quality_ready:
                if not language_gate(record):
                    dropped_language += 1
                    continue
                if visible_language_blocked(record, name):
                    dropped_visible_language += 1
                    continue
                blocked, _reason = content_type_blocked(record, name)
                if blocked:
                    dropped_content_type += 1
                    continue
                videos.append(record)
        videos, dropped_channel = dedupe_channel_caps(videos, _load_existing_feeds(name, output), feed_name=name)
        videos.sort(key=lambda v: (-v['view_count'], v['id']))
        return (videos, dropped_short, dropped_vertical, dropped_language, dropped_channel,
                dropped_content_type, dropped_visible_language, dropped_official_short)

    (videos, dropped_short, dropped_vertical, dropped_language, dropped_channel,
     dropped_content_type, dropped_visible_language, dropped_official_short) = accepted()
    dropped_podcast = 0
    if name == 'podcast':
        videos, dropped_podcast = podcast_display_cap(videos)
    dropped_channel_display_cap = 0
    if name == 'trending':
        dropped_channel_display_cap = trending_dropped_reasons.get('channel_display_cap', 0)
    final_videos = videos[:100]
    if name in ('trending', 'podcast', 'music'):
        for rank, video in enumerate(final_videos, 1):
            video['why_good'] = why_good_or_existing(video, name, rank=rank)
    published = [video['published_at'] for video in final_videos if video['published_at']]

    payload = dict(generated_at=iso_now(), window_days=30, exclude_shorts_under_seconds=60,
                   window_size_days=6, windows=5,
                   candidates_fetched=len(candidate_ids), dropped_short=dropped_short,
                   dropped_vertical=dropped_vertical, dropped_language=dropped_language,
                   dropped_channel=dropped_channel,
                   dropped_content_type=dropped_content_type,
                   dropped_visible_language=dropped_visible_language,
                   dropped_official_short=dropped_official_short,
                   landscape_only=landscape_only,
                   video_duration_buckets=['medium', 'long'], final_count=len(final_videos),
                   quota_units_approx=searches * 100 + quota_video_batches,
                   videos=final_videos)
    if dropped_podcast:
        payload['dropped_podcast_display_cap'] = dropped_podcast
    if dropped_channel_display_cap:
        payload['dropped_channel_display_cap'] = dropped_channel_display_cap
    if name == 'trending':
        payload['dropped_quality_reasons'] = dict(sorted(trending_dropped_reasons.items()))
        for reason, count in trending_dropped_reasons.items():
            payload[f'dropped_{reason}'] = count
        payload['restored_for_min'] = trending_restored_for_min
        if trending_restored_reasons:
            payload['restored_for_min_reasons'] = dict(sorted(trending_restored_reasons.items()))
    if published:
        payload['publish_date_span'] = {'min': min(published), 'max': max(published)}
    if query:
        payload['query'] = query
    if category_id:
        payload['video_category_id'] = category_id
    for reason, count in dropped_playability.items():
        payload[f'dropped_{reason}'] = count
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
            *, rss_fetcher=None, sources_file=None):
    from .podcast_whitelist import (
        fetch_channel_rss_video_ids, fetch_channel_video_ids, normalize_rss_entries,
    )
    key = youtube_key(); client = client or Client(interval=.05, db=None, quota_limit=quota_limit)
    rss_fetcher = rss_fetcher or fetch_channel_rss_video_ids
    channels = yaml.safe_load(Path(channels_file).read_text()).get('channels', [])
    if sources_file is None and Path(channels_file).resolve() == Path('config/ai_channels.yaml').resolve():
        sources_file = 'config/sources.yaml'
    if sources_file:
        channels = channels_for_topic('ai', channels, path=sources_file)
    dual_channel_ids = dual_topic_channel_ids(sources_file or 'config/sources.yaml')
    cutoff = datetime.now(UTC) - timedelta(days=FRESHNESS_MAX_DAYS)
    discovered, units = {}, 0
    for channel in channels:
        channel_id = channel.get('youtube_channel_id')
        if not channel_id:
            continue
        try:
            entries, fallback_units = fetch_channel_video_ids(
                channel_id, rss_fetcher=rss_fetcher, client=client, key=key, feed_name='ai',
            )
        except Exception as error:
            print(f"AI channel skipped: {channel.get('name', channel_id)} ({error})")
            continue
        units += fallback_units
        for entry in normalize_rss_entries(entries):
            vid = entry.get('id')
            published = _feed_timestamp(entry.get('published_at'))
            if vid and (published is None or published >= cutoff):
                discovered[vid] = entry.get('published_at')
    ids = list(discovered)
    cached = load_fresh_feed_records('ai', root=output, cache_days=metadata_cache_days())
    pending = [vid for vid in ids if vid not in cached]
    raws = youtube_videos(client, key, pending); units += (len(pending) + 49) // 50 if pending else 0
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
        record['description'] = (raw.get('snippet') or {}).get('description', '')
        record['_metadata_fetched_at'] = fetched_at
        videos.append(record)
    videos = [v for v in videos if int(v.get('duration_seconds') or 0) >= 60]
    dropped_language = sum(1 for v in videos if not language_gate(v))
    videos = [v for v in videos if language_gate(v)]
    videos, dropped_ai_topic = filter_ai_topic_videos(videos, dual_channel_ids)
    videos, dropped_stale = drop_stale_videos(videos)
    videos, dropped_channel = dedupe_channel_caps(videos, _load_existing_feeds('ai', output), feed_name='ai')
    pre_ai_filter_count = len(videos)
    videos, dropped_ai_short, dropped_ai_promo_title = filter_ai_duration_and_promo_titles(videos)
    dropped_content_type = dropped_visible_language = dropped_official_short = 0
    filtered = []
    for video in videos:
        if visible_language_blocked(video, 'ai'):
            dropped_visible_language += 1
            continue
        blocked, _reason = content_type_blocked(video, 'ai')
        if blocked:
            dropped_content_type += 1
            continue
        if is_official_short_promo(video, 'ai'):
            dropped_official_short += 1
            continue
        filtered.append(video)
    videos = filtered
    for video in videos:
        video['why_good'] = why_good_or_existing(video, 'ai')
    pre_cap_count = len(videos)
    videos, dropped_ai_display_cap = cap_ai_feed_display(
        videos, sources=load_source_rows(sources_file or 'config/sources.yaml'),
    )
    videos, dropped_channel_display_cap = channel_display_cap(videos, per_channel=2)
    payload = dict(generated_at=iso_now(), window_days=FRESHNESS_MAX_DAYS, exclude_shorts_under_seconds=60,
                   quota_units_approx=units, channels_used=len(channels), dropped_language=dropped_language,
                   dropped_ai_topic=dropped_ai_topic, dropped_channel=dropped_channel,
                   dropped_stale=dropped_stale, dropped_ai_display_cap=dropped_ai_display_cap,
                   dropped_channel_display_cap=dropped_channel_display_cap,
                   dropped_ai_short=dropped_ai_short,
                   dropped_ai_promo_title=dropped_ai_promo_title,
                   dropped_content_type=dropped_content_type,
                   dropped_visible_language=dropped_visible_language,
                   dropped_official_short=dropped_official_short,
                   pre_cap_count=pre_cap_count, final_count=len(videos), videos=videos)
    for reason, count in dropped_playability.items():
        payload[f'dropped_{reason}'] = count
    payload = write_feed_if_not_sharply_smaller('ai', payload, output, pre_cap_count=pre_ai_filter_count)
    print(f"AI: {len(payload.get('videos', []))} videos from {len(channels)} channels; approximate YouTube quota units: {units}")
    print(quota_line(quota_limit))
    return payload

def metadata_gates(raw, c, at):
    if not raw or playability_reason(raw):
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
        record['why_good'] = why_good_or_existing(record, 'community')
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
