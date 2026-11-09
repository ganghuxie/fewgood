"""Fewgood podcast: bounded creator-first collection and offline selection.

There is intentionally no discovery search: handle resolution uses channels.list
with forHandle, and collection walks each resolved channel's uploads playlist.
"""
import argparse
import copy
import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from .fewgood import Fetcher, duration, iso, parse_time, usage_empty, write_json
from .fewgood_creators import ROOT, UNSUPPORTED_TITLE_SCRIPT, evidence_label

RAW = ROOT / 'data/experiments/fewgood-podcast-raw.json'
RESULT = ROOT / 'data/experiments/fewgood-podcast-result.json'
USAGE = ROOT / 'data/experiments/fewgood-podcast-usage.json'
DEMO = ROOT / 'site/src/data/fewgood-podcast.json'

def topics_config(): return yaml.safe_load((ROOT / 'config/fewgood_podcast_topics.yaml').read_text())
def types_config(): return yaml.safe_load((ROOT / 'config/fewgood_podcast_content_types.yaml').read_text())
def seed_creators(): return copy.deepcopy(yaml.safe_load((ROOT / 'config/fewgood_podcast_creators.yaml').read_text()).get('creators', []))

def _text(row):
    sn=row.get('snippet',{}); return (sn.get('title','')+' '+sn.get('description','')).casefold()
def _match(text, term):
    term=str(term).casefold()
    return term in text if re.search(r'[\u4e00-\u9fff]',term) else bool(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text))
def _duration(row): return duration(row.get('contentDetails',{}).get('duration','')) or int(row.get('contentDetails',{}).get('duration_seconds') or 0)

def classify_content(row, config=None):
    config=config or types_config(); text=_text(row); title=row.get('snippet',{}).get('title','').casefold()
    signals={kind:[term for term in terms if _match(text,term)] for kind,terms in config['keywords'].items()}
    if _duration(row)>=90*60: signals['talk'].append('时长超过90分钟')
    # A title explicitly framed as an interview should not be displaced by a
    # generic word such as "deep" in the description.
    for kind in ('interview','deep_dive','talk'):
        if any(_match(title,x) for x in config['keywords'][kind]): return kind, list(dict.fromkeys(signals[kind]))
    kind=max(('interview','deep_dive','talk'),key=lambda x:len(signals[x]))
    return kind, list(dict.fromkeys(signals[kind] or ['节目长内容默认归为深度访谈']))

def _creator_ok(creator, reference):
    if creator.get('status') not in (None,'included'): return False
    if creator.get('official_brand'): return True
    return isinstance(creator.get('subscriber_count'),int) and creator['subscriber_count'] >= 1000 and bool(creator.get('last_upload_at'))

def _topic_match(row, topic, creator):
    # Creator curation is a hard boundary: a topical phrase in an unrelated
    # show's description must never move that episode into another theme.
    if topic['id'] not in creator.get('subtopics',[]):
        return False, None
    text=_text(row); title=row.get('snippet',{}).get('title','')
    title_terms=topic.get('title_only_include_terms',[])
    terms=[x for x in topic['include_terms'] if _match(text,x)]
    terms += [x for x in title_terms if _match(title,x) and x not in terms]
    # A single-topic curated show is substantive evidence even where episode
    # titles only name a guest. Multi-topic creators require topical wording.
    matched=bool(terms) or len(creator.get('subtopics',[])) == 1
    return matched, (terms[0] if terms else '精选频道主题归属')

def _failure(row, topic, reference, kind, types):
    sn=row.get('snippet',{}); text=_text(row); title=sn.get('title','')
    if not sn.get('publishedAt'): return 'missing_published_at'
    if row.get('status',{}).get('privacyStatus') not in (None,'public'): return 'not_public'
    sec=_duration(row)
    if sec < topic['min_duration_seconds']: return 'too_short'
    if sec > topic['max_duration_seconds']: return 'too_long'
    if UNSUPPORTED_TITLE_SCRIPT.search(title or ''): return 'unsupported_script'
    if any(_match(text,x) for x in topic.get('exclude_terms',[])+types.get('exclude_terms',[])): return 'excluded_term'
    if any(_match(title,x) for x in types.get('clickbait_terms',[])): return 'marketing_clickbait'
    days=(reference-parse_time(sn['publishedAt'])).days
    limit=topic.get('windows_days',types['windows_days']).get(kind,365)
    if days>limit: return 'type_window:'+kind

