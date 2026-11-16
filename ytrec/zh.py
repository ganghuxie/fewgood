"""Chinese value-add enrichment for visible video cards and topic columns.

This module deliberately keeps external calls behind small functions so the
pipeline can be exercised with mocks and resumed safely from ``zh.json``.
The default card path is a light title+description prompt (no transcript or
comments). Existing usable cache entries are never overwritten unless forced.
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

_GEMINI_EXHAUSTED_MODELS = set()
import yaml

from .core import Client, YOUTUBE_API, iso_now, youtube_key


def load_zh_config(path='config.yaml'):
    try:
        cfg = yaml.safe_load(Path(path).read_text(encoding='utf8')) or {}
    except FileNotFoundError:
        cfg = {}
    zh = dict(cfg.get('zh') or {})
    zh.setdefault('provider', 'gemini')
    zh.setdefault('gemini_model', 'gemini-3.5-flash')
    zh.setdefault('gemini_fallback_model', 'gemini-3.5-flash-lite')
    zh.setdefault('deepseek_model', 'deepseek-chat')
    zh.setdefault('topic_provider', 'deepseek')
    zh.setdefault('topic_deepseek_model', 'deepseek-flash')
    return zh


def parse_json_response(value):
    """Parse a model JSON response, including the common fenced variant."""
    if not isinstance(value, str):
        raise ValueError('LLM response content was not text')
    text = value.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.I)
    text = re.sub(r'\s*```$', '', text).strip()
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < start:
        raise ValueError('LLM response did not contain a JSON object')
    blob = text[start:end + 1]
    blob = re.sub(r',\s*([}\]])', r'\1', blob)  # trailing commas
    result = json.loads(blob)
    if not isinstance(result, dict):
        raise ValueError('LLM response JSON was not an object')
    return result


def truncate_transcript(cues, max_chars=7000):
    """Return bounded prompt text while preserving cue starts for highlights."""
    kept, size = [], 0
    for cue in cues or []:
        text = re.sub(r'\s+', ' ', str(cue.get('text') or '')).strip()
        if not text:
            continue
        start = cue.get('start')
        prefix = f'[{float(start):.1f}s] ' if isinstance(start, (int, float)) else ''
        remaining = max_chars - size
        if remaining <= 0:
            break
        line = (prefix + text)[:remaining]
        kept.append(line)
        size += len(line) + 1
        if len(line) < len(prefix + text):
            break
    return '\n'.join(kept)


def build_prompt(title, description, transcript, comments, has_transcript):
    """Identical user prompt for Gemini and DeepSeek A/B."""
    return (
        'Return JSON only. Translate and recommend this YouTube video for Chinese readers. '
        'title_zh: Chinese title; blurb_zh: one recommendation sentence no more than 40 Chinese characters; '
        'highlights: up to 3 objects with text no more than 30 Chinese characters and start as seconds only when transcript timestamps are present; '
        'comments_zh: translate each supplied comment retaining original and likes.\n\n'
        f'Title: {title}\nDescription: {(description or "")[:1200]}\n'
        f'Has timestamped transcript: {has_transcript}\nTranscript:\n{transcript}\n'
        f'Comments:\n{json.dumps(comments, ensure_ascii=False)}\n'
        'Required shape: {"title_zh":"","blurb_zh":"","highlights":[{"text":"","start":0}],'
        '"comments_zh":[{"original":"","text_zh":"","likes":0}]}'
    )


def _cue_dicts(items):
    cues = []
    for item in items or []:
        if isinstance(item, dict):
            text, start = item.get('text'), item.get('start')
        else:
            text, start = getattr(item, 'text', None), getattr(item, 'start', None)
        try:
            start = float(start)
        except (TypeError, ValueError):
            start = None
        if text:
            cues.append({'start': start, 'text': str(text)})
    return cues


def fetch_transcript(video_id):
    """Try English first, then the service's best available transcript."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return []
    try:
        api = YouTubeTranscriptApi()
        try:
            return _cue_dicts(api.fetch(video_id, languages=['en']))
        except Exception:
            available = list(api.list(video_id))
            return _cue_dicts(available[0].fetch()) if available else []
    except AttributeError:
        try:
            return _cue_dicts(YouTubeTranscriptApi.get_transcript(video_id, languages=['en']))
        except Exception:
            try:
                return _cue_dicts(YouTubeTranscriptApi.get_transcript(video_id))
            except Exception:
                return []
    except Exception:
        return []


def top_comments(client, video_id, key):
    response = client.get(YOUTUBE_API + 'commentThreads', {
        'part': 'snippet', 'videoId': video_id, 'order': 'relevance',
        'maxResults': 20, 'textFormat': 'plainText', 'key': key,
    }, youtube=True)
    comments = []
    for thread in response.get('items', []):
        snippet = thread.get('snippet', {}).get('topLevelComment', {}).get('snippet', {})
        text = str(snippet.get('textDisplay') or snippet.get('textOriginal') or '').strip()
        if len(text) < 8:
            continue
        author = str(snippet.get('authorDisplayName') or '').strip()
        if not author or author == '[deleted]':
            continue
        try:
            likes = int(snippet.get('likeCount') or 0)
        except (TypeError, ValueError):
            likes = 0
        comments.append({'original': text, 'author': author, 'likeCount': likes})
    return sorted(comments, key=lambda item: item['likeCount'], reverse=True)[:3]


