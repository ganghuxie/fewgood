"""Fewgood R3: offline rule classification and uploads-only collection.

The collector deliberately has no discovery endpoint: it resolves known channels,
walks their upload playlists, and obtains video details in batches.
"""
import argparse, copy, json, math, os, re, time
from collections import Counter
from datetime import timedelta
from pathlib import Path

import yaml

from .fewgood import Fetcher, duration, iso, merge, parse_time, usage_empty, write_json
from .fewgood_creators import ROOT, basic_failure, boundary, branded_match, clickbait_signals, cfg, evidence_label, replay_subscriber_rule, same_event

R2_RAW = ROOT / 'data/experiments/fewgood-r2-raw.json'
RAW = ROOT / 'data/experiments/fewgood-r3-raw.json'
RESULT = ROOT / 'data/experiments/fewgood-r3-result.json'
USAGE = ROOT / 'data/experiments/fewgood-r3-usage.json'
DEMO = ROOT / 'site/src/data/fewgood-mvp.json'

def types_config():
    return yaml.safe_load((ROOT / 'config/fewgood_content_types.yaml').read_text())

def _text(row):
    sn=row.get('snippet', {})
    return (sn.get('title','') + ' ' + sn.get('description','')).casefold()

def _matches(text, term):
    # Config permits a deliberately small regex set (e.g. "how .* works").
    term=term.casefold()
    if '.*' in term: return bool(re.search(term, text))
    # Unicode word-boundaries treat adjacent CJK characters as one word, which
    # would miss 新手教學 and 底层原理; Latin phrases still need word boundaries.
    if re.search(r'[\u4e00-\u9fff]', term): return term in text
    return bool(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)', text))

def classify_content(row, config=None):
    """Return ``(type, matched_signals)``; ties prefer tutorial, then explainer."""
    config=config or types_config(); text=_text(row); sn=row.get('snippet', {})
    title=(sn.get('title','') or '').casefold()
    title_only=set(config.get('title_only',[]))
    signals={kind:[term for term in terms if _matches(title if kind in title_only else text, str(term))]
             for kind,terms in config['keywords'].items()}
    channel=(sn.get('channelTitle','') or '').casefold()
    for kind,names in config.get('channel_hints',{}).items():
        for name in names:
            if str(name).casefold() in channel: signals[kind].append('频道倾向:'+str(name))
    # Conference uploads commonly use "Topic - Speaker, Company" rather
    # than saying keynote explicitly.
    if re.search(r'\s[-—]\s[^,]{2,},\s*[^,]{2,}', sn.get('title','')):
        signals['talk'].append('标题“主题 - 嘉宾, 公司”格式')
    sec=duration(row.get('contentDetails',{}).get('duration','')) or row.get('contentDetails',{}).get('duration_seconds') or 0
    if sec > 45*60: signals['talk'].append('时长超过45分钟')
    news_signal=next((term for term in config.get('news_or_update_terms',[]) if _matches(title, str(term))),None)
    # News/update labels keep their default explainer classification even if a
    # channel description happens to contain an instructional phrase.
    if news_signal:
        signals['explainer'].append('新闻/更新优先:'+str(news_signal))
        return 'explainer', list(dict.fromkeys(signals['explainer']))
    # Explicit instructional language takes precedence over a conference host.
    order=('tutorial','explainer','talk')
    kind=max(order, key=lambda x:(len(signals[x]), -order.index(x)))
    if not signals[kind]: kind='explainer'; signals[kind]=['默认：非使用导向的更新/新闻按新技术解读']
    return kind, list(dict.fromkeys(signals[kind]))

def known_talk(row, creator, config=None):
    config=config or types_config(); allowed=config['talk_whitelist']['channels']; sn=row.get('snippet',{})
    cid=sn.get('channelId') or creator.get('channel_id'); name=(sn.get('channelTitle') or creator.get('name') or '').casefold()
    listed=any((x.get('channel_id') and x['channel_id']==cid) or x['name'].casefold()==name for x in allowed)
    return listed or (creator.get('subscriber_count') or 0) >= config['talk_subscriber_minimum']

