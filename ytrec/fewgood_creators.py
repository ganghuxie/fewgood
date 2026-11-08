"""Fewgood round 2: a bounded, creator-first YouTube experiment.

The raw file is deliberately sufficient to replay ``select`` without a key.
"""
import argparse, copy, hashlib, json, math, os, re, shutil, time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from .fewgood import Fetcher, basic_failure, duration, hit, iso, parse_time, usage_empty, write_json

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/experiments/fewgood-r2-raw.json'
RESULT = ROOT / 'data/experiments/fewgood-r2-result.json'
CREATORS = ROOT / 'data/experiments/fewgood-r2-creators.json'
USAGE = ROOT / 'data/experiments/fewgood-r2-usage.json'
DEMO = ROOT / 'site/src/data/fewgood-mvp.json'
DEMO_CREATOR_FIELDS = ('name', 'lang', 'subtopics', 'evidence', 'channel_id', 'handle', 'subscriber_count', 'last_upload_at')

def load(name): return yaml.safe_load((ROOT / 'config' / name).read_text())
def cfg(): return load('fewgood_topics.yaml')
def rules(): return load('fewgood_creator_rules.yaml')
def discovery(): return load('fewgood_discovery.yaml')
def now(): return datetime.now(timezone.utc)
def chinese(text): return bool(re.search(r'[\u4e00-\u9fff]', text or ''))
def public_id(item): return item.get('contentDetails', {}).get('videoId') or item.get('snippet', {}).get('resourceId', {}).get('videoId')
def paths(out=None):
    if not out: return RAW, RESULT, CREATORS, DEMO, USAGE
    out=Path(out); return out/'fewgood-r2-raw.json', out/'fewgood-r2-result.json', out/'fewgood-r2-creators.json', out/'fewgood-mvp.json', out/'fewgood-r2-usage.json'

def demo_result(result):
    """Return the public Demo payload without exposing the full creator records."""
    demo = copy.deepcopy(result)
    demo['creators'] = [
        {field: creator.get(field) for field in DEMO_CREATOR_FIELDS}
        for creator in result.get('creators', [])
        if creator.get('status') == 'included'
    ]
    return demo

def evidence_rank(values):
    values = values if isinstance(values, list) else [values]
    return min((0 if x in ('existing_registry','x_bio_youtube_link') else 1 if x in ('x_profile_plus_known_channel','x_post_lead') else 2) for x in values)

def normalize_channel(item, seed=None, discovered=None):
    sn, st, cd = item.get('snippet', {}), item.get('statistics', {}), item.get('contentDetails', {})
    seed = seed or {}; discovered = discovered or []
    hidden = bool(st.get('hiddenSubscriberCount'))
    try: subscribers = None if hidden else int(st.get('subscriberCount'))
    except (TypeError, ValueError): subscribers = None
    return {'name': seed.get('name') or sn.get('title',''), 'aliases': list(seed.get('aliases', [])),
      'lang': seed.get('lang') or ('zh' if chinese(sn.get('title','')+' '+sn.get('description','')) else 'en'),
      'subtopics': list(seed.get('subtopics', [])), 'evidence': list(seed.get('evidence', [])) if isinstance(seed.get('evidence'),list) else ([seed['evidence']] if seed.get('evidence') else []),
      'x': seed.get('x'), 'channel_id': item.get('id'), 'handle': sn.get('customUrl'), 'title': sn.get('title'),
      'description': sn.get('description',''), 'subscriber_count': subscribers, 'hidden_subscribers': hidden,
      'video_count': st.get('videoCount'), 'uploads_playlist': cd.get('relatedPlaylists',{}).get('uploads'),
      'discovered': discovered, 'status': 'pending', 'reason': '', 'last_upload_at': None, 'checked_at': None}

