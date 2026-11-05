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
    good={'id':'dQw4w9WgXcQ','recommenders':5,'months':6,'span_days':365}
    bad=dict(good,id='abcdefghijk',recommenders=4)
    enrich(db,config,[good,bad],client=client)
    enrich(db,config,[good,bad],client=client)
    assert client.calls == 1
    assert db.execute('SELECT count(*) FROM metadata').fetchone()[0] == 1

def test_report_gates_and_what_if(db,config,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    good=dict(id='dQw4w9WgXcQ',recommenders=5,months=6,span_days=365,first=1,last=31536001,quotes=[])
    db.execute('INSERT INTO metadata VALUES (?,?,?)',(good['id'],1,json.dumps(raw())))
    result=report(db,config,[good],str(tmp_path/'reports'))
    assert result['final_selected']==1
    assert len(result['what_if'])==18
    first=db.execute('SELECT selected_at FROM selections').fetchone()[0]
    report(db,config,[good],str(tmp_path/'reports'))
    assert db.execute('SELECT selected_at FROM selections').fetchone()[0]==first

def test_truncation_not_completed(db,config):
    class Truncated:
        def get(self,*args): return {'nbHits':2,'nbPages':1,'hits':[]}
    with pytest.raises(RuntimeError,match='Truncated'):
        crawl(db,config,0,4,Truncated())
    assert db.execute('SELECT count(*) FROM windows').fetchone()[0]==0

def test_request_retry_and_secret_suppression(monkeypatch):
    from ytrec.core import Client
    import requests
    calls=[]
    def get(*args,**kwargs):
        calls.append(1)
        if len(calls)==1: return type('Response',(),{'status_code':429})()
        return type('Response',(),{'status_code':200,'json':lambda self:{'ok':True}})()
    monkeypatch.setattr('ytrec.core.requests.get',get)
    monkeypatch.setattr('ytrec.core.time.sleep',lambda _:None)
    assert Client().get('https://example.com',{'key':'never-show'}) == {'ok':True}
    def fail(*args,**kwargs): raise requests.RequestException('https://example.com?key=never-show')
    monkeypatch.setattr('ytrec.core.requests.get',fail)
    with pytest.raises(RuntimeError) as error:
        Client().get('https://example.com',{'key':'never-show'})
    assert 'never-show' not in str(error.value)

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
    videos=[dict(id=f'{i:011d}',recommenders=5,months=6,span_days=365) for i in range(51)]
    enrich(db,config,videos,client=client)
    enrich(db,config,videos,client=client)
    assert client.sizes==[50,1]
    assert db.execute("SELECT count(*) FROM metadata WHERE raw='null'").fetchone()[0]==51

def test_recommendation_boundaries(config):
    c=config['recommendation']
    v=dict(recommenders=5,months=6,span_days=365)
    assert not any(recommendation_gates(v,c).values())
    c['sources']['enabled']=True
    assert recommendation_gates(v,c)['sources']
