import inspect
from datetime import datetime, timezone
from pathlib import Path

import yaml
from ytrec.fewgood_creators import boundary
from ytrec.fewgood_r3 import _candidate_score, classify_content, creator_records, estimate, select, types_config, window_failure
from ytrec.fewgood_creators import cfg


NOW = '2026-11-08T00:00:00Z'

def video(identifier, channel, title, published='2026-11-01T00:00:00Z', minutes=10, description=''):
    return {'id':identifier, 'snippet':{'channelId':channel,'channelTitle':channel,'title':title,'description':description,'publishedAt':published}, 'contentDetails':{'duration':f'PT{minutes}M'}, 'statistics':{}, 'status':{'privacyStatus':'public'}}

def creator(channel, subs=1000):
    return {'name':channel,'channel_id':channel,'subscriber_count':subs,'status':'included','subtopics':['ai-agents'],'evidence':['group_c_reference']}

def test_content_classifier_signals_and_windows():
    assert classify_content(video('a','c','Grok Bot 新手教學，30 分鐘學會！'))[0] == 'tutorial'
    assert classify_content(video('b','IBM Technology','What AI Agent Skills Are and How They Work'))[0] == 'explainer'
    assert classify_content(video('c','AI Engineer','Conference keynote', minutes=60))[0] == 'talk'
    ref=datetime(2026,11,8,tzinfo=timezone.utc)
    old=video('old','small','Conference keynote', '2026-08-01T00:00:00Z', 60)
    assert window_failure(old, creator('small', 1000), ref, 'talk') == 'type_window:talk'
    assert window_failure(old, creator('small', 600000), ref, 'talk') is None

def test_classifier_requires_explicit_instruction_and_exposes_signals():
    for title in ('AI News: New ChatGPT', 'AI News Is Getting Absolutely RIDICULOUS', 'ChatGPT Can Make GIFs Now', 'Europe joins data center protests'):
        kind, signals=classify_content(video('news', 'c', title, description='Subscribe for tutorials'))
        assert kind == 'explainer'
        assert signals
    assert classify_content(video('howto', 'c', 'How to Use Meta Muse')) == ('tutorial', ['how to'])

def test_configured_product_boundaries_and_quality_ranking():
    topics=cfg()['topics']
    assert boundary('Grok Bot 新手教學，30 分鐘學會！', topics)[0] == 'ai-agents'
    assert boundary('Grok Bot进阶玩法教程：超越 Meta Muse / Claude Duet', topics)[0] == 'ai-agents'
    assert boundary('We may release models we can’t control: Amodei, Altman and Gemini', topics)[0] != 'ai-products'
    assert boundary('How to Use Meta Muse', topics)[0] == 'ai-products'
    assert boundary('Full Claude Tutorial for Beginners', topics)[0] == 'ai-products'
    ref=datetime(2026,11,8,tzinfo=timezone.utc)
    weak=video('weak', 'weak', 'AI agent tutorial', '2026-11-07T00:00:00Z')
    strong=video('strong', 'strong', 'AI agent tutorial', '2026-10-19T00:00:00Z')
    weak['statistics']['viewCount']='100'
    strong['statistics']['viewCount']='671665'
    item=lambda row: (row, creator(row['snippet']['channelId']), (1, 'AI agent'), 'tutorial', ['tutorial'], None)
    assert _candidate_score(item(strong), ref) < _candidate_score(item(weak), ref)

def test_beginner_agent_tutorial_outranks_lifestyle_pitch_at_equal_interest():
    ref=datetime(2026,11,8,tzinfo=timezone.utc)
    beginner=video('beginner', 'jay', 'Grok Bot 新手完整教學：組一支 AI 團隊')
    lifestyle=video('lifestyle', 'dan', 'How to Build an AI Agent for Every Part of Your Life')
    beginner['statistics']['viewCount']=lifestyle['statistics']['viewCount']='10000'
    item=lambda row: (row, creator(row['snippet']['channelId']), (1, 'AI agent'), 'tutorial', ['tutorial'], None)
    assert _candidate_score(item(beginner), ref) < _candidate_score(item(lifestyle), ref)

def test_hardcore_talk_does_not_take_agent_talk_slot_over_plain_language_talk():
    rows=[]; creators=[]
    for index in range(3):
        channel=f't{index}'; creators.append(creator(channel)); rows.append(video(f't{index}',channel,'AI agent tutorial guide'))
    for index in range(2):
        channel=f'e{index}'; creators.append(creator(channel)); rows.append(video(f'e{index}',channel,'AI agent explained: how it works'))
    graph=video('graph', 'AI Engineer', 'Make Your AI Agents Predictable With Graph Engineering - Zachary, Neo4j', minutes=60)
    plain=video('plain', 'AI Engineer 2', 'How Financial Planners With Zero Coding Experience Built Their Own Agents - Matt, Range', minutes=60)
    graph['statistics']['viewCount']='900000'; plain['statistics']['viewCount']='1000'
    creators.extend([creator('AI Engineer',600000),creator('AI Engineer 2',600000)])
    rows.extend([graph,plain])
    raw={'data_refreshed_at':NOW,'creators':creators,'candidate_videos':rows,'usage_summary':{},'baseline':{}}
    agents=next(t for t in select(raw)['topics'] if t['id']=='ai-agents')
    assert 'plain' in [v['video_id'] for v in agents['videos']]
    assert 'graph' not in [v['video_id'] for v in agents['videos']]