def _metadata(db, video_id):
    row = db.execute('SELECT raw FROM metadata WHERE video_id=?', (video_id,)).fetchone()
    if not row or not row['raw']:
        return None
    try:
        return json.loads(row['raw'])
    except json.JSONDecodeError:
        return None


def _video_context(db, client, video, key):
    raw = _metadata(db, video['id'])
    if raw is None:
        response = client.get(YOUTUBE_API + 'videos', {'part': 'snippet', 'id': video['id'], 'key': key}, youtube=True)
        raw = (response.get('items') or [None])[0]
    snippet = (raw or {}).get('snippet', {})
    return snippet.get('title') or video.get('title', ''), snippet.get('description', '')


def _topic_video_context(db, client, video, key):
    """Use title/description already attached to a topic or pool record."""
    title = str(video.get('title') or '').strip()
    if title or db is None:
        return title, str(video.get('description') or '')
    return _video_context(db, client, video, key)


def request_deepseek(prompt, model='deepseek-chat', post=requests.post, thinking=None):
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        raise RuntimeError('Set DEEPSEEK_API_KEY to run enrich-zh')
    payload = {
        'model': model, 'temperature': 0.2, 'response_format': {'type': 'json_object'},
        'messages': [{'role': 'user', 'content': prompt}],
    }
    if thinking is None and str(model).startswith('deepseek-flash'):
        thinking = {'type': 'disabled'}
    if thinking:
        payload['thinking'] = thinking
    response = post('https://api.deepseek.com/chat/completions', headers={
        'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
    }, json=payload, timeout=90)
    response.raise_for_status()
    body = response.json()
    content = body.get('choices', [{}])[0].get('message', {}).get('content', '')
    result = parse_json_response(content)
    usage = body.get('usage') or {}
    return result, {
        'prompt_tokens': int(usage.get('prompt_tokens', 0) or 0),
        'completion_tokens': int(usage.get('completion_tokens', 0) or 0),
        'total_tokens': int(usage.get('total_tokens', 0) or 0),
        'prompt_cache_hit_tokens': int(usage.get('prompt_cache_hit_tokens', 0) or 0),
        'prompt_cache_miss_tokens': int(usage.get('prompt_cache_miss_tokens', 0) or 0),
    }, model


def request_gemini(prompt, model='gemini-3.5-flash', post=requests.post):
    global _GEMINI_EXHAUSTED_MODELS
    if model in _GEMINI_EXHAUSTED_MODELS:
        raise RuntimeError(f'Gemini model {model} daily free-tier quota already exhausted this process')
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        raise RuntimeError('Set GEMINI_API_KEY to run enrich-zh with Gemini')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.2,
            'responseMimeType': 'application/json',
            'maxOutputTokens': 2048,
        },
    }
    last_error = None
    for attempt in range(6):
        response = post(url, params={'key': key}, json=payload, timeout=90)
        if response.status_code == 429:
            detail = ''
            try:
                detail = str((response.json().get('error') or {}).get('message') or '')
            except Exception:
                detail = response.text[:300]
            last_error = RuntimeError(f'Gemini HTTP 429: {detail[:200]}')
            # Daily free-tier exhaustion cannot be fixed by short backoff.
            if 'per day' in detail.lower() or 'requests per day' in detail.lower() or ('retry in' in detail.lower() and 'h' in detail.lower()):
                _GEMINI_EXHAUSTED_MODELS.add(model)
                raise last_error
            time.sleep(min(60, 2 ** attempt))
            continue
        if response.status_code >= 500:
            last_error = RuntimeError(f'Gemini HTTP {response.status_code}')
            time.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        body = response.json()
        if body.get('error'):
            msg = str(body['error'])
            if 'RESOURCE_EXHAUSTED' in msg or '429' in msg:
                last_error = RuntimeError(msg)
                if 'per day' in msg.lower() or ('retry in' in msg.lower() and 'h' in msg.lower()):
                    raise last_error
                time.sleep(min(60, 2 ** attempt))
                continue
            raise RuntimeError(msg)
        parts = (((body.get('candidates') or [{}])[0].get('content') or {}).get('parts') or [])
        content = ''.join(part.get('text', '') for part in parts if isinstance(part, dict))
        result = parse_json_response(content)
        meta = body.get('usageMetadata') or {}
        prompt_tokens = int(meta.get('promptTokenCount', 0) or 0)
        completion_tokens = int(meta.get('candidatesTokenCount', 0) or 0)
        total_tokens = int(meta.get('totalTokenCount', 0) or (prompt_tokens + completion_tokens))
        return result, {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
        }, model
    raise last_error or RuntimeError('Gemini request failed')