def window_failure(row, creator, reference, content_type, config=None):
    config=config or types_config(); days=(reference-parse_time(row.get('snippet',{}).get('publishedAt',''))).days
    limit=config['windows_days'][content_type]
    if content_type == 'talk' and not known_talk(row, creator, config): limit=config['windows_days']['tutorial']
    return None if days <= limit else 'type_window:'+content_type

def creator_records(raw):
    """Use saved R2 facts, then add declared R3 creators without overwriting facts."""
    rows={c.get('channel_id'):copy.deepcopy(c) for c in raw.get('creators',[]) if c.get('channel_id')}
    for seed in yaml.safe_load((ROOT/'config/fewgood_creators.yaml').read_text()).get('creators',[]):
        cid=seed['channel_id']; row=rows.setdefault(cid, {'channel_id':cid,'status':'included'})
        # Configured Group-C evidence is an explicit manual curation decision;
        # retain it when a replayed R2 record already exists.
        for key,value in seed.items():
            if key in ('evidence','subtopics'):
                row[key]=list(dict.fromkeys(row.get(key,[])+value))
            else:
                row.setdefault(key, value)
        row.setdefault('subscriber_count', seed.get('subscriber_count_at_check'))
        row.setdefault('status','included'); row.setdefault('evidence',[])
    return list(rows.values())

def _candidate_score(item, reference):
    row, creator, match, kind, signals, why=item
    published=parse_time(row['snippet'].get('publishedAt',''))
    age_days=max(1, (reference-published).total_seconds()/86400)
    views=int(row.get('statistics',{}).get('viewCount',0) or 0)
    # Log keeps an outlier from dominating while still making demonstrated
    # viewer interest the ordering signal inside an equally suitable tier.
    quality=math.log1p(views/age_days)
    return (bool(clickbait_signals(row.get('snippet',{}).get('title',''))),
            _audience_preference_rank(row, kind), match[0], -quality,
            -published.timestamp(), row['id'])

def _audience_preference_rank(row, kind):
    """Return a title-only, topic-agnostic learner-fit tier (lower is better).

    This is deliberately a coarse ordering tier, not a displayed quality score:
    practical beginner instruction and plain-language explanation outrank a
    lifestyle pitch or highly specialised engineering talk before views/day is
    used.  It neither excludes the latter nor relies on manual C-group IDs.
    """
    title=(row.get('snippet',{}).get('title','') or '').casefold()
    beginner=(
        'beginner', 'newbie', 'new user', '新手', '入門', '入门', '不用寫程式',
        '不用写程序', 'no coding', 'zero coding', 'build your first', '第一個',
        '第一个', 'clearly explained', 'simply explained', 'plain english',
        '給爸媽', '给爸妈', "anyone's mom",
    )
    specialised=(
        'graph engineering', 'harness engineering', 'agent harness', 'langgraph',
        'framework', 'production infrastructure', 'evals', 'mission critical',
        'interrupt london', 'conference', 'keynote',
    )
    lifestyle=('every part of your life', 'life coach', 'personal brand', 'make money')
    if any(term in title for term in specialised): return 3
    if any(term in title for term in lifestyle): return 2
    if any(term in title for term in beginner): return 0
    # A tutorial's explicit instructional classification still makes it more
    # useful than an otherwise neutral clip, but is weaker than beginner cues.
    return 1

