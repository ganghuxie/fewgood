"""One-off, bounded Chinese creator discovery for Fewgood round 4."""
import argparse, copy, json, os, re, time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from .fewgood import API, Fetcher, iso, merge, parse_time, usage_empty, write_json
from .fewgood_creators import (ROOT, cfg, normalize_channel, replay_creator_rules,
                               rules, write_creators_config)
from . import fewgood_r3

RAW = ROOT / 'data/experiments/fewgood-zh-raw.json'
USAGE = ROOT / 'data/experiments/fewgood-zh-usage.json'
R3_RAW = ROOT / 'data/experiments/fewgood-r3-raw.json'
R3_RESULT = ROOT / 'data/experiments/fewgood-r3-result.json'
R4_RAW = ROOT / 'data/experiments/fewgood-r4-raw.json'
RESULT = ROOT / 'data/experiments/fewgood-r4-result.json'
DEMO = ROOT / 'site/src/data/fewgood-mvp.json'
SUMMARY = ROOT / 'data/experiments/fewgood-zh-summary.json'


def discovery():
    return yaml.safe_load((ROOT / 'config/fewgood_zh_discovery.yaml').read_text())


class StrictFetcher(Fetcher):
    """A discovery request is never retried after rate/quota refusal."""
    def call(self, endpoint, params, purpose):
        if self.stopped:
            raise RuntimeError('YouTube requests stopped')
        search = endpoint == 'search'; counter = 'search_calls' if search else 'other_units'
        cap = self.cfg['search_call_cap'] if search else self.cfg['other_unit_cap']
        if self.usage[counter] >= cap:
            raise RuntimeError(f'{endpoint} call cap reached before request')
        try:
            response = self.get(API + endpoint, params={**params, 'key': self.key}, timeout=30)
            status, payload = response.status_code, response.json()
        except Exception:
            status, payload = 0, {}
        self.usage[counter] += 1; self.usage['old_model_units'] += 100 if search else 1
        self.usage['calls'].append({'endpoint': endpoint, 'purpose': purpose, 'timestamp': iso(),
                                    'http_status': status, 'returned': len(payload.get('items', []))})
        if status in (403, 429):
            self.stopped = True; self.usage['aborted_reason'] = f'{status} discovery stopped'
            raise RuntimeError(self.usage['aborted_reason'])
        return payload


def estimate():
    d = discovery()
    return {'search_calls': len(d['queries']), 'search_call_cap': d['search_call_cap'],
            'other_unit_cap': d['other_unit_cap'], 'max_channels': d['max_channels'],
            'endpoints': ['search', 'channels', 'playlistItems', 'videos'],
            'plan': '10 searches; verify channels in 50-id batches; at most 40 uploads and video-detail calls'}


def _existing_ids():
    ids = {x.get('channel_id') for x in yaml.safe_load((ROOT / 'config/fewgood_creators.yaml').read_text()).get('creators', [])}
    if R3_RAW.exists():
        ids |= {x.get('channel_id') for x in json.loads(R3_RAW.read_text()).get('creators', [])}
    return ids - {None}


def _chinese(item):
    sn = item.get('snippet', {})
    return bool(re.search(r'[\u4e00-\u9fff]', (sn.get('title', '') + sn.get('description', ''))) or
                str(sn.get('defaultLanguage', '')).lower().startswith('zh'))


def _excluded(item, rule):
    text = (item.get('snippet', {}).get('title', '') + ' ' + item.get('snippet', {}).get('description', '')).casefold()
    return any(str(x).casefold() in text for x in rule['exclude_patterns'])