def merge_seed_channels(seeds, items, unresolved):
    byid, lookup = {}, {x.get('youtube_channel_id'):x for x in seeds if x.get('youtube_channel_id')}
    for item in items:
        seed=lookup.get(item.get('id'), {})
        row=normalize_channel(item, seed)
        old=byid.get(row['channel_id'])
        if old:
            old['aliases']=list(dict.fromkeys(old['aliases']+[row['name']]+row['aliases']))
            old['subtopics']=list(dict.fromkeys(old['subtopics']+row['subtopics']))
            old['evidence']=list(dict.fromkeys(old['evidence']+row['evidence']))
        else: byid[row['channel_id']]=row
    for seed in unresolved:
        byid['unverified:'+seed.get('name','')]= {'name':seed.get('name'),'aliases':[],'lang':seed.get('lang'),'subtopics':seed.get('subtopics',[]),'evidence':[seed.get('evidence')], 'x':seed.get('x'),'channel_id':seed.get('youtube_channel_id'),'handle':seed.get('youtube_handle'),'subscriber_count':None,'hidden_subscribers':False,'video_count':None,'last_upload_at':None,'status':'unverified','reason':'channels.list 未返回频道','checked_at':None,'discovered':[]}
    return list(byid.values())

def excluded_text(text, rule): return next((x for x in rule['exclude_patterns'] if x.lower() in (text or '').lower()), None)
def topic_match(title, topic):
    terms=topic['include_terms']; title=title or ''
    for term in terms['strong']:
        if hit(title, term): return 1,term
    for term in terms['weak']:
        if hit(title, term): return 2,term
    return None
def discovery_accept(creator, topics, rule):
    text=(creator.get('title','')+' '+creator.get('description',''))
    if excluded_text(text,rule): return False,'excluded_pattern'
    minimum=rule['discovered_min_subscribers']['zh' if creator['lang']=='zh' else 'en']
    if creator.get('subscriber_count') is None or creator['subscriber_count'] < minimum: return False,'below_subscribers'
    found=[]
    for d in creator.get('discovered',[]):
        topic=next(x for x in topics if x['id']==d['topic'])
        videos=d.get('videos',[]); matches=[v for v in videos if topic_match(v.get('snippet',{}).get('title',''),topic)]
        qualifies=len(matches)>=2 or any(topic_match(v.get('snippet',{}).get('title',''),topic) and int(v.get('statistics',{}).get('viewCount',0) or 0)>=200000 for v in videos)
        if d.get('kind')=='channel' and any(hit(text,x) for x in topic['include_terms']['strong']+rule['general_ai_terms']): qualifies=True
        if qualifies: found.append((d['topic'],d['query']))
    if not found:return False,'not_topical'
    creator['subtopics']=list(dict.fromkeys(x[0] for x in found)); creator['evidence']=['youtube_discovery:'+x[1] for x in found]
    return True,'included'

def classify_creators(creators, topics, rule):
    """Apply all non-uploads admission predicates. Per-topic discovery cap is deterministic."""
    discovered=defaultdict(list)
    for c in creators:
        if c['status']=='unverified': continue
        if c.get('discovered'):
            ok,reason=discovery_accept(c,topics,rule)
            c['status'],c['reason']=('pending',reason) if ok else (reason,reason)
            if ok:
                for t in c['subtopics']: discovered[t].append(c)
        else:
            enough=(c.get('subscriber_count') or 0)>=rule['seed_min_subscribers'] or any(x in ('existing_registry','x_bio_youtube_link') for x in c['evidence'])
            c['status'],c['reason']=('pending','seed_verified') if enough else ('below_subscribers','below_subscribers')
    for tid, rows in discovered.items():
        for c in sorted(rows,key=lambda x: (-(x.get('subscriber_count') or 0),x['channel_id']))[rule['max_discovered_per_topic']:]:
            c['subtopics'].remove(tid)
            if not c['subtopics']: c['status']=c['reason']='over_cap'
    return creators

