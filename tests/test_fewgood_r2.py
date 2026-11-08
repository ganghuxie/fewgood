import copy
import json
import pytest
from ytrec.fewgood import Fetcher
import ytrec.fewgood_creators as creators_module
from ytrec.fewgood_creators import boundary, branded_match, clickbait_signals, classify_creators, cfg, demo_result, event_tokens, evidence_label, rules, same_event, select


def select_without_clock(raw):
    result=select(raw)
    result.pop('timing',None)
    result.pop('generated_at',None)
    return result


def replay_raw(creators, videos):
    return {'data_refreshed_at':'2026-11-08T00:00:00Z','usage_summary':{},'baseline':{},'creators':creators,'candidate_videos':videos}


def upload(video_id, channel_id, channel_title, title):
    return {'id':video_id,'snippet':{'title':title,'channelId':channel_id,'channelTitle':channel_title,'publishedAt':'2026-11-07T00:00:00Z'},'contentDetails':{'duration':'PT5M'},'statistics':{},'status':{'privacyStatus':'public'}}


def creator(name, channel_id, evidence, status='included'):
    return {'name':name,'channel_id':channel_id,'lang':'en','subtopics':['ai-agents'],'evidence':evidence,'subscriber_count':10,'status':status}

def test_r2_fetcher_hard_limits_and_quota_stop():
    class Ok:
        status_code=200
        def json(self): return {'items':[]}
    seen=[]; f=Fetcher({'search_call_cap':15,'other_unit_cap':500},'not-a-key',get=lambda *a,**kw:(seen.append(1) or Ok()))
    for _ in range(15): f.call('search',{},'discover_search')
    with pytest.raises(RuntimeError): f.call('search',{},'discover_search')
    assert len(seen)==15 and 'not-a-key' not in json.dumps(f.usage)
    class Quota:
        status_code=403
        def json(self): return {'error':{'errors':[{'reason':'quotaExceeded'}]}}
    f=Fetcher({'search_call_cap':15,'other_unit_cap':500},'not-a-key',get=lambda *a,**kw:Quota())
    f.call('channels',{},'resolve_ids')
    assert f.usage['aborted_reason']=='403 quotaExceeded'
    with pytest.raises(RuntimeError): f.call('channels',{},'resolve_ids')

def test_brand_boundary_and_clickbait_rules():
    topics=cfg()['topics']
    coding=next(x for x in topics if x['id']=='ai-coding')
    assert not branded_match('ex-Cursor engineer',coding)
    assert branded_match('Cursor AI editor tutorial',coding)
    assert boundary('Claude Code agent tutorial',topics)[0]=='ai-coding'
    assert boundary('AI agent tutorial',topics)[0]=='ai-agents'
    assert len(clickbait_signals('INSANE SHOCKING AI news!!'))>=2
    assert len(clickbait_signals('AI news!!'))==1

def test_creator_admission_and_one_per_channel_relaxes():
    rule=rules(); topics=cfg()['topics']
    creators=[{'name':'small','channel_id':'a','subscriber_count':999,'evidence':['knowledge_lead'],'subtopics':['ai-models'],'status':'pending','discovered':[]},
              {'name':'known','channel_id':'b','subscriber_count':None,'evidence':['existing_registry'],'subtopics':['ai-models'],'status':'pending','discovered':[]}]
    classify_creators(creators,topics,rule)
    assert creators[0]['status']=='below_subscribers' and creators[1]['status']=='pending'
    raw={'data_refreshed_at':'2026-11-08T00:00:00Z','usage_summary':{},'baseline':{},'creators':[{'name':'C','channel_id':'c','lang':'en','subtopics':['ai-agents'],'evidence':['existing_registry'],'subscriber_count':1000,'status':'included'}], 'candidate_videos':[
      {'id':'1','snippet':{'title':'AI agent one','channelId':'c','channelTitle':'C','publishedAt':'2026-11-07T00:00:00Z'},'contentDetails':{'duration':'PT5M'},'statistics':{},'status':{'privacyStatus':'public'}},
      {'id':'2','snippet':{'title':'AI agent two','channelId':'c','channelTitle':'C','publishedAt':'2026-11-06T00:00:00Z'},'contentDetails':{'duration':'PT5M'},'statistics':{},'status':{'privacyStatus':'public'}}]}
    result=select(raw); agents=next(x for x in result['topics'] if x['id']=='ai-agents')
    assert len(agents['videos'])==2 and agents['stats']['relaxed_channel_cap']
    assert select_without_clock(raw)==select_without_clock(raw)


