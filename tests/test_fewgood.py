import json
import pytest
from ytrec.fewgood_report import main as report_main
from ytrec.fewgood import Fetcher, usage_empty, select, pool_relevant

def test_search_cap_refuses_sixteenth_request():
    cfg={'search_call_cap':15,'other_unit_cap':300}; seen=[]
    class R:
        status_code=200
        def json(self): return {'items':[]}
    f=Fetcher(cfg,'secret-key',get=lambda *a,**k: (seen.append(1) or R()))
    for _ in range(15): f.call('search',{},'test')
    with pytest.raises(RuntimeError): f.call('search',{},'sixteenth')
    assert len(seen)==15

def test_other_cap_and_key_not_in_usage():
    cfg={'search_call_cap':15,'other_unit_cap':1}
    class R:
        status_code=200
        def json(self): return {'items':[]}
    f=Fetcher(cfg,'super-secret',get=lambda *a,**k:R()); f.call('videos',{},'details')
    with pytest.raises(RuntimeError) as e: f.call('videos',{},'details')
    assert 'super-secret' not in json.dumps(f.usage)+str(e.value)

def test_quota_exceeded_stops_and_does_not_leak_key():
    class R:
        status_code=403
        def json(self): return {'error':{'errors':[{'reason':'quotaExceeded'}]}}
    f=Fetcher({'search_call_cap':15,'other_unit_cap':2},'top-secret',get=lambda *a,**k:R())
    f.call('search',{},'topic')
    assert f.usage['aborted_reason']=='403 quotaExceeded'
    assert 'top-secret' not in json.dumps(f.usage)

def test_excluded_real_estate_agent_is_not_selected():
    raw={'candidates':[{'id':'x','snippet':{'title':'Real estate agent training','publishedAt':'2099-01-01T00:00:00Z','channelId':'x'},'contentDetails':{'duration':'PT5M'},'statistics':{},'sources':['search:x']}], 'baseline':{}}
    assert not next(t for t in select(raw)['topics'] if t['id']=='ai-agents')['videos']

def test_same_id_merges_sources():
    raw={'candidates':[{'id':'x','snippet':{'title':'AI agent demo','publishedAt':'2099-01-01T00:00:00Z','channelId':'x'},'contentDetails':{'duration':'PT5M'},'statistics':{},'sources':['search:x']},{'id':'x','snippet':{'title':'AI agent demo','publishedAt':'2099-01-01T00:00:00Z','channelId':'x'},'contentDetails':{'duration':'PT5M'},'statistics':{},'sources':['channel_uploads:X']}], 'baseline':{}}
    v=next(t for t in select(raw)['topics'] if t['id']=='ai-agents')['videos'][0]
    assert len(v['sources'])==2

def test_missing_player_dimensions_do_not_mark_vertical_but_portrait_does():
    raw={'candidates':[
        {'id':'embed-only','snippet':{'title':'Large language model demo','publishedAt':'2099-01-01T00:00:00Z','channelId':'x'},'contentDetails':{'duration':'PT5M'},'player':{'embedHtml':'<iframe></iframe>'},'statistics':{},'sources':['search:x']},
        {'id':'portrait','snippet':{'title':'Large language model research','publishedAt':'2099-01-01T00:00:00Z','channelId':'x'},'contentDetails':{'duration':'PT5M'},'player':{'embedWidth':270,'embedHeight':480},'statistics':{},'sources':['search:x']}
    ], 'baseline':{}}
    result=select(raw)
    videos=next(t for t in result['topics'] if t['id']=='ai-models')['videos']
    assert 'embed-only' in [video['video_id'] for video in videos]
    assert 'portrait' not in [video['video_id'] for video in videos]
    assert result['rules_notes'] == ['竖屏判断：videos.list 未返回 embedWidth/embedHeight 时不按方向排除，依靠最短 4 分钟时长排除 Shorts']