def fetch(args, get=None):
    plan = estimate()
    if args.estimate:
        print(json.dumps(plan, ensure_ascii=False)); return plan
    key = os.environ.get('YOUTUBE_API_KEY')
    if not key: raise RuntimeError('YOUTUBE_API_KEY is required (credential is never printed)')
    d, rule, topics = discovery(), rules(), cfg()['topics']
    f = StrictFetcher({'search_call_cap': 10, 'other_unit_cap': 300}, key, get=get)
    creators, candidates, hit_topics = [], [], defaultdict(set)
    started = time.monotonic()
    try:
        known = _existing_ids(); found = defaultdict(int)
        defaults = d['search_defaults']
        after = (datetime.now(timezone.utc) - timedelta(days=defaults['published_within_days'])).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        for q in d['queries']:
            response = f.call('search', {'part': 'snippet', 'type': defaults['type'], 'order': defaults['order'],
                'publishedAfter': after, 'maxResults': defaults['maxResults'], 'relevanceLanguage': q['lang'], 'q': q['query']}, 'zh_search')
            for row in response.get('items', []):
                cid = row.get('snippet', {}).get('channelId')
                if cid and cid not in known:
                    found[cid] += 1; hit_topics[cid].add(q['topic'])
        verified = {}
        for start in range(0, len(found), 50):
            ids = list(found)[start:start + 50]
            response = f.call('channels', {'part': 'snippet,statistics,contentDetails', 'id': ','.join(ids)}, 'zh_verify_channel')
            for item in response.get('items', []): verified[item.get('id')] = item
        eligible = []
        for cid, item in verified.items():
            st = item.get('statistics', {})
            try: subs = int(st.get('subscriberCount'))
            except (TypeError, ValueError): subs = 0
            if _chinese(item) and not st.get('hiddenSubscriberCount') and subs >= rule['discovered_min_subscribers']['zh'] and not _excluded(item, rule):
                eligible.append(cid)
        eligible.sort(key=lambda cid: (-found[cid], cid)); eligible = eligible[:d['max_channels']]
        for cid in eligible:
            channel = normalize_channel(verified[cid], {'lang': 'zh', 'subtopics': sorted(hit_topics[cid]), 'evidence': ['zh_discovery_r4']})
            playlist = channel.get('uploads_playlist')
            response = f.call('playlistItems', {'part': 'snippet,contentDetails', 'playlistId': playlist, 'maxResults': 50}, 'zh_uploads') if playlist else {}
            uploads = response.get('items', [])
            dates = [x.get('contentDetails', {}).get('videoPublishedAt') or x.get('snippet', {}).get('publishedAt') for x in uploads]
            channel['last_upload_at'] = max(dates, default=None); channel['checked_at'] = iso()
            if not channel['last_upload_at'] or parse_time(channel['last_upload_at']) < datetime.now(timezone.utc) - timedelta(days=rule['active_within_days']):
                channel['status'] = channel['reason'] = 'inactive'; creators.append(channel); continue
            channel['status'] = channel['reason'] = 'included'; creators.append(channel)
            for item in uploads:
                vid = item.get('contentDetails', {}).get('videoId') or item.get('snippet', {}).get('resourceId', {}).get('videoId')
                published = item.get('contentDetails', {}).get('videoPublishedAt') or item.get('snippet', {}).get('publishedAt', '')
                if vid and parse_time(published) >= datetime.now(timezone.utc) - timedelta(days=30):
                    candidates.append({'id': vid, 'sources': ['zh_discovery_r4:' + cid]})
        details = {}
        for start in range(0, len(candidates), 50):
            batch = candidates[start:start + 50]
            response = f.call('videos', {'part': 'snippet,contentDetails,statistics,status', 'id': ','.join(x['id'] for x in batch)}, 'zh_candidate_details')
            details.update({x.get('id'): x for x in response.get('items', [])})
        candidates = [dict(details[x['id']], sources=x['sources']) for x in candidates if x['id'] in details]
    except RuntimeError as error:
        f.usage['aborted_reason'] = f.usage['aborted_reason'] or str(error)
    finally:
        raw = {'data_refreshed_at': iso(), 'round': '4 zh', 'creators': creators,
               'candidate_videos': candidates, 'usage_summary': f.usage,
               'timing': {'collect_seconds': round(time.monotonic() - started, 6)}, 'plan': plan}
        write_json(RAW, raw); write_json(USAGE, f.usage)
    return raw


def _merge(base, zh):
    creators = {x.get('channel_id'): copy.deepcopy(x) for x in base.get('creators', []) if x.get('channel_id')}
    for row in zh.get('creators', []):
        creators[row.get('channel_id')] = copy.deepcopy(row)
    return {**copy.deepcopy(base), 'data_refreshed_at': zh.get('data_refreshed_at', base.get('data_refreshed_at')),
            'creators': list(creators.values()), 'candidate_videos': merge(base.get('candidate_videos', []) + zh.get('candidate_videos', [])),
            'usage_summary': zh.get('usage_summary', usage_empty())}


def _summary(result, previous):
    old = {t['id']: [v['video_id'] for v in t.get('videos', [])] for t in previous.get('topics', [])}
    changes = [{'topic': t['id'], 'before': old.get(t['id'], []), 'after': [v['video_id'] for v in t.get('videos', [])]}
               for t in result['topics'] if old.get(t['id'], []) != [v['video_id'] for v in t.get('videos', [])]]
    channels = defaultdict(list)
    for c in result['creators']:
        if c.get('status') == 'included' and 'zh_discovery_r4' in c.get('evidence', []):
            row = {k: c.get(k) for k in ('name', 'channel_id', 'subscriber_count', 'last_upload_at')}
            for topic in c.get('subtopics', []): channels[topic].append(row)
    return {'round': '4 zh', 'new_included_channels_by_subtopic': dict(channels), 'top6_changes_vs_r3': changes}


def select():
    if not RAW.exists() or not R3_RAW.exists(): raise RuntimeError('Both fewgood-zh-raw.json and fewgood-r3-raw.json are required')
    base, zh = json.loads(R3_RAW.read_text()), json.loads(RAW.read_text())
    merged = _merge(base, zh)
    # R3's selector owns final ranking; apply its creator-focus replay before it.
    fewgood_r3.replay_subscriber_rule(merged['creators'], rules())
    replay_creator_rules(merged['creators'], merged['candidate_videos'], cfg()['topics'], rules())
    write_json(R4_RAW, merged)
    result = fewgood_r3.select(merged, 'zh_select'); result['round'] = 4
    write_json(RESULT, result); write_json(DEMO, result); write_creators_config(result['creators'])
    previous = json.loads(R3_RESULT.read_text()) if R3_RESULT.exists() else {}
    write_json(SUMMARY, _summary(result, previous)); print('select: zero API calls')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument('cmd', choices=['fetch', 'select']); parser.add_argument('--estimate', action='store_true')
    args = parser.parse_args(argv)
    return fetch(args) if args.cmd == 'fetch' else select()


if __name__ == '__main__': main()