def request_llm(prompt, provider='gemini', zh_cfg=None, post=requests.post):
    """Call preferred provider; on Gemini failure try fallback Gemini model, then DeepSeek."""
    zh_cfg = zh_cfg or load_zh_config()
    provider = (provider or zh_cfg.get('provider') or 'gemini').lower()
    gemini_model = zh_cfg.get('gemini_model') or 'gemini-3.5-flash'
    gemini_fallback = zh_cfg.get('gemini_fallback_model') or 'gemini-3.5-flash-lite'
    deepseek_model = zh_cfg.get('deepseek_model') or 'deepseek-chat'
    if provider == 'deepseek':
        result, usage, model = request_deepseek(prompt, model=deepseek_model, post=post)
        return result, usage, 'deepseek', model
    models = []
    for name in (gemini_model, gemini_fallback):
        if name and name not in models:
            models.append(name)
    last_error = None
    for model_name in models:
        try:
            result, usage, model = request_gemini(prompt, model=model_name, post=post)
            return result, usage, 'gemini', model
        except Exception as error:
            last_error = error
            print(f'Gemini model {model_name} failed ({type(error).__name__})', flush=True)
            continue
    print(f'Gemini failed persistently ({type(last_error).__name__ if last_error else "unknown"}); falling back to DeepSeek', flush=True)
    result, usage, model = request_deepseek(prompt, model=deepseek_model, post=post)
    usage = dict(usage)
    usage['fallback_from'] = f'gemini:{type(last_error).__name__ if last_error else "unknown"}'
    return result, usage, 'deepseek', model


def _entry(result, usage, cues, comments, provider, model, source_basis=None, youtube_units=1):
    valid_starts = [cue['start'] for cue in cues if cue.get('start') is not None]
    highlights = []
    for value in (result.get('highlights') or [])[:3]:
        if not isinstance(value, dict) or not str(value.get('text') or '').strip():
            continue
        item = {'text': str(value['text']).strip()[:30]}
        if valid_starts and isinstance(value.get('start'), (int, float)):
            item['start'] = float(value['start'])
        highlights.append(item)
    translated = []
    requested = {comment['original']: comment for comment in comments}
    for value in result.get('comments_zh') or []:
        if not isinstance(value, dict) or value.get('original') not in requested:
            continue
        original = value['original']
        translated.append({'original': original, 'text_zh': str(value.get('text_zh') or '').strip(),
                           'likes': requested[original]['likeCount']})
    description_present = source_basis or 'full'
    return {
        'title_zh': str(result.get('title_zh') or '').strip(),
        'blurb_zh': str(result.get('blurb_zh') or '').strip()[:40],
        'highlights': highlights, 'comments_zh': translated, 'has_transcript': bool(cues),
        'llm_provider': provider, 'llm_model': model,
        'llm_usage': usage, 'deepseek_usage': usage,
        'youtube_comment_units': youtube_units, 'updated_at': iso_now(),
        'source_basis': description_present,
    }


def _persist_zh_cache(cache_file, public_path, feed, existing, providers_used=None):
    def usage_of(entry):
        return entry.get('llm_usage') or entry.get('deepseek_usage') or {}
    all_entries = list(existing.values())
    providers_used = providers_used or {}
    cache = {'generated_at': iso_now(), 'feed': feed, 'videos': existing,
             'stats': {'processed': len(all_entries),
                       'with_transcript': sum(bool(x.get('has_transcript')) for x in all_entries),
                       'llm_tokens': sum(int(usage_of(x).get('total_tokens', 0) or 0) for x in all_entries),
                       'deepseek_tokens': sum(int(usage_of(x).get('total_tokens', 0) or 0) for x in all_entries),
                       'youtube_units': sum(int(x.get('youtube_comment_units', 0) or 0) for x in all_entries),
                       'providers': providers_used or dict(__import__('collections').Counter(x.get('llm_provider') for x in all_entries))}}
    cache_file = Path(cache_file)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(cache, ensure_ascii=False, indent=2) + '\n'
    cache_file.write_text(serialized, encoding='utf8')
    public = Path(public_path); public.parent.mkdir(parents=True, exist_ok=True); public.write_text(serialized, encoding='utf8')
    return cache



