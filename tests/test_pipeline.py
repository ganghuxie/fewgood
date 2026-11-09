import json
import re
import yaml
from pathlib import Path
from ytrec.core import connect, crawl, extract, aggregate, recommendation_gates, metadata_gates, duration, enrich, report, stamp, trending_feed, podcast_feed, channels_feed, youtube_cost, charge_quota, load_quota, pacific_today, Client
import pytest

@pytest.fixture
def config():
    return yaml.safe_load(Path('config.yaml').read_text())

@pytest.fixture
def db(tmp_path):
    return connect(tmp_path / 'test.sqlite')

class HN:
    def __init__(self): self.calls = []
    def get(self, url, params):
        self.calls.append(params)
        lo,hi = [int(re.search(r'(\d+)$', x).group(1)) for x in params['numericFilters'].split(',')]
        if hi-lo > 2: return {'nbHits':1001,'nbPages':1,'hits':[]}
        return {'nbHits':1,'nbPages':1,'hits':[{'objectID':str(lo), 'author':'user', 'created_at_i':lo}]}

def test_split_resume(db, config):
    client = HN()
    crawl(db, config, 0, 4, client)
    assert len(client.calls) == 18
    assert db.execute('SELECT count(*) FROM items').fetchone()[0] == 2
    crawl(db, config, 0, 4, client)
    assert len(client.calls) == 18

def test_extract_repeated_author_months(db, config):
    for i,(author,day) in enumerate([('a','2020-01-01'),('a','2021-02-01'),('b','2021-03-01')]):
        db.execute('INSERT INTO items VALUES (?,?,?,?,?)', (str(i),'comment',author,stamp(day),json.dumps({'comment_text':'<p>Great <a href="https://youtu.be/dQw4w9WgXcQ">talk</a></p>'})))
    extract(db)
    extract(db)
    v = aggregate(db)[0]
    assert (v['recommenders'],v['months']) == (2,3)
    assert v['span_days'] > 365
    assert len(v['quotes']) == 2
    assert '<p>' not in v['quotes'][0]['text']
    assert recommendation_gates(v,config['recommendation'])['recommenders']

def raw():
    return {'id':'dQw4w9WgXcQ','snippet':{'publishedAt':'2020-01-01T00:00:00Z','title':'Example','channelTitle':'Channel'},'contentDetails':{'duration':'PT5M'},'status':{'privacyStatus':'public','uploadStatus':'processed'}}

def test_metadata_gates(config):
    c = config['metadata']; at = stamp('2025-01-01')
    assert not any(metadata_gates(raw(),c,at).values())
    assert metadata_gates(None,c,at)['metadata_unavailable']
    r=raw(); r['status']['privacyStatus']='private'
    assert metadata_gates(r,c,at)['metadata_unavailable']
    r=raw(); r['snippet']['publishedAt']='2024-12-31T00:00:00Z'; r['contentDetails']['duration']='PT4M59S'
    gates=metadata_gates(r,c,at)
    assert gates['publish_age'] and gates['duration']
    assert duration('P1DT2H3M4S') == 93784

def test_enrich_only_candidates_and_cache(db, config, monkeypatch):
    monkeypatch.setenv('YOUTUBE_' + 'API_KEY','test-only')
    class YT:
        calls=0
        def get(self, url, params, youtube=False):
            self.calls+=1
            assert len(params['id'].split(',')) <= 50
            return {'items':[raw()]}
    client=YT()
    good={'id':'dQw4w9WgXcQ','recommenders':30,'months':36,'span_days':365}
    bad=dict(good,id='abcdefghijk',recommenders=4)
    enrich(db,config,[good,bad],client=client)
    enrich(db,config,[good,bad],client=client)
    assert client.calls == 1
    assert db.execute('SELECT count(*) FROM metadata').fetchone()[0] == 1

