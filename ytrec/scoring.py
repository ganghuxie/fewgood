"""V1 scoring for 今日精选 candidate ranking.

The formula is intentionally separate from feed ordering. Callers collect the
Stage 1 pool first, then use these helpers to rank candidates within each
column (community / AI / podcast).
"""
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from .sources import load_sources


UTC = timezone.utc
RECENT_DAYS = 7
FRESHNESS_MAX_DAYS = 30
MIN_DURATION_SECONDS = 8 * 60
LONG_DURATION_SECONDS = 20 * 60

TIER_MULTIPLIERS = {1: 0.8, 2: 1.2, 3: 1.0, 4: 1.3}
FREQUENCY_MULTIPLIERS = {0: 1.0, 1: 0.5, 2: 0.2}

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SOURCES = _PROJECT_ROOT / 'config' / 'sources.yaml'

_CLICKBAIT_PHRASES = re.compile(
    r"你绝对想不到|震惊|不敢相信|全网疯传|shocking|"
    r"you\s*(?:won['’]?t|will\s+not)\s+believe",
    re.IGNORECASE,
)
_EMOJI_RE = re.compile('[\U0001F300-\U0001FAFF\u2600-\u27BF]')
_TIMESTAMP_LINE_RE = re.compile(
    r'^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}(?:\s|$)', re.MULTILINE,
)
_GENERIC_SOURCE_LABELS = frozenset({
    'community', 'videos', 'ai', 'podcast', 'editorial', 'music', 'picks',
})