def select(raw, mode='select'):
    reference=parse_time(raw.get('data_refreshed_at',iso())); topics=cfg()['topics']; types=types_config()
    creators=creator_records(raw); replay_subscriber_rule(creators, yaml.safe_load((ROOT/'config/fewgood_creator_rules.yaml').read_text()))
    cmap={c['channel_id']:c for c in creators if c.get('status')=='included'}; output=[]
    candidates=merge(raw.get('candidate_videos', raw.get('candidates',[])))
    for topic in topics:
        eligible=[]; excluded=Counter()
        for row in candidates:
            creator=cmap.get(row.get('snippet',{}).get('channelId'))
            if not creator: continue
            match=branded_match(row.get('snippet',{}).get('title',''),topic,creator.get('title',''))
            assigned,why=boundary(row.get('snippet',{}).get('title',''),topics)
            if not match or assigned != topic['id']: continue
            kind,signals=classify_content(row,types)
            # R3 applies the content-type window below; do not reject an
            # explainer/talk first using the topic's generic 30-day window.
            fail=basic_failure(row,topic,reference,check_published_within=False)
            if fail: excluded[fail]+=1; continue
            fail=window_failure(row,creator,reference,kind,types)
            if fail: excluded[fail]+=1; continue
            if topic['id'] not in creator.get('subtopics',[]) and match[0]!=1: excluded['creator_not_topic_tier2']+=1; continue
            eligible.append((row,creator,match,kind,signals,why))
        eligible.sort(key=lambda item:_candidate_score(item,reference))
        chosen=[]; used=set(); skipped=[]
        def take(rows, cap):
            for item in rows:
                row,creator,*_=item; cid=creator['channel_id']
                if cid in used or len(chosen)>=6: continue
                duplicate=next(((x,same_event(row['snippet'].get('title',''),x[0]['snippet'].get('title',''))) for x in chosen if same_event(row['snippet'].get('title',''),x[0]['snippet'].get('title',''))[0]),None)
                if duplicate: skipped.append({'skipped':row['id'],'kept':duplicate[0][0]['id'],'shared_tokens':duplicate[1][1]}); continue
                chosen.append(item); used.add(cid)
        for kind,quota in types['mix'].items(): take([x for x in eligible if x[3]==kind][:quota], 1)
        # Preserve the mix cap while candidates of the more useful types
        # remain.  Talks only fill after tutorial and explainer candidates.
        for kind in ('tutorial','explainer','talk'):
            take([x for x in eligible if x[3]==kind], 6)
        take(eligible,6)  # future-proof fallback for new content types
        videos=[]
        for row,creator,match,kind,signals,why in chosen:
            sn=row['snippet']; sec=duration(row.get('contentDetails',{}).get('duration','')) or 0
            reasons=[f'内容类型：{kind}（命中：'+'、'.join(signals)+'）', f'标题含关键词「{match[1]}」', f'来自精选博主 {creator.get("name",sn.get("channelTitle",""))}（入池依据：{evidence_label(creator.get("evidence",[]))}）']
            if why: reasons.append('边界规则：'+why)
            videos.append({'video_id':row['id'],'title':sn.get('title',''),'channel_title':sn.get('channelTitle',''),'channel_id':creator['channel_id'],'published_at':sn.get('publishedAt'),'duration_seconds':sec,'view_count':int(row.get('statistics',{}).get('viewCount',0) or 0),'topic':topic['id'],'content_type':kind,'content_type_signals':signals,'sources':row.get('sources',[]),'reasons':reasons,'url':'https://www.youtube.com/watch?v='+row['id'],'thumbnail':(sn.get('thumbnails',{}).get('medium') or sn.get('thumbnails',{}).get('default') or {}).get('url')})
        output.append({'id':topic['id'],'name_zh':topic['name_zh'],'definition':topic['definition'],'stats':{'eligible':len(eligible),'shown':len(videos),'mix_target':types['mix'],'mix_shown':dict(Counter(v['content_type'] for v in videos)),'excluded_by_rule':dict(excluded),'same_event_skipped':skipped,'creators_in_topic':sum(topic['id'] in c.get('subtopics',[]) for c in cmap.values())},'videos':videos})
    return {'generated_at':raw.get('data_refreshed_at'),'data_refreshed_at':raw.get('data_refreshed_at'),'round':3,'mode':mode,'usage_summary':raw.get('usage_summary',usage_empty()),'creators':creators,'topics':output,'baseline':raw.get('baseline',{}),'rules_notes':['R3：教程30天、解读180天、知名讲座最多730天；新闻/更新标题一律归新技术解读。']}

