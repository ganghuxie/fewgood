"""Bounded, reproducible Fewgood MVP experiment; never touches production quota."""
import argparse
import hashlib
import json
import os
import re
import time
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yaml

from .core import duration, landscape_video

ROOT = Path(__file__).resolve().parents[1]
API = 'https://www.googleapis.com/youtube/v3/'
RAW = ROOT / 'data/experiments/fewgood-mvp-raw.json'
RESULT = ROOT / 'data/experiments/fewgood-mvp-result.json'
DEMO = ROOT / 'site/src/data/fewgood-mvp.json'
USAGE = ROOT / 'data/experiments/fewgood-mvp-usage.json'


def iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def config():
    return yaml.safe_load((ROOT / 'config/fewgood_topics.yaml').read_text())


def clean(s):
    return re.sub(r'[^\w\s]', ' ', str(s or '').lower(), flags=re.UNICODE)


def hit(text, term):
    return bool(re.search(r'(?<!\w)' + re.escape(str(term).lower()) + r'(?!\w)', str(text).lower()))


def titlekey(s):
    return ' '.join(clean(s).split())


def usage_empty():
    return {'calls': [], 'search_calls': 0, 'other_units': 0, 'old_model_units': 0, 'aborted_reason': None}


class Fetcher:
    def __init__(self, cfg, key, usage=None, get=None):
        self.cfg, self.key = cfg, key
        self.usage, self.get = usage or usage_empty(), get or requests.get
        self.stopped = False

    def call(self, endpoint, params, purpose):
        if self.stopped:
            raise RuntimeError('YouTube requests stopped')
        search = endpoint == 'search'
        cap = self.cfg['search_call_cap'] if search else self.cfg['other_unit_cap']
        counter = 'search_calls' if search else 'other_units'
        if self.usage[counter] >= cap:
            raise RuntimeError(f'{endpoint} call cap reached before request')
        params = {**params, 'key': self.key}
        attempts = 0
        while True:
            if self.usage[counter] >= cap:
                raise RuntimeError(f'{endpoint} call cap reached before request')
            try:
                response = self.get(API + endpoint, params=params, timeout=30)
                status, payload = response.status_code, response.json()
            except Exception:
                status, payload = 0, {}
            self.usage[counter] += 1
            self.usage['old_model_units'] += 100 if search else 1
            self.usage['calls'].append({'endpoint': endpoint, 'purpose': purpose, 'timestamp': iso(),
                                        'http_status': status, 'returned': len(payload.get('items', []))})
            if status == 403 and 'quotaExceeded' in json.dumps(payload):
                self.stopped, self.usage['aborted_reason'] = True, '403 quotaExceeded'
                return payload
            if (status == 429 or status >= 500) and attempts < 1:
                attempts += 1
                continue
            return payload


def existing_pool():
    """Read existing public data but do not consider it detailed YouTube metadata."""
    rows = []
    for name in ('ai', 'videos', 'trending', 'podcast', 'catalog'):
        path = ROOT / f'site/src/data/{name}.json'
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            videos = data.get('videos', []) if isinstance(data, dict) else data
        except Exception:
            continue
        for video in videos:
            if isinstance(video, dict) and video.get('id') and video.get('title'):
                rows.append({'id': video['id'], 'snippet': {
                    'title': video.get('title', ''), 'channelTitle': video.get('channel', ''),
                    'channelId': video.get('channel_id', ''), 'publishedAt': video.get('published_at', ''),
                }, 'sources': [f'existing:{name}.json']})
    return rows


def pool_relevant(rows, cfg):
    """AI page is explicitly curated; other old rows need a title keyword before detail lookup."""
    terms = [term for topic in cfg['topics'] for group in ('strong', 'weak')
             for term in topic['include_terms'][group]]
    selected = []
    for row in rows:
        if 'existing:ai.json' in row.get('sources', []) or any(hit(row.get('snippet', {}).get('title', ''), x) for x in terms):
            selected.append(row)
    return selected


