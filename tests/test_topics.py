import json
from pathlib import Path

from ytrec import topics

FIXTURES = Path(__file__).parent / 'fixtures' / 'v2'

def cfg(tmp_path):
    return {'metadata_ttl_days': 30, 'max_retries': 2, 'batch_size': 5,
            'legacy_daily_limit': 8000, 'reserve_legacy_units': 3500,
            'search_call_cap': 100, 'reserve_search_calls': 35,
            'other_unit_cap': 10000, 'reserve_other_units': 2000,
            'search_calls_used': 0, 'other_units_used': 0, 'quota_path': str(tmp_path/'quota.json')}

def paths(tmp_path):
    return tmp_path/'topics', tmp_path/'index.json', tmp_path/'status.json'

def test_nfc_alias_reuse_and_languages_stay_distinct(tmp_path):
    out, index, status = paths(tmp_path)
    result, _ = topics.run(FIXTURES/'pending-topics.json', FIXTURES, out, index, status, cfg(tmp_path))
    names = [x['canonical_name'] for x in result['topics']]
    assert names.count('Café') == 1
    assert (out/'c-plus-plus.json').exists() and (out/'c-sharp.json').exists()

def test_cache_ttl_skips_fixture_fetch(tmp_path):
    out, index, status = paths(tmp_path); out.mkdir()
    topics.atomic_json(out/'cafe.json', {'topic_id':'cafe','canonical_name':'Café','status':'ready','generated_at':topics.now_iso(),'videos':[]})
    result, _ = topics.run(FIXTURES/'pending-topics.json', FIXTURES, out, index, status, cfg(tmp_path))
    assert next(x for x in result['topics'] if x['topic_id']=='cafe')['status'] == 'ready'
    assert json.loads((out/'cafe.json').read_text())['videos'] == []

def test_quota_reserve_blocks(tmp_path):
    out, index, status = paths(tmp_path); c = cfg(tmp_path); c['search_calls_used'] = 66
    result, _ = topics.run(FIXTURES/'pending-topics.json', FIXTURES, out, index, status, c)
    assert {x['status'] for x in result['topics']} == {'quota_deferred'}

def test_retry_is_bounded_at_two_retries():
    # Two retryable failures then the final fixture attempt; no network is possible.
    rows, attempts = topics.fixture_videos(FIXTURES, 'Retry Topic', 2)
    assert [x['video_id'] for x in rows] == ['fixture-retry-01']
    assert attempts == 3

def test_lock_prevents_double_run(tmp_path):
    lock = tmp_path/'lock'
    with topics.Lock(lock) as first:
        assert first
        with topics.Lock(lock) as second: assert not second

def test_atomic_publish_dedupes_and_public_docs_are_safe(tmp_path):
    out, index, status = paths(tmp_path)
    topics.run(FIXTURES/'pending-topics.json', FIXTURES, out, index, status, cfg(tmp_path))
    cafe = json.loads((out/'cafe.json').read_text())
    assert [v['video_id'] for v in cafe['videos']] == ['fixture-cafe-01']
    public = (index.read_text() + status.read_text() + (out/'cafe.json').read_text()).lower()
    assert 'user_id' not in public and 'raw input' not in public and 'error' not in public
    assert not list(out.glob('*.tmp'))

def test_fixture_end_to_end_expected_shapes_and_dry_run(tmp_path, capsys):
    out, index, status = paths(tmp_path)
    result, summary = topics.run(FIXTURES/'pending-topics.json', FIXTURES, out, index, status, cfg(tmp_path))
    assert {'generated_at','topics'} <= result.keys()
    assert {'generated_at','topics','summary'} <= summary.keys()
    dry = tmp_path/'dry'; topics.run(FIXTURES/'pending-topics.json', FIXTURES, dry, tmp_path/'i.json', tmp_path/'s.json', cfg(tmp_path), dry_run=True)
    assert not dry.exists() and 'would write' in capsys.readouterr().out