def _load_json_file(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf8'))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _pool_videos_by_id(pool_path):
    payload = _load_json_file(pool_path, {})
    videos = payload.get('videos') if isinstance(payload, dict) else None
    return {video['id']: video for video in videos or []
            if isinstance(video, dict) and video.get('id')}


def _topic_column_videos(topics_path, pool_path):
    """Return unique topic-column ids hydrated from the HN pool."""
    payload = _load_json_file(topics_path, {})
    pool_by_id = _pool_videos_by_id(pool_path)
    videos, seen = [], set()
    for topic in (payload.get('topics') if isinstance(payload, dict) else None) or []:
        if not isinstance(topic, dict):
            continue
        for video_id in topic.get('video_ids') or []:
            video_id = str(video_id or '').strip()
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            source = pool_by_id.get(video_id) or {}
            videos.append({'id': video_id,
                           'title': source.get('title') or '',
                           'description': source.get('description') or ''})
    return videos


def _normalize_videos(items, pool_path):
    """Accept explicit video dicts or ids, hydrating missing titles from the pool."""
    pool_by_id = _pool_videos_by_id(pool_path)
    videos, seen = [], set()
    for item in items or []:
        if isinstance(item, str):
            video_id = item.strip()
            source = pool_by_id.get(video_id) or {}
            video = {'id': video_id, 'title': source.get('title') or '',
                     'description': source.get('description') or ''}
        elif isinstance(item, dict) and item.get('id'):
            video_id = str(item['id'])
            source = pool_by_id.get(video_id) or {}
            video = {'id': video_id,
                     'title': item.get('title') or source.get('title') or '',
                     'description': item.get('description') or source.get('description') or ''}
        else:
            continue
        if not video['id'] or video['id'] in seen:
            continue
        seen.add(video['id'])
        videos.append(video)
    return videos


def _has_usable_zh(entry):
    return (isinstance(entry, dict)
            and bool(str(entry.get('title_zh') or '').strip())
            and bool(str(entry.get('blurb_zh') or '').strip()))


SUPPORTED_FEEDS = ('community', 'topics', 'visible', 'catalog', 'search', 'channels', 'all')
VISIBLE_FEED_FILES = (
    'picks.json', 'trending.json', 'ai.json', 'music.json', 'podcast.json',
    'videos.json', 'editorial.json', 'catalog.json',
)
FALLBACK_BLURB = '根据标题整理，未使用其他来源。'
PLACEHOLDER_BLURBS = ('精彩内容不容错过', '不容错过的精彩内容', '精彩内容，不容错过', '值得一看', '不容错过')
# Official deepseek-flash prices, CNY per 1M tokens (same as weekly_topics).
DEEPSEEK_CNY_PER_MILLION = {
    'input_hit_offpeak': 0.02,
    'input_miss_offpeak': 1.0,
    'output_offpeak': 4.0,
    'input_hit_peak': 0.04,
    'input_miss_peak': 2.0,
    'output_peak': 8.0,
}


def _deepseek_is_peak(now_dt=None):
    now_dt = now_dt or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    local = now_dt.astimezone(ZoneInfo('Asia/Shanghai'))
    if local.weekday() >= 5:
        return False
    minutes = local.hour * 60 + local.minute
    return (9 * 60 <= minutes < 12 * 60) or (14 * 60 <= minutes < 18 * 60)


def estimate_deepseek_cny(usage, now_dt=None):
    """Estimate CNY cost from a DeepSeek usage object; cache-miss if unsplit."""
    peak = _deepseek_is_peak(now_dt)
    suffix = 'peak' if peak else 'offpeak'
    rates = DEEPSEEK_CNY_PER_MILLION
    prompt = int((usage or {}).get('prompt_tokens', 0) or 0)
    completion = int((usage or {}).get('completion_tokens', 0) or 0)
    hit = int((usage or {}).get('prompt_cache_hit_tokens', 0) or 0)
    miss = (usage or {}).get('prompt_cache_miss_tokens')
    if miss is None or (int(miss or 0) == 0 and hit == 0 and prompt):
        miss = max(0, prompt - hit)
    else:
        miss = int(miss or 0)
    return (
        hit * rates[f'input_hit_{suffix}']
        + miss * rates[f'input_miss_{suffix}']
        + completion * rates[f'output_{suffix}']
    ) / 1_000_000


def build_light_prompt(title, description):
    """Title+description only: one Chinese title and a faithful one-sentence blurb."""
    return (
        'Return JSON only. Write Chinese metadata for this YouTube video for Chinese readers. '
        'Use only the title and description given. Do not invent facts, numbers, quotes, '
        'view counts, or quality judgments that are not supported by the provided text. '
        'If the description is missing or thin, write a short faithful paraphrase of the title; '
        'do not invent a plot or story. '
        'title_zh: a faithful Chinese title; '
        'blurb_zh: one sentence of at most 40 Chinese characters summarizing what the video is about.\n\n'
        f'Title: {title}\nDescription: {(description or "")[:1200]}\n'
        'Required shape: {"title_zh":"","blurb_zh":""}'
    )


def _is_placeholder_blurb(text):
    return str(text or '').strip() in PLACEHOLDER_BLURBS


def title_fallback_entry(title, usage=None):
    """Honest title-based Chinese fallback when the LLM fails; not a quality verdict."""
    return {
        'title_zh': str(title or '').strip(),
        'blurb_zh': FALLBACK_BLURB,
        'highlights': [],
        'comments_zh': [],
        'has_transcript': False,
        'llm_provider': 'fallback',
        'llm_model': 'title-only',
        'llm_usage': usage or {},
        'deepseek_usage': usage or {},
        'youtube_comment_units': 0,
        'source_basis': 'title-only',
        'updated_at': iso_now(),
    }


def _videos_from_payload(payload):
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict) and row.get('id')]
    if not isinstance(payload, dict):
        return []
    videos = payload.get('videos')
    if isinstance(videos, list):
        return [row for row in videos if isinstance(row, dict) and row.get('id')]
    return []