def test_evidence_labels_are_precise_and_bounded():
    assert evidence_label(['existing_registry'])=='原有 X→YouTube 名单'
    assert evidence_label(['x_bio_youtube_link'])=='X 资料直接链接 YouTube'
    assert evidence_label(['x_profile_plus_known_channel','x_post_lead'])=='X 认证资料 + YouTube 核验 / X 帖子线索 + YouTube 核验'
    assert evidence_label(['knowledge_lead','youtube_discovery:agentic AI','existing_registry'])=='公开线索 + YouTube 核验 / YouTube 高播放发现「agentic AI」'


def test_select_replay_creator_safeguards(monkeypatch):
    # 1/3 topical discovery uploads is insufficient; 2/3 remains in the pool.
    raw=replay_raw([
        dict(creator('one hit','one',['youtube_discovery:AI agents']),subscriber_count=1000),
        dict(creator('two hits','two',['youtube_discovery:AI agents']),subscriber_count=1000),
        dict(creator('seed','seed',['existing_registry']),subscriber_count=1000),
        dict(creator('देवनागरी','dev',['existing_registry']),subscriber_count=1000),
        dict(creator('manual','manual',['existing_registry']),subscriber_count=1000),
    ],[
        upload('o1','one','one hit','AI agent update'), upload('o2','one','one hit','cooking'), upload('o3','one','one hit','weather'),
        upload('t1','two','two hits','AI agent update'), upload('t2','two','two hits','agentic AI guide'), upload('t3','two','two hits','weather'),
        upload('s1','seed','seed','cooking'), upload('s2','seed','seed','weather'), upload('s3','seed','seed','sports'),
        upload('d1','dev','देवनागरी','नमस्ते'), upload('d2','dev','देवनागरी','समाचार'), upload('d3','dev','देवनागरी','आज'),
        upload('m1','manual','manual','AI agent update'),
    ])
    patched=copy.deepcopy(rules()); patched['manual_exclude_channel_ids']=['manual']
    monkeypatch.setattr(creators_module,'rules',lambda: patched)
    result=select(raw)
    rows={c['channel_id']:c for c in result['creators']}
    assert rows['one']['status']=='not_focused' and '1/3' in rows['one']['reason']
    assert rows['two']['status']=='included'
    assert rows['seed']['status']=='included'  # seeds bypass discovery-focus, but not language.
    assert rows['dev']['status']=='unsupported_language'
    assert rows['manual']['status']=='manual_excluded'
    agent=next(t for t in result['topics'] if t['id']=='ai-agents')
    assert agent['stats']['excluded_creators_by_rule']=={'not_focused':1,'unsupported_language':1,'manual_excluded':1}
    assert result['creator_pool']['by_status']['included']==2
    assert 'not_focused' in result['creator_pool']['by_status']


def test_distribution_uses_channel_names_and_repeat_replay_is_stable():
    raw=replay_raw([dict(creator('Readable Name','channel',['existing_registry']),subscriber_count=1000)],[
        upload('1','channel','Readable Name','AI agent one'), upload('2','channel','Readable Name','AI agent two')])
    result=select(raw)
    stats=next(t['stats'] for t in result['topics'] if t['id']=='ai-agents')
    assert stats['channel_distribution_shown']=={'Readable Name':2}
    assert select_without_clock(raw)==select_without_clock(raw)