def _score(item, reference):
    row,creator,kind,signals,term=item; sn=row['snippet']; age=max(1,(reference-parse_time(sn['publishedAt'])).total_seconds()/86400)
    views=int(row.get('statistics',{}).get('viewCount',0) or 0)
    # Tuple fields are ordering signals only; no score is exposed to users.
    return (0 if term != '精选频道主题归属' else 1, age / 365, -math.log1p(views/age), row['id'])

def select(raw, mode='select'):
    config=topics_config(); types=types_config(); reference=parse_time(raw.get('data_refreshed_at',iso()))
    creators=copy.deepcopy(raw.get('creators',seed_creators()))
    cmap={c.get('channel_id'):c for c in creators if c.get('channel_id') and _creator_ok(c,reference)}
    output=[]
    for topic in config['topics']:
        eligible=[]; excluded=Counter()
        for row in raw.get('candidate_videos',[]):
            creator=cmap.get(row.get('snippet',{}).get('channelId'))
            if not creator: continue
            matched,term=_topic_match(row,topic,creator)
            if not matched: continue
            kind,signals=classify_content(row,types); fail=_failure(row,topic,reference,kind,types)
            if fail: excluded[fail]+=1; continue
            eligible.append((row,creator,kind,signals,term))
        eligible.sort(key=lambda x:_score(x,reference)); chosen=[]; counts=Counter()
        def take(rows, cap):
            for item in rows:
                cid=item[1]['channel_id']
                if len(chosen) >= config['theme']['top_n'] or counts[cid] >= config['theme']['max_per_channel_in_top']: continue
                if item[0]['id'] not in {x[0]['id'] for x in chosen}: chosen.append(item); counts[cid]+=1
        for kind,quota in types['mix'].items(): take([x for x in eligible if x[2]==kind],quota)
        for kind in ('interview','deep_dive','talk'): take([x for x in eligible if x[2]==kind],config['theme']['top_n'])
        videos=[]
        for row,creator,kind,signals,term in chosen:
            sn=row['snippet']; videos.append({'video_id':row['id'],'title':sn.get('title',''),'channel_title':sn.get('channelTitle',''),'channel_id':creator['channel_id'],'published_at':sn.get('publishedAt'),'duration_seconds':_duration(row),'view_count':int(row.get('statistics',{}).get('viewCount',0) or 0),'topic':topic['id'],'content_type':kind,'content_type_label':types['labels'][kind],'content_type_signals':signals,'sources':row.get('sources',[]),'reasons':[f'内容类型：{types["labels"][kind]}（命中：'+ '、'.join(signals)+'）',f'主题依据：{term}',f'来自精选创作者 {creator.get("name",sn.get("channelTitle",""))}（入池依据：{evidence_label(creator.get("evidence",[]))}）'],'url':'https://www.youtube.com/watch?v='+row['id'],'thumbnail':(sn.get('thumbnails',{}).get('medium') or sn.get('thumbnails',{}).get('default') or {}).get('url')})
        output.append({'id':topic['id'],'name_zh':topic['name_zh'],'definition':topic['definition'],'stats':{'eligible':len(eligible),'shown':len(videos),'mix_target':types['mix'],'mix_shown':dict(Counter(v['content_type'] for v in videos)),'excluded_by_rule':dict(excluded),'creators_in_topic':sum(topic['id'] in c.get('subtopics',[]) for c in cmap.values())},'videos':videos})
    return {'theme':config['theme'],'generated_at':raw.get('data_refreshed_at'),'data_refreshed_at':raw.get('data_refreshed_at'),'round':'podcast-1','mode':mode,'usage_summary':raw.get('usage_summary',usage_empty()),'creators':creators,'topics':output,'rules_notes':['创作者优先；无公开质量分；候选不足时宁缺毋滥。']}

def estimate():
    creators=seed_creators(); known=sum(bool(c.get('channel_id')) for c in creators); handles=len(creators)-known
    # two upload pages/channel, and at most one details batch per page
    all_channels=known+handles
    return {'endpoints':['channels(forHandle)','channels','playlistItems','videos'],'search_calls':0,'resolve_other_units_max':handles,'fetch_other_units_upper_bound':all_channels*5,'combined_other_units_upper_bound':handles+all_channels*5,'channels_known':known,'handles_to_resolve':handles,'hard_caps':{'search_calls':0,'other_units':300}}

