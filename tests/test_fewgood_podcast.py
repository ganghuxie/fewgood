import inspect
from datetime import datetime, timezone

from ytrec import fewgood_podcast as podcast

NOW='2026-11-08T00:00:00Z'
def row(identifier, channel, title, topic_words='AI technology', minutes=60, published='2026-11-01T00:00:00Z'):
    return {'id':identifier,'snippet':{'channelId':channel,'channelTitle':channel,'title':title+' '+topic_words,'publishedAt':published},'contentDetails':{'duration':f'PT{minutes}M'},'statistics':{'viewCount':'100'}}
def creator(channel, topics):
    return {'name':channel,'channel_id':channel,'subtopics':topics,'evidence':['existing_registry'],'subscriber_count':1000,'last_upload_at':NOW,'status':'included'}

def test_classify_duration_exclusion_and_windows():
    assert podcast.classify_content(row('a','c','Interview with a founder'))[0] == 'interview'
    assert podcast._failure(row('short','c','Interview',minutes=10), podcast.topics_config()['topics'][0], datetime(2026,11,8,tzinfo=timezone.utc), 'interview', podcast.types_config()) == 'too_short'
    old=row('old','c','Deep dive analysis',published='2025-01-01T00:00:00Z')
    assert podcast._failure(old,podcast.topics_config()['topics'][0],datetime(2026,11,8,tzinfo=timezone.utc),'deep_dive',podcast.types_config()) == 'type_window:deep_dive'

def test_select_mix_channel_cap_and_schema():
    rows=[]; creators=[]
    kinds=[('interview','Interview'),('interview','Conversation'),('interview','Podcast interview'),('deep','Deep dive'),('deep','Explained analysis'),('talk','Fireside talk'),('talk','Lecture talk')]
    for n,(kind,title) in enumerate(kinds):
        cid='same' if n < 3 else f'c{n}'; rows.append(row(str(n),cid,title));
        if not any(x['channel_id']==cid for x in creators): creators.append(creator(cid,['pod-tech-ai']))
    result=podcast.select({'data_refreshed_at':NOW,'creators':creators,'candidate_videos':rows,'usage_summary':{}})
    topic=next(x for x in result['topics'] if x['id']=='pod-tech-ai')
    assert topic['stats']['shown'] <= 6
    assert sum(v['channel_id']=='same' for v in topic['videos']) <= 2
    assert all({'reasons','content_type_label','url'} <= set(v) for v in topic['videos'])

def test_estimate_and_fetch_are_search_free_and_capped():
    plan=podcast.estimate()
    assert plan['search_calls'] == 0 and plan['combined_other_units_upper_bound'] <= 300
    assert "f.call('search'" not in inspect.getsource(podcast.fetch)
    assert "'forHandle'" in inspect.getsource(podcast.resolve)

def test_topic_match_requires_creator_subtopic_and_multi_topic_term():
    multi=creator('ted',['pod-society','pod-science-health'])
    science=next(x for x in podcast.topics_config()['topics'] if x['id']=='pod-science-health')
    society=next(x for x in podcast.topics_config()['topics'] if x['id']=='pod-society')
    assert podcast._topic_match(row('x','ted','A conversation about business'), science, multi)[0] is False
    assert podcast._topic_match(row('x','ted','A conversation about neuroscience'), science, multi)[0] is True
    assert podcast._topic_match(row('x','ted','Politics and policy'), society, multi)[0] is False
    assert podcast._topic_match(row('x','ted','A conversation about culture'), society, multi)[0] is True
    assert podcast._topic_match(row('x','other','A guest episode'), science, creator('other',['pod-tech-ai']))[0] is False

def test_title_signals_classify_huberman_and_ted_formats():
    assert podcast.classify_content(row('x','c','Essentials: Sleep and Health'))[0] == 'deep_dive'
    assert podcast.classify_content(row('x','c','TED Talk: The science of sleep'))[0] == 'talk'