def boundary(title, topics):
    t=(title or '').lower()
    cursor_ok=bool(re.search(r'\bcursor\b',t)) and (bool(re.search(r'\b(ai|editor|ide|agent|coding|code)\b',t)))
    if any(x in t for x in ('coding agent','claude code','codex','vibe coding','build an app','build a full')) or cursor_ok: return 'ai-coding','含编程 Agent 信号 → AI 编程'
    if any(x in t for x in ('agent','agents','agentic','智能体','mcp')): return 'ai-agents','含 Agent 信号 → AI Agent'
    if any(x in t for x in ('news','funding','ipo','earnings','bubble','data center','policy','regulation','新闻','融资')) and not any(x in t for x in ('stock to buy','price target','market update','美股','股票')): return 'ai-industry','含产业动态信号 → AI 产业动态'
    matches=[(topic_match(title,x),x['id']) for x in topics if topic_match(title,x)]
    return (min(matches,key=lambda x:x[0][0])[1],None) if matches else (None,None)

def branded_match(title, topic, creator_title=''):
    # remove former/ex brand references before standard topic matching
    filtered=re.sub(r'\b(ex-|former\s+|前\s*)('+'|'.join(rules()['brands'])+r')\b','',title or '',flags=re.I)
    if re.search(r'\bcursor\b',filtered,re.I) and not (re.search(r'\b(ai|editor|ide|agent|coding|code)\b',filtered,re.I) or 'cursor' in (creator_title or '').lower()):
        filtered=re.sub(r'\bcursor\b','',filtered,flags=re.I)
    return topic_match(filtered,topic)

EVIDENCE_LABELS={
    'existing_registry':'原有 X→YouTube 名单',
    'x_bio_youtube_link':'X 资料直接链接 YouTube',
    'x_profile_plus_known_channel':'X 认证资料 + YouTube 核验',
    'x_post_lead':'X 帖子线索 + YouTube 核验',
    'knowledge_lead':'公开线索 + YouTube 核验',
}
UNSUPPORTED_TITLE_SCRIPT=re.compile(r'[\u0900-\u097F\u0600-\u06FF\u0E00-\u0E7F\uAC00-\uD7AF]')

def evidence_label(evidence):
    """Human-readable, bounded provenance for a selected creator."""
    labels=[]
    for item in evidence or []:
        item=str(item)
        label=('YouTube 高播放发现「'+item.split(':',1)[1]+'」') if item.startswith('youtube_discovery:') else EVIDENCE_LABELS.get(item,item)
        if label not in labels: labels.append(label)
    return ' / '.join(labels[:2]) or '未知'

def discovery_only(creator):
    evidence=creator.get('evidence') or []
    return bool(evidence) and all(str(item).startswith('youtube_discovery:') for item in evidence)

def replay_creator_rules(creators, candidate_videos, topics, rule):
    """Re-evaluate select-only safeguards from saved uploads; makes no API calls."""
    uploads=defaultdict(list)
    for row in candidate_videos:
        uploads[row.get('snippet',{}).get('channelId')].append(row.get('snippet',{}).get('title',''))
    manual=set(rule.get('manual_exclude_channel_ids',[]))
    statuses=('not_focused','unsupported_language','manual_excluded')
    for creator in creators:
        if creator.get('status')!='included': continue
        cid=creator.get('channel_id'); titles=uploads.get(cid,[])
        if cid in manual:
            creator['status']=creator['reason']='manual_excluded'
        elif titles and sum(bool(UNSUPPORTED_TITLE_SCRIPT.search(title or '')) for title in titles)/len(titles) >= rule.get('unsupported_language_min_ratio',.5):
            creator['status']='unsupported_language'
            creator['reason']=f"不支持文字标题 {sum(bool(UNSUPPORTED_TITLE_SCRIPT.search(title or '')) for title in titles)}/{len(titles)}"
        elif discovery_only(creator):
            matched=sum(any(branded_match(title,topic,creator.get('title','')) for topic in topics) for title in titles)
            minimum=rule.get('discovery_focus_min_videos',3); ratio=rule.get('discovery_focus_min_ratio',.4)
            if len(titles)<minimum or matched/len(titles) < ratio:
                creator['status']='not_focused'
                creator['reason']=f"主题标题命中 {matched}/{len(titles)}（要求至少 {minimum} 条且比例 ≥ {ratio:g}）"
    return statuses