class ScoreResult(float):
    """A numeric final score with its component parts available for reports."""

    def __new__(cls, final, parts, *, excluded=False):
        value = float(final)
        result = super().__new__(cls, value)
        result.final = value
        result.parts = dict(parts)
        result.excluded = bool(excluded)
        return result

    def __getitem__(self, key):
        if key in ('score', 'final'):
            return self.final
        if key in ('score_parts', 'parts'):
            return self.parts
        if key == 'excluded':
            return self.excluded
        return self.parts[key]

    @property
    def score(self):
        return self.final

    @property
    def score_parts(self):
        return self.parts

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def _as_number(value):
    if isinstance(value, bool):
        return float(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _as_int(value, default=0):
    number = _as_number(value)
    return default if number is None else int(number)


def _now_utc(value=None):
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _published_at(value):
    raw = value.get('published_at') if isinstance(value, dict) else value
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_days(video, now=None):
    published = _published_at(video)
    if published is None:
        return None
    return (_now_utc(now) - published).total_seconds() / 86400


def load_source_rows(sources=None):
    """Normalize a sources argument into rows suitable for tier matching.

    ``None`` loads the repo's ``config/sources.yaml``. A path loads that file,
    a payload with a ``sources`` key is unwrapped, and mappings of channel id
    to tier are also accepted for tests and small callers.
    """
    if sources is None:
        return load_sources(_DEFAULT_SOURCES)
    if isinstance(sources, (str, Path)):
        return load_sources(sources)
    if isinstance(sources, dict):
        if 'sources' in sources:
            rows = sources.get('sources') or []
        else:
            rows = []
            for external_id, value in sources.items():
                row = dict(value) if isinstance(value, dict) else {'tier': value}
                row.setdefault('external_id', external_id)
                rows.append(row)
        return rows
    return list(sources)


def _source_tier(video, sources=None):
    channel_id = str(video.get('channel_id') or '')
    channel_name = str(video.get('channel') or '').strip().lower()
    for row in load_source_rows(sources):
        if not isinstance(row, dict):
            continue
        external_id = str(row.get('external_id') or row.get('youtube_channel_id') or '')
        if channel_id and external_id == channel_id:
            tier = _as_int(row.get('tier'), 3)
            return tier if tier in TIER_MULTIPLIERS else 3
        if not channel_id and channel_name:
            names = {
                str(row.get('display_name') or '').strip().lower(),
                str(row.get('handle') or '').strip().lower(),
                str(row.get('id') or '').strip().lower(),
            }
            if channel_name in names - {''}:
                tier = _as_int(row.get('tier'), 3)
                return tier if tier in TIER_MULTIPLIERS else 3
    return 3


def _clean_source_name(value):
    if isinstance(value, dict):
        value = value.get('id') or value.get('source') or value.get('name')
    name = str(value or '').strip().lower()
    if not name or name in _GENERIC_SOURCE_LABELS:
        return None
    if name.startswith(('search:', 'channel_uploads:', 'existing:')):
        return None
    return name


def independent_community_source_count(video):
    """Return the number of distinct community sources attached to a video."""
    for key in ('community_source_count', 'independent_source_count'):
        if video.get(key) is not None:
            return max(0, _as_int(video.get(key)))
    for key in ('community_sources', 'independent_sources', 'source_hits'):
        value = video.get(key)
        if isinstance(value, bool):
            names = {_clean_source_name(value)}
        elif isinstance(value, int):
            return max(0, value)
        elif isinstance(value, dict):
            names = {_clean_source_name(item) for item in value}
        elif isinstance(value, (list, tuple, set)):
            names = {_clean_source_name(item) for item in value}
        elif value is None:
            continue
        else:
            names = {_clean_source_name(value)}
        return len(names - {None})
    value = video.get('sources')
    if isinstance(value, dict):
        value = list(value)
    if isinstance(value, (list, tuple, set)):
        return len({_clean_source_name(item) for item in value} - {None})
    return 0


def has_chapters_from_description(description):
    """Return True when a description contains at least two timestamp lines."""
    return len(_TIMESTAMP_LINE_RE.findall(str(description or ''))) >= 2


def has_chapters(video):
    flag = video.get('has_chapters')
    if flag is not None:
        return bool(flag)
    chapters = video.get('chapters')
    if isinstance(chapters, bool):
        return chapters
    if isinstance(chapters, (list, tuple, set)):
        return len(chapters) >= 2
    if chapters is not None:
        return _as_int(chapters) > 0
    description = video.get('description') or video.get('description_snippet') or ''
    return has_chapters_from_description(description)


def has_captions(video):
    for key in ('has_captions', 'captions'):
        if video.get(key) is not None:
            return bool(video.get(key))
    caption = video.get('caption')
    if caption is None:
        return False
    if isinstance(caption, bool):
        return caption
    return str(caption).strip().lower() == 'true'


def is_clickbait_title(title):
    """Small, explicit clickbait heuristic for the S_str title bonus.

    A title is clickbait when it contains one of the listed sensational
    phrases, has at least 8 ASCII letters with more than 60% uppercase, or
    contains at least three emoji/symbol characters.
    """
    text = str(title or '').strip()
    if _CLICKBAIT_PHRASES.search(text):
        return True
    letters = [char for char in text if char.isascii() and char.isalpha()]
    if len(letters) >= 8 and sum(char.isupper() for char in letters) / len(letters) > 0.60:
        return True
    return len(_EMOJI_RE.findall(text)) >= 3


def channel_median_views(videos, now=None):
    """Median views per channel among unique videos published in the last 30 days."""
    reference = _now_utc(now)
    by_channel = {}
    seen = set()
    for video in videos:
        video_id = str(video.get('id') or '')
        if video_id and video_id in seen:
            continue
        channel_id = str(video.get('channel_id') or '')
        if not channel_id:
            continue
        published = _published_at(video)
        if published is None:
            continue
        if (reference - published).total_seconds() > FRESHNESS_MAX_DAYS * 86400:
            continue
        views = _as_number(video.get('view_count'))
        if views is None:
            continue
        if video_id:
            seen.add(video_id)
        by_channel.setdefault(channel_id, []).append(views)
    return {channel_id: median(values) for channel_id, values in by_channel.items() if values}


def _external_score(video):
    recommenders = video.get('recommenders')
    if recommenders is None:
        recommenders = video.get('hn_score')
    recommenders = max(0, _as_int(recommenders))
    if not recommenders:
        return 0.0
    score = min(1.0, math.log10(1 + recommenders) / math.log10(1 + 300))
    if independent_community_source_count(video) >= 2:
        score = min(1.0, score * 1.3)
    return score


def _relative_score(video, channel_median):
    views = _as_number(video.get('view_count'))
    if views is None or views < 0:
        return 0.0, 1.0
    median_views = _as_number(channel_median)
    ratio = 1.0 if median_views is None or median_views <= 0 else views / median_views
    return min(1.0, math.log10(max(1.0, ratio)) / 1.0), ratio


def _engagement_score(video):
    views = _as_number(video.get('view_count'))
    if views is None or views <= 0:
        return 0.0
    likes = max(0.0, _as_number(video.get('like_count')) or 0.0)
    comments = max(0.0, _as_number(video.get('comment_count')) or 0.0)
    engagement = (likes + 2 * comments) / views
    return min(1.0, engagement / 0.05)


def _structure_score(video):
    from .core import is_official_brand_clip

    duration_seconds = _as_int(video.get('duration_seconds'))
    score = 0.0
    if duration_seconds >= MIN_DURATION_SECONDS:
        score += 0.30
    if duration_seconds >= LONG_DURATION_SECONDS:
        score += 0.10
    if has_chapters(video):
        score += 0.15
    if has_captions(video):
        score += 0.10
    if not is_clickbait_title(video.get('title')):
        score += 0.20
    if not is_official_brand_clip(video):
        score += 0.15
    return min(1.0, score)


def _freshness_multiplier(video, section, now=None):
    if section == 'community':
        return 1.0, None, False
    age_days = _age_days(video, now=now)
    if age_days is None or age_days > FRESHNESS_MAX_DAYS:
        return 0.7, age_days, True
    if age_days <= RECENT_DAYS:
        return 1.0, age_days, False
    return 0.7, age_days, False


def score_video(video, *, channel_median_views=None, already_picked_from_channel=0,
                now=None, sources=None, section=None):
    """Score one 今日精选 candidate with the v1 formula.

    ``section`` is the source column (community / ai / podcast / editorial).
    It defaults to the record's ``source`` or ``feed`` field. Community videos
    always receive tier 4 and never age-decay. ``already_picked_from_channel``
    is the number accepted into the current 今日精选 list so far.
    """
    video = video or {}
    section = section or video.get('source') or video.get('feed')
    recommenders = video.get('recommenders')
    if recommenders is None:
        recommenders = video.get('hn_score')
    community = section in ('community', 'videos') or (
        not section and (_as_int(recommenders) > 0
                         or independent_community_source_count(video) > 0)
    )
    if community and section in (None, 'videos'):
        section = 'community'

    s_ext = _external_score(video)
    s_rel, ratio = _relative_score(video, channel_median_views)
    s_eng = _engagement_score(video)
    s_str = _structure_score(video)
    raw = 0.40 * s_ext + 0.25 * s_rel + 0.20 * s_eng + 0.15 * s_str

    tier = 4 if community else _source_tier(video, sources)
    c_tier = TIER_MULTIPLIERS.get(tier, 1.0)
    picked_count = max(0, _as_int(already_picked_from_channel))
    frequency_excluded = picked_count >= 3
    c_freq = 0.0 if frequency_excluded else FREQUENCY_MULTIPLIERS.get(picked_count, 0.2)
    c_fresh, age_days, freshness_excluded = _freshness_multiplier(video, section, now=now)
    excluded = frequency_excluded or freshness_excluded
    final = 0.0 if excluded else min(1.0, raw * c_tier * c_freq * c_fresh)

    parts = {
        's_ext': s_ext,
        's_rel': s_rel,
        's_eng': s_eng,
        's_str': s_str,
        'raw': raw,
        'c_tier': c_tier,
        'c_freq': c_freq,
        'c_fresh': c_fresh,
        'tier': tier,
        'ratio': ratio,
        'age_days': age_days,
        'community_sources': independent_community_source_count(video),
        'has_chapters': has_chapters(video),
        'has_captions': has_captions(video),
        'clickbait': is_clickbait_title(video.get('title')),
    }
    return ScoreResult(final, parts, excluded=excluded)