def _merge_meta(target, source):
    out = dict(target or {})
    if not isinstance(source, dict):
        return out
    vid = source.get('id') or out.get('id')
    if vid:
        out['id'] = vid
    if source.get('title') and not out.get('title'):
        out['title'] = source['title']
    incoming_desc = str(source.get('description') or '').strip()
    current_desc = str(out.get('description') or '').strip()
    if incoming_desc and len(incoming_desc) > len(current_desc):
        out['description'] = source['description']
    for key in ('channel', 'channel_id', 'published_at', 'duration_seconds'):
        if source.get(key) and not out.get(key):
            out[key] = source[key]
    return out


def _add_videos(by_id, items):
    for item in items or []:
        if not isinstance(item, dict) or not item.get('id'):
            continue
        video_id = str(item['id'])
        by_id[video_id] = _merge_meta(by_id.get(video_id) or {'id': video_id}, item)


def _channel_upload_videos(channels_payload, *, recent_limit=None):
    if isinstance(channels_payload, dict):
        channels = channels_payload.get('channels') or []
    elif isinstance(channels_payload, list):
        channels = channels_payload
    else:
        channels = []
    videos = []
    for channel in channels:
        if not isinstance(channel, dict):
            continue
        rows = [row for row in (channel.get('videos') or []) if isinstance(row, dict) and row.get('id')]
        if recent_limit is not None:
            rows = sorted(rows, key=lambda row: str(row.get('published_at') or ''), reverse=True)[:recent_limit]
        for row in rows:
            item = dict(row)
            item.setdefault('channel', channel.get('title') or channel.get('name') or '')
            item.setdefault('channel_id', channel.get('id') or row.get('channel_id'))
            videos.append(item)
    return videos


def load_inventory_videos(feed, *, data_root='site/src/data', topics_path=None,
                          pool_path=None, channels_path=None, recent_channel_limit=30):
    """Load unique videos for a named inventory, hydrating title/description when present."""
    if feed not in SUPPORTED_FEEDS:
        raise ValueError(f"feed must be one of {SUPPORTED_FEEDS}")
    root = Path(data_root)
    topics_path = topics_path or root / 'topics.json'
    pool_path = pool_path or root / 'hn_pool.json'
    channels_path = channels_path or root / 'channels.json'
    by_id = {}
    if feed == 'community':
        _add_videos(by_id, _videos_from_payload(_load_json_file(root / 'videos.json', {})))
    elif feed == 'topics':
        _add_videos(by_id, _topic_column_videos(topics_path, pool_path))
    elif feed == 'catalog':
        _add_videos(by_id, _videos_from_payload(_load_json_file(root / 'catalog.json', [])))
    else:
        if feed in ('visible', 'search', 'all'):
            for name in VISIBLE_FEED_FILES:
                fallback = [] if name == 'catalog.json' else {}
                _add_videos(by_id, _videos_from_payload(_load_json_file(root / name, fallback)))
            _add_videos(by_id, _topic_column_videos(topics_path, pool_path))
        if feed in ('search', 'channels', 'all'):
            payload = _load_json_file(channels_path, {})
            limit = recent_channel_limit if feed == 'search' else None
            _add_videos(by_id, _channel_upload_videos(payload, recent_limit=limit))
    return list(by_id.values())


def fetch_missing_descriptions(videos, client, key):
    """Fill empty descriptions via videos.list in 50-id batches (1 quota unit each)."""
    pending = [video for video in videos
               if video.get('id') and not str(video.get('description') or '').strip()]
    if not pending or client is None or not key:
        return 0
    units = 0
    by_id = {video['id']: video for video in videos}
    ids = [video['id'] for video in pending]
    for offset in range(0, len(ids), 50):
        batch = ids[offset:offset + 50]
        try:
            response = client.get(YOUTUBE_API + 'videos', {
                'part': 'snippet', 'id': ','.join(batch), 'key': key,
            }, youtube=True)
            units += 1
        except Exception as error:
            print(f'enrich-zh description fetch skipped: {type(error).__name__}: {error}', flush=True)
            continue
        for item in response.get('items') or []:
            video_id = item.get('id')
            snippet = (item or {}).get('snippet') or {}
            target = by_id.get(video_id)
            if not target:
                continue
            if snippet.get('title') and not target.get('title'):
                target['title'] = snippet['title']
            if snippet.get('description'):
                target['description'] = snippet['description']
    return units


def _safe_youtube_key():
    try:
        return youtube_key()
    except Exception:
        return None


