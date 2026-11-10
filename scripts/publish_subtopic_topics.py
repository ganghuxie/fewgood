#!/usr/bin/env python3
"""Publish curated V2 sub-topics as static topic JSON from local inventories + music backfill."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, '/tmp')
sys.path.insert(0, str(ROOT))

import draft_subtopics as ds  # noqa: E402

PUBLIC_TOPICS = ROOT / 'site/public/topics'
INDEX = ROOT / 'site/src/data/topics/index.json'
BACKFILL = ROOT / 'site/src/data/music-subtopic-backfill.json'
CONFIG = ROOT / 'config/subtopics.json'
SLIM = ROOT / 'site/src/data/subtopics.json'
KEEP_FIXTURES = {'c-plus-plus', 'c-sharp', 'cafe', 'no-results', 'quota-deferred', 'waiting-demo'}

CHANNEL_GROUPS = {
    'mandopop': [
        '杰威尔音乐 JVR Music', '林俊傑 JJ Lin', "相信音樂 B'in Music", '滚石唱片 ROCK RECORDS',
        '华纳音乐台湾 Warner Music Taiwan', '台湾索尼音乐 Sony Music Taiwan', '告五人 Accusefive', '毛不易',
    ],
    'cantonese': [
        '陳奕迅 Eason Chan', '環球音樂香港 Universal Music Hong Kong', '英皇娛樂 EEG / Emperor Entertainment',
        '寰亞音樂 Media Asia Music', '林家謙 Terence Lam', '張學友 Jacky Cheung',
        'Warner Music Hong Kong 華納音樂香港', '陳卓賢 Ian Chan',
    ],
    'indie-folk': [
        'KEXP', 'Audiotree', 'Mahogany', '陈粒', '万能青年旅店', '草東沒有派對 No Party For Cao Dong',
        '好妹妹乐队', '新裤子 New Pants',
    ],
    'jazz-classical': [
        'Deutsche Grammophon', 'Berliner Philharmoniker', 'Blue Note Records', 'Jazz at Lincoln Center',
        'Classic FM', 'ECM Records', '国家大剧院 NCPA',
    ],
    'rnb-soul': [
        'SZA', 'TheWeekndVEVO', '方大同 Khalil Fong', '陶喆 David Tao', 'COLORS', 'Mahogany',
        'Daniel Caesar', '蔡健雅 Tanya Chua',
    ],
    'electronic': [
        'Boiler Room', 'Cercle', 'Ninja Tune', 'Mixmag', 'Defected Records', 'Anjunadeep',
        'Resident Advisor', 'Innervisions',
    ],
    'hiphop': [
        'COLORS', '熱狗 MC HotDog', '蛋堡 Soft Lipa', '高爾宣 OSN', '瘦子 E.SO', '張震嶽', '法老 Pharaoh', '頑童 MJ116',
    ],
}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def merge_backfill(inventories, backfill):
    extras = []
    by_request = {}
    for channel in backfill.get('channels') or []:
        by_request[channel.get('requested_name')] = channel
        for video in channel.get('videos') or []:
            extras.append({
                'id': video.get('id'),
                'title': video.get('title') or '',
                'channel_id': video.get('channel_id') or channel.get('id') or '',
                'channel': video.get('channel') or channel.get('title') or '',
                'tags': [],
                'duration': video.get('duration_seconds'),
                'published_at': video.get('published_at') or '',
                'thumb': video.get('thumb') or '',
            })
    add_unique = ds.add_unique
    store = {video['id']: video for video in inventories['music_local']['videos'] if video.get('id')}
    add_unique(store, extras)
    inventories['music_local']['videos'] = list(store.values())
    inventories['music_local']['by_id'] = store
    return by_request



def apply_rule(videos, rule):
    hits = []
    for video in videos:
        if match_safe(video, rule):
            hits.append(video)
    channels = sorted({(video.get('channel') or video.get('channel_id') or '?') for video in hits})
    return hits, channels


def match_safe(video, rule):
    if rule.get('logic') == 'intersection':
        if not ds.passes_duration(video, rule.get('min_duration_seconds')):
            return False
        if not ds.passes_excludes(video, rule.get('exclude_terms') or [], rule.get('exclude_title_terms') or getattr(ds, 'CLIP_TERMS', [])):
            return False
        title = video.get('title') or ''
        blob = ' '.join(ds.text_fields(video))
        for group in rule.get('all_groups') or []:
            text = title if group.get('in') == 'title' else blob
            if not ds.hits_any(text, group.get('terms') or []):
                return False
        return True
    return ds.match_video_with_weak(video, rule)


def ids_for(group, by_request):
    ids = []
    missing = []
    for name in CHANNEL_GROUPS[group]:
        channel = by_request.get(name)
        if channel and channel.get('id'):
            ids.append(channel['id'])
        else:
            missing.append(name)
    return ids, missing


def to_topic_video(video):
    video_id = video.get('id') or video.get('video_id')
    return {
        'video_id': video_id,
        'title': video.get('title') or video_id,
        'channel_title': video.get('channel') or video.get('channel_title') or 'YouTube',
        'published_at': video.get('published_at') or '',
        'url': f'https://www.youtube.com/watch?v={video_id}',
        'thumbnail': video.get('thumb') or f'https://i.ytimg.com/vi/{video_id}/mqdefault.jpg',
        'duration_seconds': video.get('duration') or video.get('duration_seconds') or 0,
        'channel_id': video.get('channel_id') or '',
    }


def main():
    config = json.loads(CONFIG.read_text())
    backfill = json.loads(BACKFILL.read_text()) if BACKFILL.exists() else {'channels': [], 'skipped': []}
    inventories = ds.load_inventories()
    by_request = merge_backfill(inventories, backfill)
    channel_lookup = {}
    generated_at = now_iso()

    # Existing Stones Throw / NPR / FIRST TAKE / VEVO already in music_local
    hiphop_ids, hiphop_missing = ids_for('hiphop', by_request)
    stones = next((v.get('channel_id') for v in inventories['music_local']['videos'] if (v.get('channel') or '') == 'Stones Throw' and v.get('channel_id')), 'UC0L0PDO9kUS46JC1wEjLEbg')
    if stones and stones not in hiphop_ids:
        hiphop_ids.append(stones)

    npr_id = 'UC4eYXhJI4-7wSWc8UNRwD4A'
    extra_rules = {
        'mandopop': {'logic': 'channel_only', 'channel_ids': ids_for('mandopop', by_request)[0]},
        'cantonese': {'logic': 'channel_only', 'channel_ids': ids_for('cantonese', by_request)[0]},
        'indie-folk': {'logic': 'channel_only', 'channel_ids': ids_for('indie-folk', by_request)[0]},
        'jazz-classical': {
            'logic': 'channel_or_terms',
            'channel_ids': ids_for('jazz-classical', by_request)[0],
            'title_or_tags_any': ['jazz', 'classical', 'symphony', 'orchestra', 'piano sonata', 'concerto', '爵士', '古典'],
        },
        'rnb-soul': {'logic': 'channel_only', 'channel_ids': ids_for('rnb-soul', by_request)[0]},
        'electronic': {'logic': 'channel_only', 'channel_ids': ids_for('electronic', by_request)[0]},
    }

    slim_categories = []
    published = []
    counts = {}

    for category in config.get('categories') or []:
        slim_subs = []
        for item in category.get('subtopics') or []:
            rule = dict(item.get('rule') or {})
            if item['id'] == 'hiphop':
                rule['channel_ids'] = sorted(set((rule.get('channel_ids') or []) + hiphop_ids))
                if rule.get('logic') == 'channel_and_terms' or rule.get('logic') == 'channel_and_keywords':
                    # keep existing Stones Throw title gate, but also allow new official channels by id-only
                    rule = {'logic': 'channel_only', 'channel_ids': rule['channel_ids']}
                else:
                    rule['logic'] = rule.get('logic') or 'channel_only'
                    if 'channel_ids' in rule and 'title_any' not in rule and 'title_or_tags_any' not in rule:
                        rule['logic'] = 'channel_only'
                item['rule'] = rule
            if item['id'] in extra_rules:
                rule = extra_rules[item['id']]
                item['rule'] = rule
            matched, _channels = apply_rule(inventories[item['inventory']]['videos'], rule)
            counts[item['id']] = len(matched)
            item['video_count'] = len(matched)
            item['channel_count'] = len({video.get('channel_id') for video in matched if video.get('channel_id')})
            item['status'] = 'ok' if matched else 'empty'
            write_topic(item, category, matched, generated_at)
            published.append(item)
            slim_subs.append(slim_item(item))
        promoted = []
        remaining_fetch = []
        for item in category.get('needs_fetch') or []:
            extra = extra_rules.get(item['id'])
            if not extra or not extra.get('channel_ids'):
                remaining_fetch.append(item)
                continue
            # NPR Music stays searchable by jazz/classical title terms only; do not ingest all Tiny Desk videos.
            matched, _channels = apply_rule(inventories[item['inventory']]['videos'], extra)
            # NPR extras: channel_or_terms would include ALL DG/etc via channel_ids (good) AND npr videos with jazz terms (good)
            item['rule'] = extra
            item['video_count'] = len(matched)
            item['channel_count'] = len({video.get('channel_id') for video in matched if video.get('channel_id')})
            item['status'] = 'ok' if len(matched) >= 8 else ('thin' if matched else 'needs_fetch')
            item['example_titles'] = [
                {'id': video.get('id'), 'title': video.get('title'), 'channel': video.get('channel')}
                for video in matched[:3]
            ]
            write_topic(item, category, matched, generated_at)
            published.append(item)
            if item['status'] != 'needs_fetch':
                promoted.append(item)
                slim_subs.append(slim_item(item))
            else:
                remaining_fetch.append(item)
            counts[item['id']] = len(matched)
        category['subtopics'] = (category.get('subtopics') or []) + promoted
        # de-dup if somehow both
        seen = set()
        uniq = []
        for item in category['subtopics']:
            if item['id'] in seen:
                continue
            seen.add(item['id'])
            uniq.append(item)
        category['subtopics'] = uniq
        category['needs_fetch'] = remaining_fetch
        if category['id'] != 'trending':
            slim_categories.append({
                'id': category['id'],
                'name_zh': category['name_zh'],
                'subtopics': slim_subs if category['id'] != 'trending' else slim_subs,
            })

    # Rebuild 全部 as aggregate
    all_subs = [sub for cat in slim_categories for sub in cat['subtopics']]
    slim = {
        'generated_at': generated_at,
        'categories': [
            {'id': 'trending', 'name_zh': '全部', 'subtopics': all_subs},
            *slim_categories,
        ],
    }

    # Update config metadata
    config['generated_at'] = generated_at
    config['status'] = 'final'
    config['backfill'] = {
        'quota_units': (backfill.get('quota_units') or {}).get('units'),
        'search_list': 0,
        'channels_fetched': backfill.get('channel_count'),
        'videos_fetched': backfill.get('video_count'),
        'skipped': [
            {'name': row.get('name'), 'reason': row.get('reason')}
            for row in backfill.get('skipped') or []
        ],
    }
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    SLIM.write_text(json.dumps(slim, ensure_ascii=False, indent=2) + '\n')

    # Keep fixture topics in the public index.
    existing_index = json.loads(INDEX.read_text()) if INDEX.exists() else {'topics': []}
    fixtures = [row for row in existing_index.get('topics', []) if row.get('topic_id') in KEEP_FIXTURES]
    curated = []
    for item in published:
        if item.get('status') == 'needs_fetch':
            continue
        curated.append({
            'topic_id': item['id'],
            'canonical_name': item['name_zh'],
            'status': 'ready' if item.get('video_count') else 'empty',
            'generated_at': generated_at,
            'category': next(cat['id'] for cat in config['categories'] if any(s['id']==item['id'] for s in (cat.get('subtopics') or []) + (cat.get('needs_fetch') or []))),
        })
    INDEX.write_text(json.dumps({'generated_at': generated_at, 'topics': fixtures + curated}, ensure_ascii=False, indent=2) + '\n')
    print('published topics', len(curated), 'fixtures', len(fixtures))
    for key, value in counts.items():
        print(f'  {key}: {value}')


def slim_item(item):
    return {
        'id': item['id'],
        'name_zh': item['name_zh'],
        'video_count': item.get('video_count') or 0,
        'status': 'ready' if item.get('video_count') else 'empty',
    }


def write_topic(item, category, matched, generated_at):
    videos = [to_topic_video(video) for video in matched if video.get('id') or video.get('video_id')]
    videos.sort(key=lambda row: row.get('published_at') or '', reverse=True)
    payload = {
        'topic_id': item['id'],
        'canonical_name': item['name_zh'],
        'status': 'ready' if videos else 'empty',
        'generated_at': generated_at,
        'source': 'curated_library',
        'category': category['id'],
        'videos': videos[:80],
        'match_count': len(videos),
    }
    path = PUBLIC_TOPICS / f"{item['id']}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
