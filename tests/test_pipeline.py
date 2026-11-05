import json
import re
import yaml
from pathlib import Path
from ytrec.core import connect, crawl, extract, aggregate, recommendation_gates, metadata_gates, duration, enrich, report, stamp
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
    return {'id':'dQw4w9WgXcQ','snippet':{'publishedAt':'2010-01-01T00:00:00Z','title':'Example','channelTitle':'Channel'},'contentDetails':{'duration':'PT5M'},'status':{'privacyStatus':'public','uploadStatus':'processed'}}

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
    monkeypatch.setenv('YOUTUBE_API_KEY','test-only')
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

def test_batching_and_unavailable_cache(db, config, monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY','test-only')
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
