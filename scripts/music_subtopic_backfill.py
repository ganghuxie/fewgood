#!/usr/bin/env python3
"""One-time uploads-first backfill for approved V2 music sub-topics.

Resolves official channel IDs cheaply (public channel pages first, then
channels.list forHandle/forUsername at 1 unit). Fetches playlistItems page 1
(~50 uploads, 1 unit) per new channel. Never uses search.list. Does not print
API keys. Writes its own quota file so data/quota.json is not committed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ytrec.core import Client, YOUTUBE_API, youtube_key, iso_now  # noqa: E402

UA = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
)
SKIP_NAMES = {'NPR Music'}
HANDLE_CANDIDATES = {
    '杰威尔音乐 JVR Music': ['JVRMusic', 'jvrmusic', 'JVR-Music', '杰威尔音乐'],
    '林俊傑 JJ Lin': ['jjlin', 'JJLin', 'JJLIN', '林俊傑'],
    "相信音樂 B'in Music": ['相信音樂', 'binmusic', 'BInMusic', 'binmusictw', 'believeinmusictw'],
    '滚石唱片 ROCK RECORDS': ['滾石唱片', '滚石唱片', 'rockrecordstw', 'ROCKRECORDSTW', 'RockRecordsOfficial'],
    '华纳音乐台湾 Warner Music Taiwan': ['WarnerMusicTaiwan', 'warnermusictaiwan', 'wmttaiwan'],
    '台湾索尼音乐 Sony Music Taiwan': ['SonyMusicTaiwan', 'sonymusictaiwan', 'SMETaiwan'],
    '告五人 Accusefive': ['Accusefive', 'accusefive', '告五人', 'AccusefiveOfficial'],
    '毛不易': ['毛不易', 'maobuyiofficial', 'MaobuyiMusic', 'maobuyi'],
    '陳奕迅 Eason Chan': ['easonchan', 'EasonChan', 'easonchanofficial', '陳奕迅'],
    '環球音樂香港 Universal Music Hong Kong': ['UMHK', 'universalmusichongkong', 'UniversalMusicHK', 'umghongkong'],
    '英皇娛樂 EEG / Emperor Entertainment': ['英皇娛樂', 'EEGMusicLimited', 'eegmusichk', 'EmperorEntertainmentGroup'],
    '寰亞音樂 Media Asia Music': ['MediaAsiaMusic', 'mediaasiamusic', 'MediaAsia', '寰亞音樂'],
    '林家謙 Terence Lam': ['林家謙', 'terencelammusic', 'TerenceLamOfficial', 'lamterence'],
    '張學友 Jacky Cheung': ['張學友', 'JackyCheungOfficialChannel'],
    'Warner Music Hong Kong 華納音樂香港': ['warnermusichk', 'WarnerMusicHongKong', 'WMHK'],
    '陳卓賢 Ian Chan': ['陳卓賢', 'ianchanofficial', 'IanChanAA'],
    'KEXP': ['KEXP', 'kexp', 'kexplive'],
    'Audiotree': ['audiotree', 'Audiotree', 'AudiotreeMusic'],
    'Mahogany': ['mahoganySESSIONS', 'MahoganySession', 'wearemahogany', 'MahoganyHQ'],
    '陈粒': ['陈粒', '陳粒音乐', 'ChenLiOfficial'],
    '万能青年旅店': ['万能青年旅店', 'wunianqinglv', 'WNQLD', 'ubiquitoussightseeing'],
    '草東沒有派對 No Party For Cao Dong': ['nopartyforcaodong', 'NoPartyForCaoDong', '草東沒有派對', 'caodong'],
    '好妹妹乐队': ['好妹妹乐队', 'haomeimei', 'GoodSistersBand', '好妹妹'],
    '新裤子 New Pants': ['NewPants', 'newpants', '新裤子', 'NewPantsOfficial'],
    'Deutsche Grammophon': ['deutschegrammophon', 'DeutscheGrammophon', 'DG'],
    'Berliner Philharmoniker': ['BerlinerPhilharmoniker', 'berlinphil', 'berlinerphilharmoniker'],
    'Blue Note Records': ['bluenoterecords', 'BlueNoteRecords', 'bluenote'],
    'Jazz at Lincoln Center': ['jazzatlincolncenter', 'JazzAtLincolnCenter', 'jalc'],
    'Classic FM': ['ClassicFM', 'classicfm'],
    'ECM Records': ['ECMRecords', 'ecmrecords', 'ECM'],
    '国家大剧院 NCPA': ['NCPAChina', 'ncpachina', '国家大剧院', 'NCPA'],
    'SZA': ['SZA', 'SZAVEVO', 'sza'],
    'TheWeekndVEVO': ['TheWeekndVEVO', 'theweekndvevo', 'TheWeeknd'],
    '方大同 Khalil Fong': ['KhalilFong', 'khalilfong', '方大同', 'KhalilFongOfficial'],
    '陶喆 David Tao': ['davidtao', 'DavidTao', '陶喆', 'DavidTaoOfficial'],
    'COLORS': ['COLORS', 'COLORSxSTUDIOS', 'colorsxstudios'],
    'Daniel Caesar': ['DanielCaesar', 'danielcaesar'],
    '蔡健雅 Tanya Chua': ['蔡健雅', 'TanyaChuaOfficial', 'tanyachuaofficial'],
    'Boiler Room': ['boilerroom', 'BoilerRoom', 'boilerroomtv'],
    'Cercle': ['Cercle', 'cercle', 'CercleMusic'],
    'Ninja Tune': ['NinjaTune', 'ninjatune'],
    'Mixmag': ['Mixmag', 'mixmag'],
    'Defected Records': ['DefectedRecords', 'defectedrecords', 'Defected'],
    'Anjunadeep': ['Anjunadeep', 'anjunadeep'],
    'Resident Advisor': ['ResidentAdvisor', 'residentadvisor', 'RAco'],
    'Innervisions': ['Innervisions', 'innervisions', 'Innervisionsofficial'],
    '熱狗 MC HotDog': ['MCHotDog', 'mchotdog', '熱狗', 'MCHotDogOfficial'],
    '蛋堡 Soft Lipa': ['softlipaofficial', '蛋堡', 'SoftLipaOfficial'],
    '高爾宣 OSN': ['OSN', '高尔宣OSN', '高爾宣OSN', 'gaoerxuanOSN', 'OSNofficial'],
    '瘦子 E.SO': ['ESO', '瘦子ESO', 'esoMJ116', 'ESOofficial'],
    '張震嶽': ['張震嶽', '张震岳官方', 'AyalKomodOfficial'],
    '法老 Pharaoh': ['法老', '法老Pharaoh', 'Pharaoh法老'],
    '頑童 MJ116': ['MJ116', '顽童MJ116', '頑童MJ116', 'MJ116Official'],
}
TITLE_HINTS = {
    '杰威尔音乐 JVR Music': ['jvr', '杰威尔', '傑威爾'],
    '林俊傑 JJ Lin': ['林俊傑', '林俊杰', 'jj lin', 'jjlin'],
    "相信音樂 B'in Music": ['相信音樂', "b'in", 'bin music'],
    '滚石唱片 ROCK RECORDS': ['rock records', '滚石唱片', '滾石唱片'],
    '华纳音乐台湾 Warner Music Taiwan': ['warner music taiwan', '华纳音乐台湾', '華納音樂台灣'],
    '台湾索尼音乐 Sony Music Taiwan': ['sony music taiwan', '索尼音乐台湾', '台灣索尼'],
    '告五人 Accusefive': ['告五人', 'accusefive'],
    '毛不易': ['毛不易'],
    '陳奕迅 Eason Chan': ['陳奕迅', '陈奕迅', 'eason chan'],
    '環球音樂香港 Universal Music Hong Kong': ['universal music hong kong', '環球音樂香港', '环球音乐香港', 'umhk'],
    '英皇娛樂 EEG / Emperor Entertainment': ['eeg', '英皇', 'emperor entertainment'],
    '寰亞音樂 Media Asia Music': ['media asia', '寰亞', '寰亚'],
    '林家謙 Terence Lam': ['林家謙', '林家谦', 'terence lam'],
    '張學友 Jacky Cheung': ['張學友', '张学友', 'jacky cheung'],
    'Warner Music Hong Kong 華納音樂香港': ['warner music hong kong', '華納音樂香港', '华纳音乐香港'],
    '陳卓賢 Ian Chan': ['陳卓賢', '陈卓贤', 'ian chan'],
    'KEXP': ['kexp'],
    'Audiotree': ['audiotree'],
    'Mahogany': ['mahogany'],
    '陈粒': ['陈粒', '陳粒'],
    '万能青年旅店': ['万能青年旅店', '萬能青年旅店'],
    '草東沒有派對 No Party For Cao Dong': ['草東', '草东', 'cao dong', 'no party'],
    '好妹妹乐队': ['好妹妹'],
    '新裤子 New Pants': ['新裤子', '新褲子', 'new pants'],
    'Deutsche Grammophon': ['deutsche grammophon', 'dg'],
    'Berliner Philharmoniker': ['berliner phil', 'berlin phil'],
    'Blue Note Records': ['blue note'],
    'Jazz at Lincoln Center': ['lincoln center', 'jazz at lincoln'],
    'Classic FM': ['classic fm'],
    'ECM Records': ['ecm'],
    '国家大剧院 NCPA': ['ncpa', '国家大剧院', '國家大劇院'],
    'SZA': ['sza'],
    'TheWeekndVEVO': ['weeknd'],
    '方大同 Khalil Fong': ['方大同', 'khalil fong'],
    '陶喆 David Tao': ['陶喆', '陶喆', 'david tao'],
    'COLORS': ['colors'],
    'Daniel Caesar': ['daniel caesar'],
    '蔡健雅 Tanya Chua': ['蔡健雅', 'tanya chua'],
    'Boiler Room': ['boiler room'],
    'Cercle': ['cercle'],
    'Ninja Tune': ['ninja tune'],
    'Mixmag': ['mixmag'],
    'Defected Records': ['defected'],
    'Anjunadeep': ['anjunadeep'],
    'Resident Advisor': ['resident advisor'],
    'Innervisions': ['innervisions'],
    '熱狗 MC HotDog': ['hotdog', '熱狗', '热狗'],
    '蛋堡 Soft Lipa': ['软唇', '蛋堡', 'soft lipa'],
    '高爾宣 OSN': ['osn', '高爾宣', '高尔宣'],
    '瘦子 E.SO': ['e.so', '瘦子', 'eso'],
    '張震嶽': ['張震嶽', '张震岳'],
    '法老 Pharaoh': ['法老'],
    '頑童 MJ116': ['mj116', '頑童', '顽童'],
}
REQUIRED_TITLE_HINTS = {
    "相信音樂 B'in Music": ['相信', "b'in"],
    '滚石唱片 ROCK RECORDS': ['滚石', '滾石', 'rock records'],
    '英皇娛樂 EEG / Emperor Entertainment': ['英皇', 'emperor entertainment', 'eeg music'],
    '陳卓賢 Ian Chan': ['陳卓賢', '陈卓贤'],
    'Mahogany': ['mahogany session', 'mahogany sessions'],
    '陈粒': ['陈粒', '陳粒'],
    '蔡健雅 Tanya Chua': ['蔡健雅', 'tanya chua'],
    '張學友 Jacky Cheung': ['張學友', '张学友', 'jacky cheung'],
    '蛋堡 Soft Lipa': ['蛋堡', 'soft lipa'],
    '法老 Pharaoh': ['法老'],
    'Classic FM': ['classic fm'],
}
PAGE_ID_OVERRIDES = {
    'Warner Music Hong Kong 華納音樂香港': {
        'id': 'UCOkYP-AE5izd0N7af72uC1Q',
        'title': 'Warner Music Hong Kong',
        'resolved_via': 'page:@warnermusichk',
        'url': 'https://www.youtube.com/warnermusichk',
    },
}


def fold(value: str) -> str:
    return (value or '').casefold()


def compact(value: str) -> str:
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '', fold(value))


def title_matches(expected: str, actual: str) -> bool:
    actual_f = fold(actual)
    actual_c = compact(actual)
    hints = TITLE_HINTS.get(expected) or [expected]
    required = REQUIRED_TITLE_HINTS.get(expected) or []
    if required and not any(fold(token) in actual_f or compact(token) in actual_c for token in required):
        return False
    return any(
        fold(hint) and (fold(hint) in actual_f or compact(hint) in actual_c)
        for hint in hints
    )


def parse_channel_page(html: str) -> dict:
    ids = re.findall(r'"externalId":"(UC[\w-]{20,})"', html)
    ids += re.findall(r'"channelId":"(UC[\w-]{20,})"', html)
    ids += re.findall(r'itemprop="identifier" content="(UC[\w-]{20,})"', html)
    titles = re.findall(r'<meta property="og:title" content="([^"]+)"', html)
    titles += re.findall(r'"channelMetadataRenderer":\{"title":"([^"]+)"', html)
    channel_id = max(set(ids), key=ids.count) if ids else ''
    title = titles[0] if titles else ''
    title = title.replace(' - YouTube', '').replace(' – YouTube', '')
    return {'id': channel_id, 'title': title}


def fetch_html(url: str) -> tuple[int, str, str]:
    response = requests.get(
        url,
        headers={'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'},
        timeout=25,
        allow_redirects=True,
    )
    return response.status_code, response.text, response.url


def resolve_via_pages(name: str) -> dict | None:
    if name in PAGE_ID_OVERRIDES:
        return dict(PAGE_ID_OVERRIDES[name])
    for handle in HANDLE_CANDIDATES.get(name, []):
        url = f'https://www.youtube.com/@{handle}'
        try:
            status, html, final = fetch_html(url)
        except requests.RequestException:
            continue
        if status != 200 or 'This page isn\'t available' in html:
            continue
        parsed = parse_channel_page(html)
        if parsed['id'] and title_matches(name, parsed['title'] or handle):
            return {
                'id': parsed['id'],
                'title': parsed['title'] or name,
                'resolved_via': f'page:@{handle}',
                'url': final,
            }
    return None


def resolve_via_api(name: str, client: Client, key: str, used: dict) -> dict | None:
    for handle in HANDLE_CANDIDATES.get(name, []):
        if used['units'] + 1 > used['cap']:
            break
        try:
            payload = client.get(
                YOUTUBE_API + 'channels',
                dict(part='snippet,contentDetails,statistics', forHandle=handle, key=key),
                youtube=True,
            )
            used['units'] += 1
            used['channels_list'] += 1
        except RuntimeError as error:
            print(f'resolve skipped {name} @{handle}: {error}')
            continue
        items = payload.get('items') or []
        if not items:
            continue
        item = items[0]
        title = (item.get('snippet') or {}).get('title') or ''
        if title_matches(name, title):
            return {
                'id': item['id'],
                'title': title,
                'resolved_via': f'forHandle:{handle}',
                'uploads_playlist_id': ((item.get('contentDetails') or {}).get('relatedPlaylists') or {}).get('uploads'),
                'subscriber_count': int((item.get('statistics') or {}).get('subscriberCount') or 0),
            }
        print(f'skip unverified handle @{handle} for {name}: title={title!r}')
    return None


def uploads_id(channel_id: str) -> str:
    return 'UU' + channel_id[2:] if channel_id.startswith('UC') and len(channel_id) > 2 else ''


def proposed_channels(config: dict) -> list[dict]:
    rows = []
    seen = set()
    for category in config.get('categories', []):
        for bucket in ('needs_fetch', 'subtopics'):
            for item in category.get(bucket) or []:
                for key in ('fetch_proposal', 'supplement_fetch_proposal'):
                    proposal = item.get(key) or {}
                    for channel in proposal.get('channels') or []:
                        name = channel['name']
                        if name in seen:
                            continue
                        seen.add(name)
                        rows.append({
                            'name': name,
                            'confidence': channel.get('confidence'),
                            'note': channel.get('note'),
                            'subtopic_id': item.get('id'),
                            'subtopic_name': item.get('name_zh'),
                        })
    return rows


def fetch_uploads(client: Client, key: str, channel: dict, used: dict) -> list[dict]:
    playlist = channel.get('uploads_playlist_id') or uploads_id(channel['id'])
    if not playlist:
        return []
    if used['units'] + 1 > used['cap']:
        raise RuntimeError('quota cap would be exceeded before playlistItems')
    payload = client.get(
        YOUTUBE_API + 'playlistItems',
        dict(part='snippet,contentDetails', playlistId=playlist, maxResults=50, key=key),
        youtube=True,
    )
    used['units'] += 1
    used['playlist_items'] += 1
    videos = []
    for item in payload.get('items') or []:
        snippet, details = item.get('snippet') or {}, item.get('contentDetails') or {}
        video_id = details.get('videoId') or (snippet.get('resourceId') or {}).get('videoId')
        if not video_id:
            continue
        videos.append({
            'id': video_id,
            'title': snippet.get('title') or '',
            'published_at': details.get('videoPublishedAt') or snippet.get('publishedAt') or '',
            'thumb': ((snippet.get('thumbnails') or {}).get('medium') or {}).get('url')
            or ((snippet.get('thumbnails') or {}).get('default') or {}).get('url') or '',
            'channel_id': snippet.get('channelId') or channel['id'],
            'channel': snippet.get('channelTitle') or channel.get('title') or '',
        })
    return videos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(ROOT / 'config/subtopics.json'))
    parser.add_argument('--output', default=str(ROOT / 'site/src/data/music-subtopic-backfill.json'))
    parser.add_argument('--quota-path', default='/tmp/v2-music-backfill-quota.json')
    parser.add_argument('--cap', type=int, default=120)
    parser.add_argument('--resolve-only', action='store_true')
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text())
    rows = proposed_channels(config)
    used = {'units': 0, 'channels_list': 0, 'playlist_items': 0, 'search_list': 0, 'cap': args.cap}
    resolved, skipped = [], []

    for row in rows:
        name = row['name']
        if name in SKIP_NAMES:
            skipped.append({**row, 'reason': 'already_in_library'})
            print(f'skip existing library channel: {name}')
            continue
        found = resolve_via_pages(name)
        if found:
            print(f'resolved {name} -> {found["id"]} ({found["title"]}) via {found["resolved_via"]}')
        else:
            print(f'page resolve missed {name}; will try channels.list if fetching')
        resolved.append({**row, **(found or {}), 'page_resolved': bool(found)})

    if args.resolve_only:
        Path('/tmp/v2-music-resolve.json').write_text(
            json.dumps({'resolved': resolved, 'skipped': skipped}, ensure_ascii=False, indent=2) + '\n'
        )
        print(f'resolve-only: page-resolved {sum(1 for item in resolved if item.get("id"))}/{len(resolved)}')
        return

    key = youtube_key()
    client = Client(interval=0.2, db=None, quota_limit=args.cap, quota_path=args.quota_path)
    channels = []
    for item in resolved:
        name = item['name']
        if not item.get('id'):
            found = resolve_via_api(name, client, key, used)
            if not found:
                skipped.append({**item, 'reason': 'unverified_or_unresolved'})
                print(f'skip unresolved/unverified: {name}')
                continue
            item.update(found)
            print(f'resolved {name} -> {found["id"]} ({found["title"]}) via {found["resolved_via"]}')
        try:
            videos = fetch_uploads(client, key, item, used)
        except RuntimeError as error:
            skipped.append({**item, 'reason': f'fetch_failed:{error}'})
            print(f'fetch failed {name}: {error}')
            continue
        channels.append({
            'id': item['id'],
            'title': item.get('title') or name,
            'requested_name': name,
            'confidence': item.get('confidence'),
            'note': item.get('note'),
            'subtopic_id': item.get('subtopic_id'),
            'resolved_via': item.get('resolved_via'),
            'uploads_playlist_id': item.get('uploads_playlist_id') or uploads_id(item['id']),
            'videos': videos,
        })
        print(f'fetched {name}: {len(videos)} videos; units={used["units"]}')

    payload = {
        'generated_at': iso_now(),
        'method': 'uploads-first playlistItems page 1',
        'quota_units': dict(used),
        'skipped': skipped,
        'channels': channels,
        'channel_count': len(channels),
        'video_count': sum(len(channel['videos']) for channel in channels),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(
        f'wrote {out} channels={payload["channel_count"]} videos={payload["video_count"]} '
        f'units={used["units"]} (channels.list={used["channels_list"]} '
        f'playlistItems={used["playlist_items"]} search.list={used["search_list"]})'
    )


if __name__ == '__main__':
    main()