def _resolve_mode(mode, feed, explicit):
    if mode in ('light', 'full'):
        return mode
    if feed == 'community' and not explicit:
        return 'full'
    return 'light'


def enrich_before_export(**kwargs):
    """Daily-refresh hook: enrich visible cards, never raise to the caller."""
    try:
        kwargs.setdefault('feed', 'visible')
        kwargs.setdefault('mode', 'light')
        kwargs.setdefault('provider', 'deepseek')
        return enrich_zh(None, **kwargs)
    except Exception as error:
        print(f'WARNING: zh enrichment skipped: {type(error).__name__}: {error}', flush=True)
        return {'attempted': 0, 'succeeded': 0, 'skipped': 0, 'tokens': 0,
                'units': 0, 'cost_cny': 0, 'failed': 0, 'fallbacks': 0,
                'error': f'{type(error).__name__}: {error}'}


def enrich_zh(db, *, feed='community', limit=None, force=False, provider=None,
              feed_path='site/src/data/videos.json', cache_path='site/src/data/zh.json',
              public_path='site/public/zh.json', videos=None, video_ids=None,
              topics_path='site/src/data/topics.json', pool_path='site/src/data/hn_pool.json',
              client=None, post=requests.post, config_path='config.yaml',
              mode=None, cost_cap_cny=None, data_root='site/src/data',
              channels_path='site/src/data/channels.json', quota_path='data/quota.json'):
    """Enrich videos with Chinese title_zh + blurb_zh, resuming from zh.json."""
    if feed not in SUPPORTED_FEEDS:
        raise ValueError(f"feed must be one of {SUPPORTED_FEEDS}")
    explicit = videos is not None or video_ids is not None
    resolved_mode = _resolve_mode(mode, feed, explicit)
    topic_like = feed != 'community' or explicit
    zh_cfg = load_zh_config(config_path)
    if topic_like or resolved_mode == 'light':
        preferred = (provider or zh_cfg.get('topic_provider') or 'deepseek').lower()
        llm_cfg = dict(zh_cfg)
        llm_cfg['deepseek_model'] = zh_cfg.get('topic_deepseek_model') or 'deepseek-flash'
    else:
        preferred = (provider or zh_cfg.get('provider') or 'gemini').lower()
        llm_cfg = zh_cfg

    data_root = Path(data_root)
    if str(topics_path) == 'site/src/data/topics.json':
        topics_path = data_root / 'topics.json'
    if str(pool_path) == 'site/src/data/hn_pool.json':
        pool_path = data_root / 'hn_pool.json'
    if str(channels_path) == 'site/src/data/channels.json':
        channels_path = data_root / 'channels.json'
    if str(feed_path) == 'site/src/data/videos.json' and data_root != Path('site/src/data'):
        feed_path = data_root / 'videos.json'

    if videos is not None:
        loaded = _normalize_videos(videos, pool_path)
    elif video_ids is not None:
        loaded = _normalize_videos(video_ids, pool_path)
    elif feed == 'community':
        loaded = json.loads(Path(feed_path).read_text(encoding='utf8')).get('videos', [])
    else:
        loaded = load_inventory_videos(
            feed, data_root=data_root, topics_path=topics_path,
            pool_path=pool_path, channels_path=channels_path,
        )

    cache_file = Path(cache_path)
    try:
        cache = json.loads(cache_file.read_text(encoding='utf8'))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    existing = cache.get('videos') if isinstance(cache.get('videos'), dict) else {}

    if topic_like or resolved_mode == 'light':
        pending_all = [video for video in loaded
                       if force or not _has_usable_zh(existing.get(video.get('id')))]
    else:
        pending_all = [video for video in loaded if force or video.get('id') not in existing]
    cached = len(loaded) - len(pending_all)
    pending = pending_all
    if limit is not None:
        pending = pending[:max(0, limit)]
    if not pending:
        public = Path(public_path)
        public.parent.mkdir(parents=True, exist_ok=True)
        public.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print(f'enrich-zh: transcripts 0/0, llm tokens 0, youtube units 0, skipped {len(loaded)}')
        return {'transcripts': 0, 'attempted': 0, 'succeeded': 0, 'tokens': 0,
                'units': 0, 'skipped': len(loaded), 'cached': len(loaded),
                'failed': 0, 'fallbacks': 0, 'providers': {}, 'missing_key': False,
                'source': feed, 'mode': resolved_mode, 'cost_cny': 0,
                'stopped_for_cap': False}

    if (topic_like or resolved_mode == 'light') and preferred == 'deepseek' and not os.environ.get('DEEPSEEK_API_KEY'):
        print('enrich-zh: skipped: DEEPSEEK_API_KEY not set', flush=True)
        return {'transcripts': 0, 'attempted': 0, 'succeeded': 0, 'tokens': 0,
                'units': 0, 'skipped': len(loaded),
                'cached': len(loaded) - len(pending), 'failed': 0, 'fallbacks': 0,
                'providers': {}, 'missing_key': True,
                'source': feed, 'mode': resolved_mode, 'cost_cny': 0,
                'stopped_for_cap': False}

    key = _safe_youtube_key()
    client = client or Client(interval=.05, db=db, quota_path=quota_path)
    done = transcripts = tokens = units = 0
    fallbacks = 0
    providers_used = {}
    cost_cny = 0.0
    stopped_for_cap = False
    processed = 0

    if resolved_mode == 'light':
        units += fetch_missing_descriptions(pending, client, key)
        reserve = 0.02
        for video in pending:
            if cost_cap_cny is not None and cost_cny + reserve > float(cost_cap_cny):
                stopped_for_cap = True
                print(f'enrich-zh stopped before cap: spent={cost_cny:.4f} cap={cost_cap_cny}', flush=True)
                break
            video_id = video.get('id')
            title = str(video.get('title') or '').strip()
            description = str(video.get('description') or '')
            source_basis = 'title+description' if description.strip() else 'title-only'
            prompt = build_light_prompt(title, description)
            try:
                result, usage, used_provider, used_model = request_llm(
                    prompt, provider=preferred, zh_cfg=llm_cfg, post=post)
                call_cost = estimate_deepseek_cny(usage)
                if cost_cap_cny is not None and cost_cny + call_cost > float(cost_cap_cny) + 1e-12:
                    # This call already happened; if it would clearly overrun, still
                    # keep a successful cheap result only when we pre-checked reserve.
                    # Stop further calls after recording it if we exceeded.
                    pass
                blurb = str(result.get('blurb_zh') or '').strip()[:40]
                title_zh = str(result.get('title_zh') or '').strip()
                if not title_zh or not blurb or _is_placeholder_blurb(blurb):
                    raise ValueError('empty or placeholder Chinese blurb')
                existing[video_id] = _entry(
                    result, usage, [], [], used_provider, used_model,
                    source_basis=source_basis, youtube_units=0,
                )
                done += 1
                tokens += int(usage.get('total_tokens', 0) or 0)
                cost_cny += call_cost
                providers_used[used_provider] = providers_used.get(used_provider, 0) + 1
                print(f"enrich-zh progress {done}/{len(pending)} id={video_id} provider={used_provider} "
                      f"tokens={usage.get('total_tokens', 0)} cost_cny={cost_cny:.4f}", flush=True)
            except Exception as error:
                print(f"enrich-zh fallback {video_id}: {type(error).__name__}: {error}", flush=True)
                existing[video_id] = title_fallback_entry(title)
                fallbacks += 1
            processed += 1
            _persist_zh_cache(cache_file, public_path, feed, existing, providers_used)
            if cost_cap_cny is not None and cost_cny >= float(cost_cap_cny):
                stopped_for_cap = True
                print(f'enrich-zh reached cap: spent={cost_cny:.4f} cap={cost_cap_cny}', flush=True)
                break
    else:
        INTER_CALL_SLEEP = 3.0
        for index, video in enumerate(pending):
            try:
                if index and preferred == 'gemini':
                    time.sleep(INTER_CALL_SLEEP)
                video_id = video.get('id')
                cues = fetch_transcript(video_id)
                if topic_like:
                    title, description = _topic_video_context(db, client, video, key)
                else:
                    title, description = _video_context(db, client, video, key)
                try:
                    comments = top_comments(client, video_id, key)
                    units += 1
                except Exception:
                    comments = []
                    units += 1
                prompt = build_prompt(title, description, truncate_transcript(cues), comments, bool(cues))
                result, usage, used_provider, used_model = request_llm(
                    prompt, provider=preferred, zh_cfg=llm_cfg, post=post)
                existing[video_id] = _entry(result, usage, cues, comments, used_provider, used_model)
                done += 1
                transcripts += bool(cues)
                tokens += usage['total_tokens']
                providers_used[used_provider] = providers_used.get(used_provider, 0) + 1
                _persist_zh_cache(cache_file, public_path,
                                  'topics' if topic_like else 'community',
                                  existing, providers_used)
                print(f"enrich-zh progress {done}/{len(pending)} id={video_id} provider={used_provider} tokens={usage['total_tokens']}", flush=True)
            except Exception as error:
                print(f"enrich-zh skipped {video.get('id', '')}: {type(error).__name__}: {error}", flush=True)
                processed += 1
            else:
                processed += 1

    _persist_zh_cache(cache_file, public_path, feed, existing, providers_used)
    leftover = len(pending) - processed
    failed = leftover  # unprocessed remain without a new entry
    skipped = cached + failed
    summary = {'transcripts': transcripts, 'attempted': len(pending), 'succeeded': done,
               'tokens': tokens, 'units': units, 'skipped': skipped,
               'cached': cached, 'failed': failed, 'fallbacks': fallbacks,
               'providers': providers_used, 'missing_key': False,
               'source': feed, 'mode': resolved_mode, 'cost_cny': round(cost_cny, 6),
               'stopped_for_cap': stopped_for_cap, 'unprocessed': leftover}
    print(f"enrich-zh: mode={resolved_mode} transcripts {transcripts}/{processed}, llm tokens {tokens}, "
          f"youtube units {units}, cost_cny {cost_cny:.4f}, providers {providers_used}, "
          f"succeeded {done}, fallbacks {fallbacks}, skipped {skipped} "
          f"(cached {cached}, unprocessed {leftover})")
    return summary