def test_group_c_replay_restores_included_but_keeps_subscriber_floor():
    raw={'creators':[{'name':'Gary Chen','channel_id':'UC9C3t-3ocL0LiwGRD0gBJ8A','subscriber_count':103000,
                      'status':'not_topical','subtopics':[],'evidence':[]}]}
    gary=next(c for c in creator_records(raw) if c['channel_id']=='UC9C3t-3ocL0LiwGRD0gBJ8A')
    # The actual select path applies the same replay rule before filtering.
    result=select({**raw, 'data_refreshed_at':NOW, 'candidate_videos':[], 'usage_summary':{}, 'baseline':{}})
    assert next(c for c in result['creators'] if c['channel_id']==gary['channel_id'])['status'] == 'included'
    too_small={'creators':[{'name':'Gary Chen','channel_id':'UC9C3t-3ocL0LiwGRD0gBJ8A','subscriber_count':999,
                            'status':'not_topical','subtopics':[],'evidence':[]}]}
    result=select({**too_small, 'data_refreshed_at':NOW, 'candidate_videos':[], 'usage_summary':{}, 'baseline':{}})
    assert next(c for c in result['creators'] if c['channel_id']=='UC9C3t-3ocL0LiwGRD0gBJ8A')['status'] == 'below_subscribers'

def test_type_window_replaces_topic_age_window():
    raw={'data_refreshed_at':NOW, 'creators':[creator('explainer')], 'candidate_videos':[
        video('old-explainer', 'explainer', 'AI agent explained: how it works', '2026-06-01T00:00:00Z')],
        'usage_summary':{}, 'baseline':{}}
    agents=next(t for t in select(raw)['topics'] if t['id']=='ai-agents')
    assert [v['video_id'] for v in agents['videos']] == ['old-explainer']

def test_mix_quota_then_graceful_degradation():
    rows=[]; creators=[]
    for index in range(4):
        channel=f't{index}'; creators.append(creator(channel)); rows.append(video(f't{index}',channel,'AI agent tutorial guide'))
    for index in range(2):
        channel=f'e{index}'; creators.append(creator(channel)); rows.append(video(f'e{index}',channel,'AI agent explained: how it works'))
    channel='talk'; creators.append(creator(channel,600000)); rows.append(video('talk',channel,'AI agent conference keynote',minutes=60))
    raw={'data_refreshed_at':NOW,'creators':creators,'candidate_videos':rows,'usage_summary':{},'baseline':{}}
    agents=next(t for t in select(raw)['topics'] if t['id']=='ai-agents')
    assert agents['stats']['mix_shown'] == {'tutorial':3,'explainer':2,'talk':1}
    # Without a talk, a fourth tutorial fills the leftover sixth card.
    agents=next(t for t in select({**raw,'candidate_videos':rows[:-1],'creators':creators[:-1]})['topics'] if t['id']=='ai-agents')
    assert len(agents['videos']) == 6 and agents['stats']['mix_shown']['tutorial'] == 4
    # Talks cannot consume the open slot while an extra tutorial is available.
    rows.append(video('t4', 't4', 'AI agent tutorial guide')); creators.append(creator('t4'))
    rows.extend(video(f'talk{n}', f'talk{n}', 'AI agent conference keynote', minutes=60) for n in range(2))
    creators.extend(creator(f'talk{n}', 600000) for n in range(2))
    agents=next(t for t in select({**raw, 'candidate_videos':rows, 'creators':creators})['topics'] if t['id']=='ai-agents')
    assert agents['stats']['mix_shown']['talk'] == 1

def test_fetch_plan_is_uploads_only_and_budgeted():
    source=inspect.getsource(__import__('ytrec.fewgood_r3', fromlist=['x']).fetch)
    assert "f.call('channels'" in source and "f.call('playlistItems'" in source and "f.call('videos'" in source
    assert "f.call('search'" not in source
    plan=estimate()
    assert plan['units_upper_bound'] > 0

def test_global_recommendation_thresholds_are_not_relaxed():
    config=yaml.safe_load((Path(__file__).parents[1] / 'config.yaml').read_text())
    recommendation=config['recommendation']
    assert recommendation['min_recommenders'] == 30
    assert recommendation['min_months'] == 36
    assert config['metadata']['min_duration_seconds'] >= 300
