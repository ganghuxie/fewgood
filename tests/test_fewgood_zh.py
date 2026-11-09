import json
from types import SimpleNamespace

from ytrec import fewgood_zh
from ytrec.fewgood_creators import discovery_only


class Response:
    def __init__(self, status, items=()): self.status_code, self.items = status, list(items)
    def json(self): return {'items': self.items}


def test_estimate_is_fixed_to_ten_searches():
    plan = fewgood_zh.estimate()
    assert plan['search_calls'] == plan['search_call_cap'] == 10
    assert plan['other_unit_cap'] == 300
    assert discovery_only({'evidence': ['zh_discovery_r4']})


def test_fetch_stops_on_rate_limit_and_persists_partial_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(fewgood_zh, 'RAW', tmp_path / 'zh-raw.json')
    monkeypatch.setattr(fewgood_zh, 'USAGE', tmp_path / 'zh-usage.json')
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    calls = []
    def get(url, **kwargs):
        calls.append(url); return Response(429)
    raw = fewgood_zh.fetch(SimpleNamespace(estimate=False), get=get)
    assert len(calls) == 1
    assert raw['usage_summary']['aborted_reason'].startswith('429')
    assert json.loads(fewgood_zh.RAW.read_text())['usage_summary']['search_calls'] == 1


def test_fetch_uses_search_snippets_then_verifies_and_collects(tmp_path, monkeypatch):
    monkeypatch.setattr(fewgood_zh, 'RAW', tmp_path / 'zh-raw.json')
    monkeypatch.setattr(fewgood_zh, 'USAGE', tmp_path / 'zh-usage.json')
    monkeypatch.setattr(fewgood_zh, '_existing_ids', lambda: set())
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    channel = {'id': 'UCzh', 'snippet': {'title': '中文 AI 频道', 'description': '', 'defaultLanguage': 'zh-Hans'},
               'statistics': {'subscriberCount': '20000', 'hiddenSubscriberCount': False},
               'contentDetails': {'relatedPlaylists': {'uploads': 'UUzh'}}}
    upload = {'contentDetails': {'videoId': 'v1', 'videoPublishedAt': '2026-11-08T00:00:00Z'},
              'snippet': {'channelId': 'UCzh', 'channelTitle': '中文 AI 频道', 'title': 'AI Agent 智能体 教程', 'publishedAt': '2026-11-08T00:00:00Z'}}
    detail = {'id': 'v1', 'snippet': upload['snippet'], 'contentDetails': {'duration': 'PT10M'},
              'statistics': {'viewCount': '100'}, 'status': {'privacyStatus': 'public'}}
    def get(url, params, **kwargs):
        endpoint = url.rsplit('/', 1)[-1]
        if endpoint == 'search': return Response(200, [{'id': {'videoId': 'seed'}, 'snippet': {'channelId': 'UCzh'}}])
        if endpoint == 'channels': return Response(200, [channel])
        if endpoint == 'playlistItems': return Response(200, [upload])
        if endpoint == 'videos': return Response(200, [detail])
        raise AssertionError(endpoint)
    # Current date controls the collector's windows; keep this test independent
    # of wall-clock time by using a fresh upload relative to it.
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    upload['contentDetails']['videoPublishedAt'] = upload['snippet']['publishedAt'] = stamp
    raw = fewgood_zh.fetch(SimpleNamespace(estimate=False), get=get)
    assert len(raw['creators']) == 1 and raw['creators'][0]['evidence'] == ['zh_discovery_r4']
    assert raw['creators'][0]['subtopics'] == ['ai-agents', 'ai-coding', 'ai-industry', 'ai-models', 'ai-products']
    assert [row['id'] for row in raw['candidate_videos']] == ['v1']
    assert raw['usage_summary']['search_calls'] == 10