def ab_compare(db, video_ids, *, out_path='reports/zh_ab.md', feed_path='site/src/data/videos.json',
               client=None, post=requests.post, config_path='config.yaml'):
    """Generate Gemini and DeepSeek outputs with the identical prompt for A/B review."""
    zh_cfg = load_zh_config(config_path)
    videos = {v['id']: v for v in json.loads(Path(feed_path).read_text(encoding='utf8')).get('videos', [])}
    key = youtube_key()
    client = client or Client(interval=.05, db=db)
    rows = []
    for video_id in video_ids:
        video = videos[video_id]
        cues = fetch_transcript(video_id)
        title, description = _video_context(db, client, video, key)
        try:
            comments = top_comments(client, video_id, key)
        except Exception as error:
            comments = []
            print(f'ab comments failed {video_id}: {type(error).__name__}')
        transcript = truncate_transcript(cues)
        prompt = build_prompt(title, description, transcript, comments, bool(cues))
        gemini = deepseek = None
        gemini_err = deepseek_err = None
        try:
            result, usage, model = request_gemini(prompt, model=zh_cfg['gemini_model'], post=post)
            gemini = _entry(result, usage, cues, comments, 'gemini', model)
        except Exception as error:
            gemini_err = f'{type(error).__name__}: {error}'
        try:
            result, usage, model = request_deepseek(prompt, model=zh_cfg['deepseek_model'], post=post)
            deepseek = _entry(result, usage, cues, comments, 'deepseek', model)
        except Exception as error:
            deepseek_err = f'{type(error).__name__}: {error}'
        rows.append({
            'id': video_id, 'title': title, 'has_transcript': bool(cues), 'comments': comments,
            'prompt_chars': len(prompt), 'gemini': gemini, 'deepseek': deepseek,
            'gemini_err': gemini_err, 'deepseek_err': deepseek_err,
        })
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(_render_ab_markdown(rows, zh_cfg), encoding='utf8')
    return rows