def test_one_video_is_assigned_to_only_one_best_topic_and_tier3_is_not_shown():
    raw={'candidates':[
        {'id':'best','snippet':{'title':'Claude Code agentic AI','publishedAt':'2099-01-01T00:00:00Z','channelId':'x'},'contentDetails':{'duration':'PT5M'},'statistics':{},'sources':['search:q']},
        {'id':'weak','snippet':{'title':'Unrelated title','description':'Claude','publishedAt':'2099-01-01T00:00:00Z','channelId':'x'},'contentDetails':{'duration':'PT5M'},'statistics':{},'sources':['search:q']}
    ], 'baseline':{}, 'usage_summary':usage_empty()}
    result=select(raw)
    shown=[v['video_id'] for t in result['topics'] for v in t['videos']]
    assert shown.count('best') == 1
    models=next(t for t in result['topics'] if t['id']=='ai-models')
    assert models['stats']['matched_tier3'] == 1
    assert 'weak' not in shown

def test_stats_searches_are_scoped_and_pool_filter_keeps_ai_or_keyword_titles():
    cfg={'topics':[{'include_terms':{'strong':['AI agent'],'weak':['agent']}}]}
    rows=[{'id':'a','snippet':{'title':'unrelated'},'sources':['existing:ai.json']}, {'id':'b','snippet':{'title':'AI agent demo'},'sources':['existing:videos.json']}, {'id':'c','snippet':{'title':'cooking'},'sources':['existing:videos.json']}]
    assert [x['id'] for x in pool_relevant(rows,cfg)] == ['a','b']
    raw={'candidates':[], 'baseline':{}, 'usage_summary':{**usage_empty(), 'calls':[{'endpoint':'search','purpose':'topic:ai-models:x','returned':7},{'endpoint':'search','purpose':'baseline:ai-models','returned':6}]}}
    stats=next(t for t in select(raw)['topics'] if t['id']=='ai-models')['stats']
    assert stats['searches']==1 and stats['baseline_searches']==1 and stats['topic_search_results']==7
    for key in ('matched','matched_tier1','matched_tier2','matched_tier3','eligible','shown','channel_distribution_shown','channel_distribution_eligible','excluded_by_rule','duplicates_in_topic'):
        assert key in stats


def test_report_generates_quality_and_ab_docs_with_escaped_pipe(tmp_path):
    result = {
        'data_refreshed_at': '2026-01-02T00:00:00Z', 'pool_stats': {'raw': 1},
        'timing': {'collect_seconds': 1.2},
        'topics': [{'id': 't', 'name_zh': '测试主题', 'stats': {'shown': 1}, 'videos': [{
            'video_id': 'v1', 'title': '标题 | 测试', 'url': 'https://example.test/v1',
            'channel_title': '频道', 'published_at': '2026-01-01T00:00:00Z',
            'duration_seconds': 125, 'view_count': 7, 'sources': ['search:q'], 'reasons': ['依据 | 一']
        }]}], 'baseline': {'t': [{
            'rank': 1, 'video_id': 'v1', 'title': '标题 | 测试', 'url': 'https://example.test/v1',
            'channel_title': '频道', 'published_at': '2026-01-01T00:00:00Z', 'duration_seconds': 125,
            'view_count': 7
        }]}}
    usage = {'calls': [{'endpoint': 'search', 'purpose': 'topic:t:q', 'http_status': 200}], 'old_model_units': 100, 'aborted_reason': None}
    judgments = {'v1': {'verdict': '相关', 'note': '好 | 注'}}
    result_path, usage_path, judgments_path = (tmp_path / x for x in ('result.json', 'usage.json', 'judgments.json'))
    for path, data in ((result_path, result), (usage_path, usage), (judgments_path, judgments)):
        path.write_text(json.dumps(data, ensure_ascii=False))
    report_main(['--result', str(result_path), '--usage', str(usage_path), '--judgments', str(judgments_path), '--out-dir', str(tmp_path)])
    quality = (tmp_path / 'quality-tables.md').read_text()
    comparison = (tmp_path / 'ab-comparison.md').read_text()
    assert '# Fewgood MVP 质量报告' in quality and '测试主题' in quality and '标题 \\| 测试' in quality
    assert '初步主题相关率 = 1/1' in quality and '# Fewgood MVP A/B 对比' in comparison
    assert 'C 组（Jason 人工挑选）待补充' in comparison