def clickbait_signals(title):
    title=title or ''; r=rules(); found=[]
    caps=[w for w in re.findall(r'\b[A-Z]{4,}\b',title) if w not in {'LLM','GPT','API','MCP','AGI','IDE','NVIDIA','OPENAI'}]
    if len(caps)>=2: found.append('多个全大写词')
    found += [x for x in r['clickbait_terms'] if x.lower() in title.lower()]
    if '!!' in title or '??' in title or '！！' in title: found.append('夸张标点')
    if sum(title.count(x) for x in '😱🤯😳🔥')>=2: found.append('多个 emoji')
    return list(dict.fromkeys(found))

def select(raw, mode='select'):
    started=time.monotonic()
    topics=cfg()['topics']; rule=rules(); reference=parse_time(raw.get('data_refreshed_at',iso())); creators=copy.deepcopy(raw.get('creators',[]))
    new_exclusion_statuses=replay_creator_rules(creators,raw.get('candidate_videos',[]),topics,rule)
    creator_map={c.get('channel_id'):c for c in creators if c.get('status')=='included'}
    out=[]
    for topic in topics:
        candidates=[]; excluded=Counter(); tier_counts=Counter()
        for row in raw.get('candidate_videos',[]):
            sn=row.get('snippet',{}); creator=creator_map.get(sn.get('channelId'))
            if not creator: continue
            match=branded_match(sn.get('title',''),topic,creator.get('title',''))
            if match: tier_counts[match[0]]+=1
            assigned,why=boundary(sn.get('title',''),topics)
            if assigned!=topic['id'] or not match: continue
            fail=basic_failure(row,topic,reference)
            if fail: excluded[fail]+=1; continue
            if topic['id'] not in creator['subtopics'] and match[0]!=1: excluded['creator_not_topic_tier2']+=1; continue
            signals=clickbait_signals(sn.get('title',''))
            if len(signals)>=2: excluded['clickbait']+=1; continue
            candidates.append((row,creator,match,signals,why))
        candidates.sort(key=lambda x:(bool(x[3]), topic['id'] not in x[1]['subtopics'],x[2][0],evidence_rank(x[1]['evidence']),-parse_time(x[0]['snippet'].get('publishedAt','')).timestamp(),x[0].get('id','')))
        def take(cap):
            show=[]; counts=Counter()
            for x in candidates:
                cid=x[1]['channel_id']
                if counts[cid]>=cap: continue
                counts[cid]+=1; show.append(x)
                if len(show)==6: break
            return show,counts
        shown,dist=take(1); relaxed=False
        if len(shown)<6: shown,dist=take(2); relaxed=True
        videos=[]
        for row,c,m,signals,why in shown:
            sn=row['snippet']; sec=duration(row.get('contentDetails',{}).get('duration','')) or 0; days=max(0,(reference-parse_time(sn.get('publishedAt',''))).days)
            evidence=evidence_label(c['evidence'])
            reasons=[f'来自精选博主 {c["name"]}（入池依据：{evidence}；'+('本主题博主）' if topic['id'] in c['subtopics'] else '标题 tier1 跨主题）'),f'标题含关键词「{m[1]}」']
            if why: reasons.append('边界规则：'+why)
            if signals: reasons.append('标题含营销/夸张信号：'+ '、'.join(signals)+'，已降权')
            reasons += [f'发布于 {sn.get("publishedAt","")[:10]}（{days} 天前）',f'时长 {sec//60}:{sec%60:02d}',f'订阅数 {c.get("subscriber_count") if c.get("subscriber_count") is not None else "未知"}（入池时）']
            videos.append({'video_id':row['id'],'title':sn.get('title',''),'channel_title':sn.get('channelTitle',''),'channel_id':c['channel_id'],'published_at':sn.get('publishedAt'),'duration_seconds':sec,'view_count':int(row.get('statistics',{}).get('viewCount',0) or 0),'topic':topic['id'],'sources':['creator_uploads:'+c['name']],'reasons':reasons,'url':'https://www.youtube.com/watch?v='+row['id'],'thumbnail':(sn.get('thumbnails',{}).get('medium') or sn.get('thumbnails',{}).get('default') or {}).get('url')})
        in_topic=[c for c in creator_map.values() if topic['id'] in c['subtopics']]
        shown_by_name=Counter()
        for cid,count in dist.items(): shown_by_name[creator_map[cid].get('name') or cid]+=count
        excluded_creators=Counter(c['status'] for c in creators if topic['id'] in c.get('subtopics',[]) and c.get('status') in new_exclusion_statuses)
        out.append({'id':topic['id'],'name_zh':topic['name_zh'],'definition':topic['definition'],'stats':{'creators_in_topic':len(in_topic),'candidates_from_creators':sum(1 for r in raw.get('candidate_videos',[]) if r.get('snippet',{}).get('channelId') in creator_map),'matched_tier1':tier_counts[1],'matched_tier2':tier_counts[2],'matched_tier3':tier_counts[3],'matched':sum(tier_counts.values()),'eligible':len(candidates),'shown':len(videos),'excluded_by_rule':dict(excluded),'excluded_creators_by_rule':dict(excluded_creators),'channel_distribution_shown':dict(shown_by_name),'relaxed_channel_cap':relaxed},'videos':videos})
    baseline={}
    for tid,rows in raw.get('baseline',{}).items():
        baseline[tid]=[{'rank':i,'video_id':r.get('id'),'title':r.get('snippet',{}).get('title',''),'channel_title':r.get('snippet',{}).get('channelTitle',''),'published_at':r.get('snippet',{}).get('publishedAt'),'duration_seconds':duration(r.get('contentDetails',{}).get('duration','')),'view_count':int(r.get('statistics',{}).get('viewCount',0) or 0),'url':'https://www.youtube.com/watch?v='+r.get('id',''),'reused_from_round1':True,'also_in_fewgood_topN':any(r.get('id')==v['video_id'] for t in out for v in t['videos'])} for i,r in enumerate(rows[:6],1)]
    pool={'by_topic':{t['id']:sum(c['status']=='included' and t['id'] in c.get('subtopics',[]) for c in creators) for t in topics},'by_lang':dict(Counter(c.get('lang') for c in creators if c.get('status')=='included')),'by_evidence':dict(Counter(e for c in creators if c.get('status')=='included' for e in c.get('evidence',[]))),'by_status':dict(Counter(c.get('status') for c in creators)),'examples':[c['name'] for c in creators if c.get('status')=='included'][:10]}
    timing=dict(raw.get('timing',{})); timing['select_seconds']=round(time.monotonic()-started,6)
    return {'generated_at':raw.get('data_refreshed_at'),'data_refreshed_at':raw.get('data_refreshed_at'),'round':2,'mode':mode,'usage_summary':raw.get('usage_summary',usage_empty()),'timing':timing,'creator_pool':pool,'creators':[{k:v for k,v in c.items() if k not in ('description','discovered','uploads_playlist')} for c in creators],'topics':out,'baseline':baseline,'rules_notes':['博主优先：候选只来自已入池频道 uploads；播放量与订阅数不参与排序。']}