def _fmt_highlights(items):
    if not items:
        return '_（无）_'
    lines = []
    for item in items:
        start = item.get('start')
        stamp = f" @{int(start)//60}:{int(start)%60:02d}" if isinstance(start, (int, float)) else ''
        lines.append(f"- {item.get('text', '')}{stamp}")
    return '\n'.join(lines)


def _fmt_comments(items):
    if not items:
        return '_（无）_'
    blocks = []
    for item in items:
        blocks.append(
            f"- 译：{item.get('text_zh', '')}\n"
            f"  原：{item.get('original', '')}\n"
            f"  赞：{item.get('likes', 0)}"
        )
    return '\n'.join(blocks)


def _fmt_side(entry, err):
    if err:
        return f'_Error: {err}_'
    if not entry:
        return '_（无输出）_'
    usage = entry.get('llm_usage') or {}
    return (
        f"**Model:** `{entry.get('llm_provider')}/{entry.get('llm_model')}`  \n"
        f"**Tokens:** prompt={usage.get('prompt_tokens', 0)}, "
        f"completion={usage.get('completion_tokens', 0)}, total={usage.get('total_tokens', 0)}\n\n"
        f"**中文标题:** {entry.get('title_zh', '')}\n\n"
        f"**一句话推荐:** {entry.get('blurb_zh', '')}\n\n"
        f"**看点:**\n{_fmt_highlights(entry.get('highlights'))}\n\n"
        f"**评论翻译:**\n{_fmt_comments(entry.get('comments_zh'))}"
    )


def _render_ab_markdown(rows, zh_cfg):
    lines = [
        '# 中文增值 A/B：Gemini vs DeepSeek',
        '',
        f"- Generated at: {iso_now()}",
        f"- Gemini model: `{zh_cfg.get('gemini_model')}`",
        f"- DeepSeek model: `{zh_cfg.get('deepseek_model')}`",
        f"- Identical prompt+inputs per video (transcript truncated, top-3 comments by likes).",
        f"- Videos: {len(rows)}",
        '',
    ]
    for index, row in enumerate(rows, 1):
        lines += [
            f"## {index}. {row['title']}",
            '',
            f"- Video id: `{row['id']}`",
            f"- Has transcript: {row['has_transcript']}",
            f"- Prompt chars: {row['prompt_chars']}",
            f"- Source comments fetched: {len(row['comments'])}",
            '',
            '### Gemini',
            '',
            _fmt_side(row['gemini'], row['gemini_err']),
            '',
            '### DeepSeek',
            '',
            _fmt_side(row['deepseek'], row['deepseek_err']),
            '',
        ]
    return '\n'.join(lines) + '\n'
