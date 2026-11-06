"""Chinese value-add enrichment for the community video feed.

This module deliberately keeps external calls behind small functions so the
pipeline can be exercised with mocks and resumed safely from ``zh.json``.
"""
import json
import os
import re
import time
from pathlib import Path

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


def request_deepseek(prompt, model='deepseek-chat', post=requests.post):
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        raise RuntimeError('Set DEEPSEEK_API_KEY to run enrich-zh')
    payload = {
        'model': model, 'temperature': 0.2, 'response_format': {'type': 'json_object'},
        'messages': [{'role': 'user', 'content': prompt}],
    }
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


def _entry(result, usage, cues, comments, provider, model):
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
    return {
        'title_zh': str(result.get('title_zh') or '').strip(),
        'blurb_zh': str(result.get('blurb_zh') or '').strip()[:40],
        'highlights': highlights, 'comments_zh': translated, 'has_transcript': bool(cues),
        'llm_provider': provider, 'llm_model': model,
        'llm_usage': usage, 'deepseek_usage': usage,
        'youtube_comment_units': 1, 'updated_at': iso_now(),
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



def enrich_zh(db, *, feed='community', limit=None, force=False, provider=None,
              feed_path='site/src/data/videos.json', cache_path='site/src/data/zh.json',
              public_path='site/public/zh.json', client=None, post=requests.post, config_path='config.yaml'):
    if feed != 'community':
        raise ValueError('Only the community feed is supported by enrich-zh')
    zh_cfg = load_zh_config(config_path)
    preferred = (provider or zh_cfg.get('provider') or 'gemini').lower()
    videos = json.loads(Path(feed_path).read_text(encoding='utf8')).get('videos', [])
    cache_file = Path(cache_path)
    try:
        cache = json.loads(cache_file.read_text(encoding='utf8'))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    existing = cache.get('videos') if isinstance(cache.get('videos'), dict) else {}
    pending = [video for video in videos if force or video.get('id') not in existing]
    if limit is not None:
        pending = pending[:max(0, limit)]
    if not pending:
        public = Path(public_path)
        public.parent.mkdir(parents=True, exist_ok=True)
        public.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print(f'enrich-zh: transcripts 0/0, llm tokens 0, youtube units 0, skipped {len(videos)}')
        return {'transcripts': 0, 'attempted': 0, 'tokens': 0, 'units': 0, 'skipped': len(videos)}
    key = youtube_key()
    client = client or Client(interval=.05, db=db)
    done = transcripts = tokens = units = 0
    providers_used = {}
    INTER_CALL_SLEEP = 3.0  # free-tier pacing between Gemini calls
    for index, video in enumerate(pending):
        try:
            if index and preferred == 'gemini':
                time.sleep(INTER_CALL_SLEEP)
            cues = fetch_transcript(video['id'])
            title, description = _video_context(db, client, video, key)
            try:
                comments = top_comments(client, video['id'], key)
                units += 1
            except Exception:
                comments = []
                units += 1
            prompt = build_prompt(title, description, truncate_transcript(cues), comments, bool(cues))
            result, usage, used_provider, used_model = request_llm(prompt, provider=preferred, zh_cfg=zh_cfg, post=post)
            existing[video['id']] = _entry(result, usage, cues, comments, used_provider, used_model)
            done += 1
            transcripts += bool(cues)
            tokens += usage['total_tokens']
            providers_used[used_provider] = providers_used.get(used_provider, 0) + 1
            _persist_zh_cache(cache_file, public_path, feed, existing, providers_used)
            print(f"enrich-zh progress {done}/{len(pending)} id={video.get('id')} provider={used_provider} tokens={usage['total_tokens']}", flush=True)
        except Exception as error:
            print(f"enrich-zh skipped {video.get('id', '')}: {type(error).__name__}: {error}", flush=True)
    all_entries = list(existing.values())

    def usage_of(entry):
        return entry.get('llm_usage') or entry.get('deepseek_usage') or {}

    cache = _persist_zh_cache(cache_file, public_path, feed, existing, providers_used)
    serialized = json.dumps(cache, ensure_ascii=False, indent=2) + '\n'
    summary = {'transcripts': transcripts, 'attempted': len(pending), 'tokens': tokens, 'units': units,
               'skipped': len(videos) - len(pending), 'providers': providers_used}
    print(f"enrich-zh: transcripts {transcripts}/{len(pending)}, llm tokens {tokens}, youtube units {units}, "
          f"providers {providers_used}, skipped {summary['skipped']}")
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