def test_report_gates_and_what_if(db,config,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    good=dict(id='dQw4w9WgXcQ',recommenders=30,months=36,span_days=365,first=1,last=31536001,quotes=[])
    db.execute('INSERT INTO metadata VALUES (?,?,?)',(good['id'],1,json.dumps(raw())))
    result=report(db,config,[good],str(tmp_path/'reports'))
    assert result['final_selected']==1
    assert len(result['what_if'])==25
    first=db.execute('SELECT selected_at FROM selections').fetchone()[0]
    report(db,config,[good],str(tmp_path/'reports'))
    assert db.execute('SELECT selected_at FROM selections').fetchone()[0]==first

def test_report_upload_age_cutoff_and_classic_speech_exemptions(db, config, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recent = raw()
    old_plain = dict(raw(), id='old-plain'); old_plain['snippet'] = dict(old_plain['snippet'], publishedAt='2000-01-01T00:00:00Z')
    exempt_a = dict(raw(), id='exempt-a'); exempt_a['snippet'] = dict(exempt_a['snippet'], publishedAt='2000-01-01T00:00:00Z', title='Steve Jobs Commencement Address', channelTitle='Archive')
    exempt_b = dict(raw(), id='exempt-b'); exempt_b['snippet'] = dict(exempt_b['snippet'], publishedAt='2000-01-01T00:00:00Z', title='Course recording', channelTitle='Stanford'); exempt_b['contentDetails'] = {'duration':'PT20M'}
    exempt_c = dict(raw(), id='exempt-c'); exempt_c['snippet'] = dict(exempt_c['snippet'], publishedAt='2000-01-01T00:00:00Z', title='Talk', channelTitle='Richard Feynman Archive'); exempt_c['contentDetails'] = {'duration':'PT20M'}
    raws = [recent, old_plain, exempt_a, exempt_b, exempt_c]
    for item in raws:
        db.execute('INSERT INTO metadata VALUES (?,?,?)', (item['id'], 1, json.dumps(item)))
    videos = [dict(id=item['id'], recommenders=30, months=36, span_days=365, first=1, last=31536001, quotes=[]) for item in raws]
    result = report(db, config, videos, str(tmp_path / 'reports'))
    selected = json.loads((tmp_path / 'site/src/data/videos.json').read_text())['videos']
    by_id = {video['id']: video for video in selected}
    assert result['final_selected'] == 4
    assert result['dropped_by_gate']['max_upload_age'] == 1
    assert 'old-plain' not in by_id
    assert by_id[recent['id']]['classic_speech'] is False
    assert by_id[recent['id']]['published_at'] == '2020-01-01T00:00:00Z'
    assert all(by_id[item['id']]['classic_speech'] is True for item in (exempt_a, exempt_b, exempt_c))
    assert 'A_speech' in by_id['exempt-a']['classic_speech_reasons']
    assert 'B_channel_duration' in by_id['exempt-b']['classic_speech_reasons']
    assert 'C_speaker_duration' in by_id['exempt-c']['classic_speech_reasons']

def test_truncation_not_completed(db,config):
    class Truncated:
        def get(self,*args): return {'nbHits':2,'nbPages':1,'hits':[]}
    with pytest.raises(RuntimeError,match='Truncated'):
        crawl(db,config,0,4,Truncated())
    assert db.execute('SELECT count(*) FROM windows').fetchone()[0]==0

@pytest.mark.parametrize('error_type', ['RequestException', 'ReadTimeout'])
def test_request_retry_and_secret_suppression(monkeypatch, error_type):
    from ytrec.core import Client
    import requests
    calls=[]
    def get(*args,**kwargs):
        calls.append(1)
        response = requests.Response()
        response.status_code = 429 if len(calls) == 1 else 200
        response._content = b'{"ok": true}'
        response._content_consumed = True
        return response
    monkeypatch.setattr('ytrec.core.requests.Session.get',get)
    monkeypatch.setattr('ytrec.core.time.sleep',lambda _:None)
    assert Client().get('https://example.com',{'key':'never-show'}) == {'ok':True}
    failed_sessions = []
    def fail(session, *args, **kwargs):
        failed_sessions.append(session)
        raise getattr(requests, error_type)('https://example.com?key=never-show')
    monkeypatch.setattr('ytrec.core.requests.Session.get',fail)
    with pytest.raises(RuntimeError) as error:
        Client().get('https://example.com',{'key':'never-show'})
    assert str(error.value) == 'API transport failed (request details suppressed)'
    assert len(failed_sessions) == 7
    assert len({id(session) for session in failed_sessions}) == 7

def test_timestamp_offset():
    assert stamp('2024-01-01T08:00:00+08:00') == stamp('2024-01-01')

def test_youtube_costs():
    assert youtube_cost('https://www.googleapis.com/youtube/v3/search') == 100
    assert youtube_cost('https://www.googleapis.com/youtube/v3/videos') == 1
    assert youtube_cost('https://www.googleapis.com/youtube/v3/channels') == 1
    assert youtube_cost('https://www.googleapis.com/youtube/v3/playlistItems') == 1
    assert youtube_cost('https://www.googleapis.com/youtube/v3/commentThreads') == 1

def test_config_daily_quota_limit(config):
    assert config['metadata']['daily_quota_limit'] == 8000
    assert config['metadata']['max_upload_age_years'] == 12
    assert config['metadata']['classic_speech']['min_duration_seconds'] == 1200
    assert 'Ray Dalio' not in config['metadata']['classic_speech']['famous_speakers']

def test_quota_charge_persists_and_refuses(tmp_path):
    path = tmp_path / 'quota.json'
    charge_quota(3, 5, path)
    assert load_quota(path) == {'date': pacific_today(), 'units': 3}
    before = path.read_text()
    with pytest.raises(RuntimeError, match='would exceed 5'):
        charge_quota(3, 5, path)
    assert path.read_text() == before

def test_quota_rolls_over(tmp_path):
    path = tmp_path / 'quota.json'
    path.write_text(json.dumps({'date': '2000-01-01', 'units': 999}))
    assert load_quota(path) == {'date': pacific_today(), 'units': 0}

def test_client_youtube_search_charges_before_request(tmp_path):
    client = Client(quota_limit=200, quota_path=tmp_path / 'quota.json')
    client._request = lambda url, params: (200, {'ok': True})
    assert client.get('https://www.googleapis.com/youtube/v3/search', {}, youtube=True) == {'ok': True}
    assert load_quota(tmp_path / 'quota.json')['units'] == 100

def test_batching_and_unavailable_cache(db, config, monkeypatch):
    monkeypatch.setenv('YOUTUBE_' + 'API_KEY','test-only')
    class YT:
        sizes=[]
        def get(self,url,params,youtube=False):
            self.sizes.append(len(params['id'].split(',')))
            return {'items':[]}
    client=YT()
    videos=[dict(id=f'{i:011d}',recommenders=30,months=36,span_days=365) for i in range(51)]
    enrich(db,config,videos,client=client)
    enrich(db,config,videos,client=client)
    assert client.sizes==[50,1]
    assert db.execute("SELECT count(*) FROM metadata WHERE raw='null'").fetchone()[0]==51

def test_recommendation_boundaries(config):
    c=config['recommendation']
    v=dict(recommenders=30,months=36,span_days=365)
    assert not any(recommendation_gates(v,c).values())
    c['sources']['enabled']=True
    assert recommendation_gates(v,c)['sources']

def test_trending_feed_filters_shorts_and_writes_json(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_' + 'API_KEY', 'test-only')
    class YT:
        search_params = []
        def get(self, url, params, youtube=False):
            if url.endswith('search'):
                self.search_params.append(params)
                return {'items': [{'id': {'videoId': 'long'}}, {'id': {'videoId': 'vertical'}}, {'id': {'videoId': 'short'}}]}
            return {'items': [
                dict(raw(), id='long', player={'embedWidth': 640, 'embedHeight': 360}, statistics={'viewCount': '9'}),
                dict(raw(), id='vertical', player={'embedWidth': 360, 'embedHeight': 640}, statistics={'viewCount': '99'}),
                dict(raw(), id='short', player={'embedWidth': 360, 'embedHeight': 640}, contentDetails={'duration': 'PT59S'}, statistics={'viewCount': '199'}),
            ]}
    result = trending_feed(YT(), tmp_path)
    assert result['videos'][0]['id'] == 'long'
    assert result['candidates_fetched'] == 3
    assert result['dropped_short'] == 1
    assert result['dropped_vertical'] == 1
    assert result['landscape_only'] is True
    assert result['final_count'] == 1
    assert len(YT.search_params) == 10
    assert {params['videoDuration'] for params in YT.search_params} == {'medium', 'long'}
    assert all('videoDuration' in params for params in YT.search_params)
    assert len({(params['publishedAfter'], params['publishedBefore']) for params in YT.search_params}) == 5
    assert all('publishedAfter' in params and 'publishedBefore' in params for params in YT.search_params)
    assert result['video_duration_buckets'] == ['medium', 'long']
    assert result['window_days'] == 30
    assert result['window_size_days'] == 6
    assert result['windows'] == 5
    saved = json.loads((tmp_path / 'trending.json').read_text())
    assert saved['exclude_shorts_under_seconds'] == 60

def test_trending_feed_deduplicates_window_candidates_and_sorts(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_' + 'API_KEY', 'test-only')
    class YT:
        search_params = []
        def get(self, url, params, youtube=False):
            if url.endswith('search'):
                self.search_params.append(params)
                return {'items': [{'id': {'videoId': 'a'}}, {'id': {'videoId': 'b'}},
                                  {'id': {'videoId': 'a'}}]}
            ids = params['id'].split(',')
            return {'items': [dict(raw(), id=video_id, player={'embedWidth': 640, 'embedHeight': 360},
                                   statistics={'viewCount': '9' if video_id == 'a' else '99'})
                             for video_id in ids]}

    client = YT()
    result = trending_feed(client, tmp_path)
    assert len(client.search_params) == 10
    assert result['candidates_fetched'] == 2
    assert [video['id'] for video in result['videos']] == ['b', 'a']
    assert result['quota_units_approx'] == 1001

def test_podcast_windowed_feed_uses_query(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_' + 'API_KEY', 'test-only')
    class YT:
        queries = []
        def get(self, url, params, youtube=False):
            if url.endswith('search'):
                self.queries.append(params)
                return {'items': [{'id': {'videoId': 'pod'}}]}
            return {'items': [dict(raw(), id='pod', player={'embedWidth': 640, 'embedHeight': 360}, statistics={'viewCount': '1'})]}
    result = podcast_feed(YT(), tmp_path)
    assert len(YT.queries) == 10
    assert {query['q'] for query in YT.queries} == {'podcast'}
    assert result['query'] == 'podcast'

def test_channels_feed_collects_feed_channel_ids_and_uploads(tmp_path, monkeypatch):
    monkeypatch.setenv('YOUTUBE_' + 'API_KEY', 'test-only')
    (tmp_path / 'trending.json').write_text(json.dumps({'videos': [{'channel_id': 'channel-1'}]}))
    class YT:
        def get(self, url, params, youtube=False):
            if url.endswith('channels'):
                return {'items': [{'id': 'channel-1', 'snippet': {'title': 'Example', 'thumbnails': {'default': {'url': 'avatar'}}}, 'statistics': {'subscriberCount': '12'}, 'contentDetails': {'relatedPlaylists': {'uploads': 'uploads-1'}}}]}
            return {'items': [{'snippet': {'title': 'Recent', 'thumbnails': {'default': {'url': 'thumb'}}, 'resourceId': {'videoId': 'video-1'}}, 'contentDetails': {'videoId': 'video-1', 'videoPublishedAt': '2025-01-01T00:00:00Z'}}]}
    result = channels_feed(YT(), tmp_path)
    assert result['channels'][0]['id'] == 'channel-1'
    assert result['channels'][0]['videos'][0]['id'] == 'video-1'


@pytest.mark.parametrize('stall_at', ['headers', 'body'])
def test_request_deadline_retries_stalled_response(monkeypatch, stall_at):
    from threading import Event
    from time import monotonic
    import requests
    from ytrec.core import Client

    release = Event()
    closed = Event()
    sessions = []
    sleeps = []

    class StalledResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.set()

        def iter_content(self, chunk_size):
            yield b'{'  # Receiving some bytes must not reset the deadline.
            release.wait(5)
            yield b'}'

    def get(session, url, **kwargs):
        sessions.append(session)
        assert kwargs['stream'] is True
        assert kwargs['timeout'] == (10, 30)
        if len(sessions) == 1:
            if stall_at == 'headers':
                release.wait(5)
            return StalledResponse()
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"ok": true}'
        response._content_consumed = True
        return response

    monkeypatch.setattr('ytrec.core.requests.Session.get', get)
    monkeypatch.setattr('ytrec.core.time.sleep', sleeps.append)
    client = Client()
    client.request_deadline = 0.1
    started = monotonic()
    try:
        assert client.get('https://example.com', {'key': 'never-show'}) == {'ok': True}
        assert monotonic() - started < 2
        assert len(sessions) == 2
        assert sessions[0] is not sessions[1]
        assert sleeps[1] == 1  # Existing first-retry backoff.
    finally:
        release.set()
        assert closed.wait(2)
        client.session.close()


def test_extract_skips_malformed_candidates(db):
    text = ('http://[youtube.com/watch?v=dQw4w9WgXcQ '
            'https://youtu.be/] '
            'https://youtube.com/watch?v=abcdefghijk&x=%FF '
            '(https://youtu.be/dQw4w9WgXcQ)')
    db.execute('INSERT INTO items VALUES (?,?,?,?,?)',
               ('malformed', 'comment', 'user', stamp('2020-01-01'),
                json.dumps({'comment_text': text})))
    extract(db)
    assert [v['id'] for v in aggregate(db)] == ['dQw4w9WgXcQ']


def test_what_if_uses_each_rows_thresholds_and_cached_gates(db, config, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    videos = [dict(id=str(i), recommenders=p, months=m, span_days=s)
              for i, (p, m, s) in enumerate([(5, 6, 365), (30, 36, 365),
                                           (50, 48, 365), (50, 48, 365),
                                           (50, 48, 364)])]
    # Loose-only cached pass, strict cached failure, and two unknowns.
    db.execute('INSERT INTO metadata VALUES (?,?,?)', ('0', 1, json.dumps(raw())))
    db.execute('INSERT INTO metadata VALUES (?,?,?)', ('2', 1, 'null'))
    result = report(db, config, videos, str(tmp_path / 'reports'))
    rows = {(r['recommenders'], r['months']): r for r in result['what_if']}
    assert (rows[5, 6]['candidates'], rows[5, 6]['selected_with_cached_metadata'],
            rows[5, 6]['unknown_metadata']) == (4, 1, 2)
    assert (rows[50, 48]['candidates'], rows[50, 48]['selected_with_cached_metadata'],
            rows[50, 48]['unknown_metadata']) == (2, 0, 1)
    assert db.execute('SELECT count(*) FROM quota').fetchone()[0] == 0