def compact(raw):
    return {'id': raw.get('id'), 'snippet': raw.get('snippet', {}),
            'contentDetails': raw.get('contentDetails', {}), 'statistics': raw.get('statistics', {}),
            'status': raw.get('status', {}), 'player': raw.get('player', {}),
            'sources': raw.get('sources', [])}


def snippet_score(row):
    snippet = row.get('snippet', {})
    return sum(bool(snippet.get(k)) for k in ('description', 'tags', 'thumbnails')) + bool(snippet.get('title'))


def merge(rows):
    merged = {}
    for row in rows:
        if not row.get('id'):
            continue
        row = compact(row)
        old = merged.get(row['id'])
        if old is None:
            merged[row['id']] = row
            continue
        sources = list(dict.fromkeys(old.get('sources', []) + row.get('sources', [])))
        # Search/playlist snippets are less complete than videos.list snippets.
        winner = row if snippet_score(row) > snippet_score(old) else old
        winner['sources'] = sources
        merged[row['id']] = winner
    return list(merged.values())


def parse_time(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def similar_title(a, b):
    a, b = set(titlekey(a).split()), set(titlekey(b).split())
    return bool(a and b and (a == b or len(a & b) / len(a | b) >= .8))


def title_dedup(rows):
    kept, pairs = [], []
    for row in rows:
        same = next((item for item in kept if similar_title(row.get('snippet', {}).get('title', ''), item.get('snippet', {}).get('title', ''))), None)
        if not same:
            kept.append(row)
            continue
        views = lambda x: int(x.get('statistics', {}).get('viewCount', 0) or 0)
        winner, loser = (row, same) if views(row) > views(same) else (same, row)
        winner['sources'] = list(dict.fromkeys(winner.get('sources', []) + loser.get('sources', [])))
        if loser is same:
            kept.remove(same)
            kept.append(winner)
        pairs.append({'kept': winner['id'], 'removed': loser['id'], 'title': winner.get('snippet', {}).get('title', '')})
    return kept, pairs


def topic_match(row, topic):
    snippet = row.get('snippet', {})
    title = snippet.get('title', '')
    other = ' '.join([snippet.get('description', '')[:500], ' '.join(snippet.get('tags', []))])
    strong_title = next((x for x in topic['include_terms']['strong'] if hit(title, x)), None)
    # Standalone product names in boilerplate descriptions are too broad to
    # promote a video into AI products.  Keep them as configured title rules;
    # this also leaves a description-only "Claude" as the models tier-3
    # diagnostic rather than a displayable product match.
    other_strong = [x for x in topic['include_terms']['strong']
                    if x not in topic['include_terms'].get('title_only_strong', [])]
    strong_other = next((x for x in other_strong if hit(other, x)), None)
    weak_title = next((x for x in topic['include_terms']['weak'] if hit(title, x)), None)
    weak_other = next((x for x in topic['include_terms']['weak'] if hit(other, x)), None)
    if strong_title:
        return 1, strong_title, '标题'
    if strong_other or weak_title:
        return 2, strong_other or weak_title, '标签或说明' if strong_other else '标题'
    if weak_other:
        return 3, weak_other, '标签或说明'
    return None


def basic_failure(row, topic, now, check_published_within=True):
    snippet = row.get('snippet', {})
    text = ' '.join([snippet.get('title', ''), snippet.get('description', '')[:500], ' '.join(snippet.get('tags', []))])
    excluded = next((x for x in topic['exclude_terms'] if hit(text, x)), None)
    if excluded:
        return 'exclude:' + excluded
    if row.get('status', {}).get('privacyStatus') not in (None, 'public'):
        return 'not_public'
    if snippet.get('liveBroadcastContent') in ('live', 'upcoming'):
        return 'live_or_upcoming'
    seconds = duration(row.get('contentDetails', {}).get('duration', '')) or row.get('contentDetails', {}).get('duration_seconds') or 0
    if seconds < 60 or seconds < topic['min_duration_seconds'] or seconds > topic['max_duration_seconds']:
        return 'duration'
    player = row.get('player') or {}
    if ('embedWidth' in player and 'embedHeight' in player) and not landscape_video(row):
        return 'vertical'
    if check_published_within and parse_time(snippet.get('publishedAt', '')) < now - timedelta(days=topic['published_within_days']):
        return 'too_old'
    return None


def source_label(source):
    if source.startswith('channel_uploads:'):
        return '频道上传'
    if source.startswith('search:'):
        return '搜索「' + source.split(':', 2)[-1] + '」'
    if source.startswith('existing:'):
        return '已有数据 ' + source.split(':', 1)[1]
    return source


def select(raw, mode='select', usage=None):
    started = time.monotonic()
    cfg, now = config(), datetime.now(timezone.utc)
    usage = usage or raw.get('usage_summary', usage_empty())
    merged = merge(raw.get('candidates', []))
    kept, duplicate_pairs = title_dedup(merged)
    pool = dict(raw.get('pool_stats', {}))
    pool.update({'merged_unique': len(merged), 'after_title_dedup': len(kept),
                 'duplicates_removed': len(duplicate_pairs), 'duplicate_pairs': duplicate_pairs})
    assignments, matches = {}, {}
    for row in kept:
        found = [(index, topic, topic_match(row, topic)) for index, topic in enumerate(cfg['topics'])]
        found = [(index, topic, result) for index, topic, result in found if result]
        matches[row['id']] = found
        if found:
            # Tier first, configuration order provides stable tie breaking.
            assignments[row['id']] = min(found, key=lambda x: (x[2][0], x[0]))
    topics = []
    for index, topic in enumerate(cfg['topics']):
        allocated = [(row, assignments[row['id']][2]) for row in kept
                     if row['id'] in assignments and assignments[row['id']][0] == index]
        # Matching statistics describe every textual hit for this topic, while
        # ``allocated`` below still guarantees a video is displayed under only
        # its single best topic.  This preserves the useful tier-3 diagnostic
        # when, for example, a description mentions Claude (AI models) but the
        # stronger product-name match assigns the video to AI products.
        tiers = {n: sum(1 for row in kept
                        for match_topic_index, _, match in matches.get(row['id'], [])
                        if match_topic_index == index and match[0] == n)
                 for n in (1, 2, 3)}
        excluded = {}
        # This is intentionally based on textual matches, not every pool row: an
        # unrelated cooking video must not inflate a topic's "too_old" count.
        for row in kept:
            if any(match_topic_index == index for match_topic_index, _, _ in matches.get(row['id'], [])):
                failure = basic_failure(row, topic, now)
                if failure:
                    excluded[failure] = excluded.get(failure, 0) + 1
        eligible = []
        for row, match in allocated:
            failure = basic_failure(row, topic, now)
            if not failure and match[0] in (1, 2):
                eligible.append((row, match))
        trusted = {channel['youtube_channel_id']: channel['name'] for channel in topic['trusted_channels']}
        eligible.sort(key=lambda item: (item[1][0], -(item[0].get('snippet', {}).get('channelId', '') in trusted),
                                        -len(item[0].get('sources', [])), -parse_time(item[0].get('snippet', {}).get('publishedAt', '')).timestamp(), item[0]['id']))
        shown, shown_channels, eligible_channels = [], {}, {}
        for row, match in eligible:
            channel = row.get('snippet', {}).get('channelTitle', '')
            eligible_channels[channel] = eligible_channels.get(channel, 0) + 1
            if shown_channels.get(channel, 0) >= cfg['max_per_channel_in_top']:
                continue
            shown_channels[channel] = shown_channels.get(channel, 0) + 1
            snippet = row.get('snippet', {})
            seconds = duration(row.get('contentDetails', {}).get('duration', '')) or row.get('contentDetails', {}).get('duration_seconds') or 0
            published = parse_time(snippet.get('publishedAt', ''))
            day_count = max(0, (now.date() - published.date()).days)
            reason = f'{match[2]}含关键词「{match[1]}」'
            reasons = [reason]
            other_names = [other['name_zh'] for other_index, other, _ in matches[row['id']] if other_index != index]
            if other_names:
                reasons.append('也匹配：' + '、'.join(other_names))
            if snippet.get('channelId') in trusted:
                reasons.append('来自可信频道：' + trusted[snippet['channelId']])
            reasons += [f'发布于 {snippet.get("publishedAt", "")[:10]}（{day_count} 天前）',
                        f'时长 {seconds // 60}:{seconds % 60:02d}，非 Shorts',
                        '被 ' + str(len(row.get('sources', []))) + ' 个来源发现：' + ' / '.join(source_label(x) for x in row.get('sources', []))]
            shown.append({'video_id': row['id'], 'title': snippet.get('title', ''), 'channel_title': channel,
                          'channel_id': snippet.get('channelId'), 'published_at': snippet.get('publishedAt'),
                          'duration_seconds': seconds, 'view_count': int(row.get('statistics', {}).get('viewCount', 0)) if row.get('statistics', {}).get('viewCount') is not None else None,
                          'topic': topic['id'], 'sources': row.get('sources', []), 'reasons': reasons,
                          'url': 'https://www.youtube.com/watch?v=' + row['id'],
                          'thumbnail': (snippet.get('thumbnails', {}).get('medium', {}) or snippet.get('thumbnails', {}).get('default', {})).get('url')})
            if len(shown) >= cfg['top_n']:
                break
        searches = [call for call in usage.get('calls', []) if call.get('endpoint') == 'search' and call.get('purpose', '').startswith('topic:' + topic['id'] + ':')]
        duplicate_count = sum(1 for pair in duplicate_pairs if any(row['id'] == pair['removed'] for row, _ in allocated))
        topics.append({'id': topic['id'], 'name_zh': topic['name_zh'], 'definition': topic['definition'],
                       'stats': {'searches': len(searches), 'baseline_searches': sum(1 for call in usage.get('calls', []) if call.get('purpose') == 'baseline:' + topic['id']),
                                 'topic_search_results': sum(call.get('returned', 0) for call in searches),
                                 'matched': sum(tiers.values()), 'matched_tier1': tiers[1], 'matched_tier2': tiers[2], 'matched_tier3': tiers[3],
                                 'eligible': len(eligible), 'shown': len(shown), 'channel_distribution_shown': shown_channels,
                                 'channel_distribution_eligible': eligible_channels, 'excluded_by_rule': excluded,
                                 'duplicates_in_topic': duplicate_count}, 'videos': shown})
    baseline = {}
    for topic_id, values in raw.get('baseline', {}).items():
        baseline[topic_id] = []
        for rank, row in enumerate(values[:6], 1):
            snippet = row.get('snippet', {})
            baseline[topic_id].append({'rank': rank, 'video_id': row['id'], 'title': snippet.get('title', ''),
                'channel_title': snippet.get('channelTitle', ''), 'published_at': snippet.get('publishedAt'),
                'duration_seconds': duration(row.get('contentDetails', {}).get('duration', '')) or row.get('contentDetails', {}).get('duration_seconds'),
                'view_count': int(row.get('statistics', {}).get('viewCount', 0)) if row.get('statistics', {}).get('viewCount') is not None else None,
                'url': 'https://www.youtube.com/watch?v=' + row['id'], 'also_in_fewgood_topN': any(row['id'] == video['video_id'] for topic in topics for video in topic['videos'])})
    pool['fetched_details'] = pool.get('fetched_details', len(kept))
    pool['missing_details'] = pool.get('missing_details', 0)
    digest = hashlib.sha256((ROOT / 'config/fewgood_topics.yaml').read_bytes()).hexdigest()
    return {'generated_at': iso(), 'data_refreshed_at': raw.get('data_refreshed_at', iso()), 'mode': mode,
            'config_digest': digest, 'usage_summary': usage, 'pool_stats': pool,
            'timing': {'collect_seconds': raw.get('timing', {}).get('collect_seconds', 0), 'select_seconds': round(time.monotonic() - started, 6)},
            'rules_notes': ['竖屏判断：videos.list 未返回 embedWidth/embedHeight 时不按方向排除，依靠最短 4 分钟时长排除 Shorts'],
            'topics': topics, 'baseline': baseline}


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def paths(output_dir=None):
    if not output_dir:
        return RAW, RESULT, DEMO, USAGE
    base = Path(output_dir)
    return base / 'fewgood-mvp-raw.json', base / 'fewgood-mvp-result.json', base / 'fewgood-mvp.json', base / 'fewgood-mvp-usage.json'


def run(args):
    cfg, key = config(), os.environ.get('YOUTUBE_API_KEY')
    if not args.dry_run and not key:
        raise RuntimeError('YOUTUBE_API_KEY is required (credential is never printed)')
    query_count = min(args.queries_per_topic, 2)
    baseline_ids = args.baseline_topics.split(',') if args.baseline_topics else [topic['id'] for topic in cfg['topics']]
    ordered = [topic for topic in cfg['topics'] if topic['id'] in baseline_ids]
    plan = [('search', 'baseline:' + topic['id']) for topic in ordered]
    plan += [('search', 'topic:' + topic['id'] + ':' + query) for topic in cfg['topics'] for query in topic['queries'][:query_count]]
    channels = yaml.safe_load((ROOT / 'config/ai_channels.yaml').read_text()).get('channels', [])
    plan += [('playlistItems', 'channel_uploads:' + channel['name']) for channel in channels]
    if len([x for x in plan if x[0] == 'search']) > cfg['search_call_cap']:
        raise RuntimeError('planned search calls exceed search_call_cap')
    if args.dry_run:
        # Conservative bound: every channel page and search result is distinct.
        old_selected = len(pool_relevant(existing_pool(), cfg))
        maximum_detail_ids = old_selected + len(ordered) * 6 + len(cfg['topics']) * query_count * 25 + len(channels) * 50
        other_estimate = len(channels) + math.ceil(maximum_detail_ids / 50)
        print(json.dumps({'calls': plan, 'search_calls': sum(x[0] == 'search' for x in plan),
                          'other_units_estimate': other_estimate,
                          'old_model_units_estimate': sum(100 if x[0] == 'search' else 1 for x in plan) + other_estimate}, ensure_ascii=False))
        return
    started, fetcher = time.monotonic(), Fetcher(cfg, key)
    pool_all = existing_pool()
    candidates, baseline, base_ids = pool_relevant(pool_all, cfg), {}, []
    pool_stats = {'existing_pool_raw': len(pool_all), 'existing_pool_selected': len(candidates), 'channel_upload_raw': 0, 'search_raw': 0,
                  'merged_unique': 0, 'after_title_dedup': 0, 'fetched_details': 0, 'missing_details': 0, 'duplicates_removed': 0, 'duplicate_pairs': []}
    try:
        for topic in ordered:
            response = fetcher.call('search', {'part': 'snippet', 'type': 'video', 'q': topic['baseline_query'], 'maxResults': 10}, 'baseline:' + topic['id'])
            ids = [item.get('id', {}).get('videoId') for item in response.get('items', []) if item.get('id', {}).get('videoId')]
            baseline[topic['id']] = [{'id': video_id, 'sources': ['baseline:' + topic['id']]} for video_id in ids[:6]]
            base_ids += ids[:6]
        for topic in cfg['topics']:
            for query in topic['queries'][:query_count]:
                response = fetcher.call('search', {'part': 'snippet', 'type': 'video', 'order': 'relevance', 'publishedAfter': (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace('+00:00', 'Z'), 'maxResults': 25, 'relevanceLanguage': 'en', 'safeSearch': 'moderate', 'q': query}, 'topic:' + topic['id'] + ':' + query)
                found = [{'id': item.get('id', {}).get('videoId'), 'snippet': item.get('snippet', {}), 'sources': ['search:' + query]} for item in response.get('items', []) if item.get('id', {}).get('videoId')]
                candidates += found
                pool_stats['search_raw'] += len(found)
        for channel in channels:
            playlist = 'UU' + channel['youtube_channel_id'][2:]
            response = fetcher.call('playlistItems', {'part': 'snippet,contentDetails', 'playlistId': playlist, 'maxResults': 50}, 'channel_uploads:' + channel['name'])
            for item in response.get('items', []):
                snippet, video_id = item.get('snippet', {}), item.get('contentDetails', {}).get('videoId') or item.get('snippet', {}).get('resourceId', {}).get('videoId')
                if video_id and parse_time(item.get('contentDetails', {}).get('videoPublishedAt') or snippet.get('publishedAt', '')) >= datetime.now(timezone.utc) - timedelta(days=30):
                    candidates.append({'id': video_id, 'snippet': snippet, 'sources': ['channel_uploads:' + channel['name']]})
                    pool_stats['channel_upload_raw'] += 1
        ids = list(dict.fromkeys([row['id'] for row in candidates if row.get('id')] + base_ids))
        details = {}
        for offset in range(0, len(ids), 50):
            response = fetcher.call('videos', {'part': 'snippet,contentDetails,statistics,status,player', 'id': ','.join(ids[offset:offset + 50])}, 'details')
            details.update({item['id']: item for item in response.get('items', [])})
        pool_stats['fetched_details'], pool_stats['missing_details'] = len(details), len(ids) - len(details)
        def detailed(rows):
            return [dict(details[row['id']], sources=row.get('sources', [])) for row in rows if row.get('id') in details]
        candidates, baseline = detailed(candidates), {topic_id: detailed(rows) for topic_id, rows in baseline.items()}
    except RuntimeError as error:
        fetcher.usage['aborted_reason'] = str(error)
    raw_path, result_path, demo_path, usage_path = paths(args.output_dir)
    raw = {'data_refreshed_at': iso(), 'candidates': candidates, 'baseline': baseline, 'usage_summary': fetcher.usage,
           'pool_stats': pool_stats, 'timing': {'collect_seconds': round(time.monotonic() - started, 6)}}
    write_json(raw_path, raw)
    write_json(usage_path, fetcher.usage)
    result = select(raw, 'run', fetcher.usage)
    write_json(result_path, result)
    write_json(demo_path, result)
    for topic in result['topics']:
        print(f"{topic['id']}: {topic['stats']['shown']}/{topic['stats']['eligible']}")
    print(json.dumps({key: fetcher.usage[key] for key in ('search_calls', 'other_units', 'old_model_units', 'aborted_reason')}, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('cmd', choices=['pool', 'run', 'select'])
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--queries-per-topic', type=int, default=2)
    parser.add_argument('--baseline-topics')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    if args.cmd == 'pool':
        rows = existing_pool()
        print(json.dumps({'existing_pool_raw': len(rows), 'existing_pool_selected': len(pool_relevant(rows, config()))}, ensure_ascii=False))
        return
    raw_path, result_path, demo_path, _ = paths(args.output_dir)
    if args.cmd == 'run':
        return run(args)
    if not raw_path.exists():
        raise RuntimeError('No saved raw Fewgood candidates')
    result = select(json.loads(raw_path.read_text()), 'select')
    write_json(result_path, result)
    write_json(demo_path, result)
    print('select: zero API calls')


if __name__ == '__main__':
    main()