def test_official_channels_are_exempt_but_personal_and_xbio_channels_are_not():
    raw=replay_raw([
        {'name':'Stability AI','title':'Stability AI','channel_id':'official','lang':'en','subtopics':['ai-models'],'evidence':['existing_registry'],'subscriber_count':57,'status':'included'},
        {'name':'Personal','title':'Personal','channel_id':'personal','lang':'en','subtopics':['ai-models'],'evidence':['x_bio_youtube_link'],'subscriber_count':999,'status':'included'},
        {'name':'Known','title':'Known','channel_id':'known','lang':'en','subtopics':['ai-models'],'evidence':['existing_registry'],'subscriber_count':None,'status':'included'},
    ],[])
    rows={x['channel_id']:x for x in select(raw)['creators']}
    assert rows['official']['status']=='included'
    assert rows['personal']['status']==rows['known']['status']=='below_subscribers'
    assert rows['personal']['reason']==rows['known']['reason']=='individual_below_1000'


def test_same_event_tokens_and_thresholds():
    a='ChatGPT Can Make GIFs Now (Images 2.6 Tested)'
    b='ChatGPT Images 2.6 Is Here: GIFs, Dot Upgrades & More'
    c='🚀ChatGPT Images 2.6全方位实测！'
    assert same_event(a,b)[0] and same_event(a,c)[0] and same_event(b,c)[0]
    assert not same_event('ChatGPT Just Changed A LOT AGAIN (Here’s What’s New)',b)[0]
    assert not same_event("Your Coding Agent Can't Undo Its Own Mistakes",'7 Things AI Coding Agents Get Wrong')[0]
    versions,other=event_tokens(c)
    assert versions=={'2.6'} and {'chatgpt','images'} <= other


def test_same_event_skips_and_top6_fills_slot():
    titles=['AI agent ChatGPT Can Make GIFs Now (Images 2.6 Tested)','AI agent ChatGPT Images 2.6 Is Here: GIFs, Dot Upgrades & More','AI agent 🚀ChatGPT Images 2.6全方位实测！','AI agent ChatGPT Just Changed A LOT AGAIN (Here’s What’s New)','AI agent Claude News','AI agent OpenAI Funding News','AI agent Industry Funding Update','AI agent Product Launch Briefing']
    videos=[upload(str(i),'c'+str(i),'C'+str(i),title) for i,title in enumerate(titles)]
    raw=replay_raw([dict(creator('C'+str(i),'c'+str(i),['existing_registry']),subscriber_count=1000) for i in range(len(titles))],videos)
    topic=next(t for t in select(raw)['topics'] if t['id']=='ai-agents')
    assert len(topic['videos'])==6
    assert len(topic['stats']['same_event_skipped'])>=2
    assert any('同一事件已合并' in reason for v in topic['videos'] for reason in v['reasons'])


def test_demo_output_crops_creators_to_included_public_fields():
    result={'creators':[
        {'name':'Included','lang':'en','subtopics':['ai-agents'],'evidence':['existing_registry'],
         'channel_id':'included','handle':'@included','subscriber_count':123,
         'last_upload_at':'2026-11-07T00:00:00Z','status':'included','reason':'','description':'private'},
        {'name':'Excluded','lang':'zh','subtopics':['ai-models'],'evidence':['knowledge_lead'],
         'channel_id':'excluded','handle':'@excluded','subscriber_count':456,
         'last_upload_at':None,'status':'below_subscribers','reason':'below_subscribers'},
    ], 'topics':[]}
    demo=demo_result(result)
    assert demo['creators']==[{
        'name':'Included','lang':'en','subtopics':['ai-agents'],'evidence':['existing_registry'],
        'channel_id':'included','handle':'@included','subscriber_count':123,
        'last_upload_at':'2026-11-07T00:00:00Z'}]
    assert result['creators'][0]['description']=='private'