def fetch_targets():
    """New Group-C tutorial creators plus known long-window authorities only."""
    seeds=yaml.safe_load((ROOT/'config/fewgood_creators.yaml').read_text()).get('creators',[])
    base=json.loads(R2_RAW.read_text()) if R2_RAW.exists() else {}
    allowed=types_config()['talk_whitelist']['channels']
    all_rows=seeds + base.get('creators',[])
    selected=[]
    for row in all_rows:
        name=(row.get('name') or '').casefold(); cid=row.get('channel_id')
        group_c='group_c_reference' in row.get('evidence',[])
        whitelist=any((x.get('channel_id') and x['channel_id']==cid) or x['name'].casefold()==name for x in allowed)
        if cid and (group_c or whitelist) and cid not in {x['channel_id'] for x in selected}: selected.append(row)
    return selected

def estimate():
    channels=fetch_targets()
    # channels + two playlist pages each + conservative detail batches
    return {'endpoints':['channels','playlistItems','videos'],'channels':len(channels),'playlist_pages_max':len(channels)*2,'videos_batches_max':len(channels)*2,'units_upper_bound':len(channels)*5}

def fetch(args):
    plan=estimate()
    if args.estimate: print(json.dumps(plan,ensure_ascii=False)); return
    key=os.environ.get('YOUTUBE_API_KEY')
    if not key: raise RuntimeError('YOUTUBE_API_KEY is required (credential is never printed)')
    base=json.loads(R2_RAW.read_text()); seeds=fetch_targets()
    f=Fetcher({'search_call_cap':0,'other_unit_cap':args.unit_cap},key); rows=[]; started=time.monotonic()
    try:
        for seed in seeds:
            ch=f.call('channels',{'part':'contentDetails,statistics,snippet','id':seed['channel_id']},'r3_channel').get('items',[])
            if not ch: continue
            channel=ch[0]; playlist=channel.get('contentDetails',{}).get('relatedPlaylists',{}).get('uploads')
            token=None
            for _ in range(2):
                if not playlist: break
                response=f.call('playlistItems',{'part':'snippet,contentDetails','playlistId':playlist,'maxResults':50,**({'pageToken':token} if token else {})},'r3_uploads')
                rows += [{'id':x.get('contentDetails',{}).get('videoId'),'sources':['r3_uploads:'+seed['name']]} for x in response.get('items',[]) if x.get('contentDetails',{}).get('videoId')]
                token=response.get('nextPageToken')
                if not token: break
        details={}
        for n in range(0,len(rows),50):
            response=f.call('videos',{'part':'snippet,contentDetails,statistics,status,player','id':','.join(x['id'] for x in rows[n:n+50])},'r3_details')
            details.update({x['id']:x for x in response.get('items',[])})
        base['candidate_videos']=merge(base.get('candidate_videos',[])+[dict(details[x['id']],sources=x['sources']) for x in rows if x['id'] in details])
    finally:
        base['data_refreshed_at']=iso(); base['usage_summary']=f.usage; base.setdefault('timing',{})['collect_seconds']=round(time.monotonic()-started,6)
        write_json(RAW,base); write_json(USAGE,f.usage)
    result=select(base,'fetch'); write_json(RESULT,result); write_json(DEMO,result)

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('cmd',choices=['fetch','select']); p.add_argument('--estimate',action='store_true'); p.add_argument('--unit-cap',type=int,default=250); a=p.parse_args(argv)
    if a.cmd=='fetch': return fetch(a)
    raw=json.loads(RAW.read_text()); result=select(raw); write_json(RESULT,result); write_json(DEMO,result); print('select: zero API calls')
if __name__=='__main__': main()