def _save_raw(raw): write_json(RAW,raw)
def resolve(args):
    key=os.environ.get('YOUTUBE_API_KEY')
    if not key: raise RuntimeError('YOUTUBE_API_KEY is required (credential is never printed)')
    raw=json.loads(RAW.read_text()) if RAW.exists() else {'creators':seed_creators(),'candidate_videos':[]}
    f=Fetcher({'search_call_cap':0,'other_unit_cap':args.unit_cap},key)
    try:
        for creator in raw['creators']:
            if creator.get('channel_id') or not creator.get('youtube_handle'): continue
            items=f.call('channels',{'part':'snippet,statistics,contentDetails','forHandle':creator['youtube_handle']},'podcast_handle_resolve').get('items',[])
            if items: _apply_channel(creator,items[0])
            else: creator['status']='unverified'; creator['reason']='forHandle 未返回频道'
    finally:
        raw['data_refreshed_at']=iso(); raw['usage_summary']=f.usage; _save_raw(raw); write_json(USAGE,f.usage)
    print(json.dumps({'resolved':sum(bool(x.get('channel_id')) for x in raw['creators']),'search_calls':f.usage['search_calls']},ensure_ascii=False))

def _apply_channel(creator, item):
    sn=item.get('snippet',{}); st=item.get('statistics',{}); cd=item.get('contentDetails',{})
    creator.update({'channel_id':item.get('id'),'handle':sn.get('customUrl'),'subscriber_count':None if st.get('hiddenSubscriberCount') else int(st.get('subscriberCount',0) or 0),'uploads_playlist':cd.get('relatedPlaylists',{}).get('uploads'),'status':'included'})

def fetch(args):
    key=os.environ.get('YOUTUBE_API_KEY')
    if not key: raise RuntimeError('YOUTUBE_API_KEY is required (credential is never printed)')
    raw=json.loads(RAW.read_text()) if RAW.exists() else {'creators':seed_creators(),'candidate_videos':[]}; f=Fetcher({'search_call_cap':0,'other_unit_cap':args.unit_cap},key); uploads=[]
    try:
        for creator in raw['creators']:
            if not creator.get('channel_id'): continue
            items=f.call('channels',{'part':'snippet,statistics,contentDetails','id':creator['channel_id']},'podcast_channel').get('items',[])
            if not items: continue
            _apply_channel(creator,items[0]); playlist=creator.get('uploads_playlist'); token=None
            for _ in range(2):
                if not playlist: break
                page=f.call('playlistItems',{'part':'snippet,contentDetails','playlistId':playlist,'maxResults':50,**({'pageToken':token} if token else {})},'podcast_uploads')
                if not creator.get('last_upload_at') and page.get('items'):
                    creator['last_upload_at']=page['items'][0].get('snippet',{}).get('publishedAt')
                uploads += [{'id':x.get('contentDetails',{}).get('videoId'),'sources':['podcast_uploads:'+creator['name']]} for x in page.get('items',[]) if x.get('contentDetails',{}).get('videoId')]
                token=page.get('nextPageToken')
                if not token: break
        details={}
        for n in range(0,len(uploads),50):
            page=f.call('videos',{'part':'snippet,contentDetails,statistics,status','id':','.join(x['id'] for x in uploads[n:n+50])},'podcast_details')
            details.update({x['id']:x for x in page.get('items',[])})
        raw['candidate_videos']=[dict(details[x['id']],sources=x['sources']) for x in uploads if x['id'] in details]
    finally:
        raw['data_refreshed_at']=iso(); raw['usage_summary']=f.usage; _save_raw(raw); write_json(USAGE,f.usage)
    result=select(raw,'fetch'); write_json(RESULT,result); write_json(DEMO,result)

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('cmd',choices=['estimate','resolve','fetch','select']); p.add_argument('--unit-cap',type=int,default=300); a=p.parse_args(argv)
    if a.cmd=='estimate': print(json.dumps(estimate(),ensure_ascii=False)); return
    if a.cmd=='resolve': return resolve(a)
    if a.cmd=='fetch': return fetch(a)
    raw=json.loads(RAW.read_text()) if RAW.exists() else {'creators':seed_creators(),'candidate_videos':[],'data_refreshed_at':iso(),'usage_summary':usage_empty()}
    result=select(raw); write_json(RESULT,result); write_json(DEMO,result); print('select: zero API calls')
if __name__=='__main__': main()