def write_creators_config(creators):
    included=[]
    for c in creators:
      if c.get('status')=='included':
        included.append({'name':c.get('name'),'channel_id':c.get('channel_id'),'handle':c.get('handle'),'lang':c.get('lang'),'subtopics':c.get('subtopics',[]),'evidence':c.get('evidence',[]),'subscriber_count_at_check':c.get('subscriber_count'),'checked_at':c.get('checked_at')})
    (ROOT/'config/fewgood_creators.yaml').write_text(yaml.safe_dump({'creators':included},allow_unicode=True,sort_keys=False))

def run(args):
    topics,seedcfg,rule=cfg()['topics'],load('fewgood_creator_seeds.yaml')['seeds'],rules(); disc=discovery()
    ids=[x for x in seedcfg if x.get('youtube_channel_id')]; handles=[x for x in seedcfg if not x.get('youtube_channel_id') and x.get('youtube_handle')]
    search=len(disc['video_queries'])+len(disc['channel_queries']); estimate=math.ceil(len(ids)/50)+len(handles)+search+math.ceil(search*50/50)*2+len(seedcfg)+math.ceil(len(seedcfg)*50/50)
    if args.dry_run:
        print(json.dumps({'search_calls':search,'other_units_upper_bound':estimate,'seed_id_batches':math.ceil(len(ids)/50),'handle_calls':len(handles),'uploads_upper_bound':len(seedcfg)},ensure_ascii=False)); return
    key=os.environ.get('YOUTUBE_API_KEY')
    if not key: raise RuntimeError('YOUTUBE_API_KEY is required (credential is never printed)')
    f=Fetcher({**cfg(),'other_unit_cap':500},key); items=[]; unresolved=[]; started=time.monotonic()
    try:
      for i in range(0,len(ids),50):
        resp=f.call('channels',{'part':'snippet,statistics,contentDetails','id':','.join(x['youtube_channel_id'] for x in ids[i:i+50])},'resolve_ids'); items+=resp.get('items',[])
      found_ids={x.get('id') for x in items}; unresolved += [x for x in ids if x['youtube_channel_id'] not in found_ids]
      handle_items=[]
      for s in handles:
        resp=f.call('channels',{'part':'snippet,statistics,contentDetails','forHandle':'@'+s['youtube_handle']},'resolve_handle'); got=resp.get('items',[]); handle_items += [(x,s) for x in got]; unresolved += ([] if got else [s])
      creators=merge_seed_channels(seedcfg,items,unresolved)
      # ``forHandle`` responses need their original seed metadata too.
      for item,s in handle_items:
        row=normalize_channel(item,s); old=next((x for x in creators if x.get('channel_id')==row['channel_id']),None)
        if old:
          old['aliases']=list(dict.fromkeys(old['aliases']+[row['name']])); old['subtopics']=list(dict.fromkeys(old['subtopics']+row['subtopics'])); old['evidence']=list(dict.fromkeys(old['evidence']+row['evidence']))
        else: creators.append(row)
      seed_ids={c.get('channel_id') for c in creators if c.get('channel_id')}
      dmap=defaultdict(list); videos=[]
      for q in disc['video_queries']:
        r=f.call('search',{'part':'snippet','type':'video','order':'viewCount','publishedAfter':(now()-timedelta(days=90)).isoformat().replace('+00:00','Z'),'maxResults':50,'relevanceLanguage':'zh-Hans' if q['lang']=='zh' else 'en','q':q['query']},'discover_search');
        for x in r.get('items',[]):
          cid=x.get('snippet',{}).get('channelId'); vid=x.get('id',{}).get('videoId');
          if cid and cid not in seed_ids:
            event=next((z for z in dmap[cid] if z['topic']==q['topic'] and z['query']==q['query'] and z['kind']=='video'),None)
            if not event: event={'topic':q['topic'],'query':q['query'],'kind':'video','videos':[]}; dmap[cid].append(event)
            event['videos'].append({'id':vid,'snippet':x.get('snippet',{})})
          if vid: videos.append({'id':vid,'snippet':x.get('snippet',{})})
      for q in disc['channel_queries']:
        r=f.call('search',{'part':'snippet','type':'channel','order':'relevance','relevanceLanguage':'zh-Hans','maxResults':50,'q':q['query']},'discover_search')
        for x in r.get('items',[]):
          cid=x.get('id',{}).get('channelId');
          if cid and cid not in seed_ids:dmap[cid].append({'topic':q['topic'],'query':q['query'],'kind':'channel','videos':[]})
      detailvid={}
      for i in range(0,len(videos),50):
        r=f.call('videos',{'part':'statistics,snippet','id':','.join(x['id'] for x in videos[i:i+50])},'discover_video_stats'); detailvid.update({x['id']:x for x in r.get('items',[])})
      for ds in dmap.values():
        for d in ds:
          d['videos']=[detailvid.get(x['id'],x) for x in d['videos']]
      for batch in [list(dmap)[i:i+50] for i in range(0,len(dmap),50)]:
        r=f.call('channels',{'part':'snippet,statistics,contentDetails','id':','.join(batch)},'discover_channel_stats')
        for x in r.get('items',[]): creators.append(normalize_channel(x,discovered=dmap[x['id']]))
      classify_creators(creators,topics,rule)
      pending=[c for c in creators if c['status']=='pending']
      candidates=[]
      for c in pending:
        playlist=c.get('uploads_playlist') or ('UU'+c['channel_id'][2:]); r=f.call('playlistItems',{'part':'snippet,contentDetails','playlistId':playlist,'maxResults':50},'uploads'); uploads=r.get('items',[]); dates=[x.get('contentDetails',{}).get('videoPublishedAt') or x.get('snippet',{}).get('publishedAt') for x in uploads]; c['last_upload_at']=max(dates,default=None); c['checked_at']=iso()
        if not c['last_upload_at'] or parse_time(c['last_upload_at'])<now()-timedelta(days=rule['active_within_days']): c['status']=c['reason']='inactive'; continue
        c['status']=c['reason']='included'
        candidates += [{'id':public_id(x),'snippet':x.get('snippet',{}),'contentDetails':x.get('contentDetails',{})} for x in uploads if public_id(x) and parse_time(x.get('contentDetails',{}).get('videoPublishedAt') or x.get('snippet',{}).get('publishedAt',''))>=now()-timedelta(days=30)]
      details={}
      for i in range(0,len(candidates),50):
        r=f.call('videos',{'part':'snippet,contentDetails,statistics,status','id':','.join(x['id'] for x in candidates[i:i+50])},'details'); details.update({x['id']:x for x in r.get('items',[])})
      candidates=[details.get(x['id'],x) for x in candidates]
    except RuntimeError as e: f.usage['aborted_reason']=str(e); creators=locals().get('creators',[]); candidates=locals().get('candidates',[])
    r1=json.loads((ROOT/'data/experiments/fewgood-mvp-raw.json').read_text()) if (ROOT/'data/experiments/fewgood-mvp-raw.json').exists() else {}
    raw={'data_refreshed_at':iso(),'creators':creators,'candidate_videos':candidates,'baseline':r1.get('baseline',{}),'usage_summary':f.usage,'timing':{'collect_seconds':round(time.monotonic()-started,6)}}
    rp,xp,cp,dp,up=paths(args.output_dir); write_json(rp,raw);write_json(up,f.usage);write_json(cp,creators);result=select(raw,'run');write_json(xp,result);write_json(dp,demo_result(result))
    if not args.output_dir:
      write_creators_config(creators)
      r1=ROOT/'data/experiments/fewgood-mvp-result.json'
      if r1.exists(): shutil.copyfile(r1,ROOT/'site/src/data/fewgood-mvp-r1.json')

def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('cmd',choices=['run','select']);p.add_argument('--dry-run',action='store_true');p.add_argument('--output-dir',type=Path);a=p.parse_args(argv); rp,xp,cp,dp,up=paths(a.output_dir)
 if a.cmd=='run': return run(a)
 if not rp.exists(): raise RuntimeError('No saved round 2 raw data')
 result=select(json.loads(rp.read_text()));write_json(xp,result);write_json(dp,demo_result(result))
 if not a.output_dir: write_creators_config(result['creators'])
 r1=ROOT/'data/experiments/fewgood-mvp-result.json'; r1demo=ROOT/'site/src/data/fewgood-mvp-r1.json'
 if r1.exists() and not a.output_dir: shutil.copyfile(r1,r1demo)
 print('select: zero API calls')
if __name__=='__main__': main()
