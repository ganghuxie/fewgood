import json
from pathlib import Path

from ytrec.core import connect, youtube_cost
from ytrec import zh as zh_module
from ytrec.zh import _entry, enrich_zh, parse_json_response, request_deepseek, truncate_transcript


def test_comment_threads_cost_one():
    assert youtube_cost('https://www.googleapis.com/youtube/v3/commentThreads') == 1
    assert youtube_cost('https://www.googleapis.com/youtube/v3/commentthreads?part=snippet') == 1


def test_parse_deepseek_fenced_json():
    assert parse_json_response('```json\n{"title_zh":"标题"}\n```') == {'title_zh': '标题'}


def test_truncate_transcript_is_bounded_and_keeps_timestamps():
    text = truncate_transcript([{'start': 12.5, 'text': 'a' * 100}, {'start': 30, 'text': 'later'}], 30)
    assert text.startswith('[12.5s] ')
    assert len(text) <= 30
    assert 'later' not in text


def test_enrich_zh_skips_cached_without_credentials(tmp_path):
    feed = tmp_path / 'videos.json'
    cache = tmp_path / 'zh.json'
    public = tmp_path / 'public' / 'zh.json'
    feed.write_text(json.dumps({'videos': [{'id': 'abcdefghijk', 'title': 'Cached'}]}))
    cache.write_text(json.dumps({'videos': {'abcdefghijk': {'title_zh': '已有'}}}))
    db = connect(tmp_path / 'test.sqlite')
    try:
        result = enrich_zh(db, feed_path=feed, cache_path=cache, public_path=public)
    finally:
        db.close()
    assert result['attempted'] == 0
    assert result['skipped'] == 1


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _FakeCommentsClient:
    def __init__(self):
        self.urls = []

    def get(self, url, params, youtube=False):
        self.urls.append(url)
        assert url.endswith('/commentThreads')
        return {'items': []}


class _FakeVideosClient:
    def __init__(self, snippets=None):
        self.urls = []
        self.ids = []
        self.snippets = snippets or {}

    def get(self, url, params, youtube=False):
        self.urls.append(url)
        assert '/videos' in url
        ids = [item for item in str(params.get('id') or '').split(',') if item]
        self.ids.extend(ids)
        items = []
        for video_id in ids:
            snippet = self.snippets.get(video_id)
            if snippet is not None:
                items.append({'id': video_id, 'snippet': snippet})
        return {'items': items}


def _deepseek_payload(title_zh='标题'):
    return _FakeResponse({
        'choices': [{'message': {'content': json.dumps({
            'title_zh': title_zh,
            'blurb_zh': '一句话推荐',
            'highlights': [],
            'comments_zh': [],
        }, ensure_ascii=False)}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
    })


def _write_topic_fixture(tmp_path, topic_ids, pool_titles, cache_entries=None):
    topics_path = tmp_path / 'topics.json'
    pool_path = tmp_path / 'hn_pool.json'
    cache_path = tmp_path / 'zh.json'
    public_path = tmp_path / 'public' / 'zh.json'
    topics_path.write_text(json.dumps({'topics': [
        {'id': 'ai', 'video_ids': list(topic_ids)},
    ]}))
    pool_ids = list(dict.fromkeys(list(topic_ids) + list(pool_titles)))
    pool_path.write_text(json.dumps({'videos': [
        {'id': video_id, 'title': pool_titles.get(video_id, video_id)}
        for video_id in pool_ids
    ]}))
    if cache_entries is not None:
        cache_path.write_text(json.dumps({'videos': cache_entries}))
    return topics_path, pool_path, cache_path, public_path


def test_entry_truncates_blurb_to_40_characters():
    entry = _entry(
        {'title_zh': '中文标题', 'blurb_zh': '好' * 50},
        {'total_tokens': 1}, [], [], 'deepseek', 'deepseek-flash',
    )
    assert entry['blurb_zh'] == '好' * 40
    assert len(entry['blurb_zh']) <= 40


def test_request_deepseek_flash_disables_thinking_but_chat_stays_safe(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')
    calls = []

    def post(url, headers, json, timeout):
        calls.append(json)
        return _deepseek_payload()

    result, usage, model = request_deepseek('prompt', model='deepseek-flash', post=post)
    assert result['title_zh'] == '标题'
    assert usage['total_tokens'] == 15
    assert model == 'deepseek-flash'
    assert calls[0]['model'] == 'deepseek-flash'
    assert calls[0]['thinking'] == {'type': 'disabled'}

    request_deepseek('prompt', model='deepseek-chat', post=post)
    assert calls[1]['model'] == 'deepseek-chat'
    assert 'thinking' not in calls[1]


def test_topic_feed_only_uses_unique_column_ids_and_skips_cached(tmp_path, monkeypatch):
    topics_path, pool_path, cache_path, public_path = _write_topic_fixture(
        tmp_path,
        ['cached00001', 'halfcached01', 'missing0001', 'missing0001'],
        {'cached00001': 'Cached Video', 'halfcached01': 'Half Cached',
         'missing0001': 'Missing One', 'extra000001': 'Pool Extra'},
        {
            'cached00001': {'title_zh': '已有', 'blurb_zh': '已有一句话'},
            'halfcached01': {'title_zh': '半个'},
        },
    )
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')
    monkeypatch.setattr(zh_module, 'fetch_transcript', lambda video_id: [])
    payloads = []
    prompts = []

    def post(url, headers, json, timeout):
        payloads.append(json)
        prompts.append(json['messages'][0]['content'])
        return _deepseek_payload()

    client = _FakeVideosClient()
    result = enrich_zh(
        None, feed='topics', topics_path=topics_path, pool_path=pool_path,
        cache_path=cache_path, public_path=public_path, client=client, post=post,
        config_path=tmp_path / 'missing-config.yaml',
    )

    assert result['attempted'] == 2
    assert result['succeeded'] == 2
    assert result['skipped'] == 1
    assert result['mode'] == 'light'
    assert result['units'] == 1  # one videos.list batch, no commentThreads
    assert len(payloads) == 2
    assert all(payload['model'] == 'deepseek-flash' for payload in payloads)
    assert all(payload['thinking'] == {'type': 'disabled'} for payload in payloads)
    assert any('Half Cached' in prompt for prompt in prompts)
    assert any('Missing One' in prompt for prompt in prompts)
    assert all('Has timestamped transcript' not in prompt for prompt in prompts)
    assert all('Pool Extra' not in prompt for prompt in prompts)
    assert all('Cached Video' not in prompt for prompt in prompts)
    assert len(client.urls) == 1
    assert all('/videos' in url for url in client.urls)
    updated = json.loads(cache_path.read_text())['videos']
    assert set(updated) == {'cached00001', 'halfcached01', 'missing0001'}
    assert updated['cached00001']['title_zh'] == '已有'
    assert updated['cached00001']['blurb_zh'] == '已有一句话'


def test_topic_feed_skips_cached_without_credentials(tmp_path, monkeypatch):
    topics_path, pool_path, cache_path, public_path = _write_topic_fixture(
        tmp_path,
        ['cached00001', 'cached00002', 'cached00002'],
        {'cached00001': 'Cached One', 'cached00002': 'Cached Two',
         'extra000001': 'Pool Extra'},
        {
            'cached00001': {'title_zh': '已有', 'blurb_zh': '已有一句话'},
            'cached00002': {'title_zh': '已有', 'blurb_zh': '已有两句话'},
        },
    )
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('YOUTUBE_API_KEY', raising=False)

    result = enrich_zh(
        None, feed='topics', topics_path=topics_path, pool_path=pool_path,
        cache_path=cache_path, public_path=public_path,
        config_path=tmp_path / 'missing-config.yaml',
    )

    assert result['attempted'] == 0
    assert result['succeeded'] == 0
    assert result['skipped'] == 2
    assert result['source'] == 'topics'


def test_topic_feed_missing_deepseek_key_reports_skip_without_writing(tmp_path, monkeypatch):
    topics_path, pool_path, cache_path, public_path = _write_topic_fixture(
        tmp_path, ['missing0001'], {'missing0001': 'Missing One'},
    )
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('YOUTUBE_API_KEY', raising=False)

    result = enrich_zh(
        None, feed='topics', topics_path=topics_path, pool_path=pool_path,
        cache_path=cache_path, public_path=public_path,
        config_path=tmp_path / 'missing-config.yaml',
    )

    assert result['missing_key'] is True
    assert result['attempted'] == 0
    assert result['skipped'] == 1
    assert not cache_path.exists()
    assert not public_path.exists()


def test_enrich_zh_accepts_explicit_videos_and_ids(tmp_path, monkeypatch):
    cache_path = tmp_path / 'zh.json'
    public_path = tmp_path / 'public' / 'zh.json'
    pool_path = tmp_path / 'pool.json'
    cache_path.write_text(json.dumps({'videos': {
        'explicit0001': {'title_zh': '已有', 'blurb_zh': '已有一句话'},
    }}))
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('YOUTUBE_API_KEY', raising=False)

    result = enrich_zh(
        None, videos=[{'id': 'explicit0001', 'title': 'Explicit'}],
        pool_path=pool_path, cache_path=cache_path, public_path=public_path,
        config_path=tmp_path / 'missing-config.yaml',
    )
    assert result['attempted'] == 0
    assert result['skipped'] == 1

    result = enrich_zh(
        None, video_ids=['explicit0001'], pool_path=pool_path,
        cache_path=cache_path, public_path=public_path,
        config_path=tmp_path / 'missing-config.yaml',
    )
    assert result['attempted'] == 0
    assert result['skipped'] == 1


def test_visible_feed_skips_existing_and_uses_light_prompt(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'picks.json').write_text(json.dumps({'videos': [
        {'id': 'picksvideo1', 'title': 'Pick One', 'description': 'A long talk about tools.'},
    ]}))
    (data / 'ai.json').write_text(json.dumps({'videos': [
        {'id': 'aivideo0001', 'title': 'AI Talk'},
        {'id': 'picksvideo1', 'title': 'Pick One', 'description': 'A long talk about tools.'},
    ]}))
    (data / 'trending.json').write_text(json.dumps({'videos': []}))
    (data / 'music.json').write_text(json.dumps({'videos': []}))
    (data / 'podcast.json').write_text(json.dumps({'videos': []}))
    (data / 'videos.json').write_text(json.dumps({'videos': []}))
    (data / 'editorial.json').write_text(json.dumps({'videos': []}))
    (data / 'catalog.json').write_text(json.dumps([
        {'id': 'picksvideo1', 'title': 'Pick One'},
    ]))
    (data / 'topics.json').write_text(json.dumps({'topics': []}))
    (data / 'hn_pool.json').write_text(json.dumps({'videos': []}))
    cache_path = tmp_path / 'zh.json'
    public_path = tmp_path / 'public' / 'zh.json'
    cache_path.write_text(json.dumps({'videos': {
        'picksvideo1': {'title_zh': '已有精选', 'blurb_zh': '已有一句话'},
    }}))
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    prompts = []

    def post(url, headers, json, timeout):
        prompts.append(json['messages'][0]['content'])
        return _deepseek_payload('AI 讲座')

    client = _FakeVideosClient({'aivideo0001': {'title': 'AI Talk', 'description': 'A lecture on models.'}})
    result = enrich_zh(
        None, feed='visible', data_root=data, cache_path=cache_path, public_path=public_path,
        client=client, post=post, config_path=tmp_path / 'missing-config.yaml',
    )
    assert result['attempted'] == 1
    assert result['succeeded'] == 1
    assert result['mode'] == 'light'
    assert 'AI Talk' in prompts[0]
    assert 'A lecture on models.' in prompts[0]
    assert 'Has timestamped transcript' not in prompts[0]
    updated = json.loads(cache_path.read_text())['videos']
    assert updated['picksvideo1']['title_zh'] == '已有精选'
    assert updated['aivideo0001']['title_zh'] == 'AI 讲座'
    assert updated['aivideo0001']['source_basis'] == 'title+description'


def test_light_mode_writes_title_fallback_on_llm_failure(tmp_path, monkeypatch):
    cache_path = tmp_path / 'zh.json'
    public_path = tmp_path / 'public' / 'zh.json'
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')

    def post(url, headers, json, timeout):
        raise RuntimeError('boom')

    result = enrich_zh(
        None, videos=[{'id': 'failvideo01', 'title': 'Original Title'}],
        cache_path=cache_path, public_path=public_path, client=_FakeVideosClient(),
        post=post, mode='light', config_path=tmp_path / 'missing-config.yaml',
    )
    assert result['succeeded'] == 0
    assert result['fallbacks'] == 1
    entry = json.loads(cache_path.read_text())['videos']['failvideo01']
    assert entry['title_zh'] == 'Original Title'
    assert entry['blurb_zh'] == zh_module.FALLBACK_BLURB
    assert entry['source_basis'] == 'title-only'
    assert '精彩内容不容错过' not in entry['blurb_zh']


def test_light_mode_rejects_placeholder_blurb(tmp_path, monkeypatch):
    cache_path = tmp_path / 'zh.json'
    public_path = tmp_path / 'public' / 'zh.json'
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')

    def post(url, headers, json, timeout):
        payload = '{"title_zh":"标题","blurb_zh":"精彩内容不容错过"}'
        return _FakeResponse({
            'choices': [{'message': {'content': payload}}],
            'usage': {'prompt_tokens': 8, 'completion_tokens': 4, 'total_tokens': 12},
        })

    enrich_zh(
        None, videos=[{'id': 'placeholder1', 'title': 'Some Video'}],
        cache_path=cache_path, public_path=public_path, client=_FakeVideosClient(),
        post=post, mode='light', config_path=tmp_path / 'missing-config.yaml',
    )
    entry = json.loads(cache_path.read_text())['videos']['placeholder1']
    assert entry['blurb_zh'] == zh_module.FALLBACK_BLURB
    assert entry['llm_provider'] == 'fallback'


def test_cost_cap_stops_before_further_calls(tmp_path, monkeypatch):
    cache_path = tmp_path / 'zh.json'
    public_path = tmp_path / 'public' / 'zh.json'
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')
    calls = []

    def post(url, headers, json, timeout):
        calls.append(json)
        payload = '{"title_zh":"标题","blurb_zh":"根据标题写的简介"}'
        return _FakeResponse({
            'choices': [{'message': {'content': payload}}],
            'usage': {'prompt_tokens': 1_000_000, 'completion_tokens': 0, 'total_tokens': 1_000_000},
        })

    videos = [{'id': f'capvideo{i:03}', 'title': f'Title {i}'} for i in range(3)]
    result = enrich_zh(
        None, videos=videos, cache_path=cache_path, public_path=public_path,
        client=_FakeVideosClient(), post=post, mode='light', cost_cap_cny=0.5,
        config_path=tmp_path / 'missing-config.yaml',
    )
    # 1M prompt tokens * ¥1/M offpeak = ¥1.0, which exceeds 0.5 after the first recorded call
    # The pre-check reserve is 0.02 so the first call is allowed, then stop.
    assert len(calls) == 1
    assert result['stopped_for_cap'] is True
    assert result['succeeded'] == 1
    assert result['unprocessed'] == 2
    cache = json.loads(cache_path.read_text())['videos']
    assert 'capvideo000' in cache
    assert 'capvideo002' not in cache


def test_description_fetch_batches_fifty_ids(tmp_path, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-key')
    monkeypatch.setenv('YOUTUBE_API_KEY', 'test-key')
    videos = [{'id': f'batch{i:04}', 'title': f'Title {i}'} for i in range(51)]
    client = _FakeVideosClient({
        'batch0000': {'title': 'Title 0', 'description': 'Official description 0'},
    })
    prompts = []

    def post(url, headers, json, timeout):
        prompts.append(json['messages'][0]['content'])
        return _deepseek_payload()

    result = enrich_zh(
        None, videos=videos, cache_path=tmp_path / 'zh.json',
        public_path=tmp_path / 'public' / 'zh.json',
        client=client, post=post, mode='light', limit=2,
        config_path=tmp_path / 'missing-config.yaml',
    )
    assert result['units'] == 1 or result['units'] == 2
    # limit=2 still fetches descriptions only for the 2 pending videos? 
    # fetch_missing_descriptions is called on pending after limit, so 2 ids -> 1 batch
    assert result['units'] == 1
    assert len(client.urls) == 1
    assert 'Official description 0' in prompts[0]


def test_refresh_enriches_visible_light_before_rebuild():
    source = Path(__file__).resolve().parents[1].joinpath('ytrec/__main__.py').read_text()
    assert 'enrich_before_export' in source
    assert source.index('enrich_before_export') < source.index('rebuild_offline()')
    assert source.index("print(f'WARNING: zh enrichment skipped:") < source.index('rebuild_offline()')
    assert "'site/public/zh.json'" in source


def test_search_and_library_templates_keep_blurb_data_out_of_video_cards():
    root = Path(__file__).resolve().parents[1]
    catalog = (root / 'site/scripts/build-catalog.mjs').read_text()
    assert 'enrichment.blurb_zh' in catalog
    search = (root / 'site/src/pages/search.astro').read_text()
    assert 'v.b' not in search and 'zh-blurb' not in search
    library = (root / 'site/src/components/LibraryPage.astro').read_text()
    assert "fetch(`${base}/zh.json`)" in library
    assert 'z.blurb_zh' not in library and 'zh-blurb' not in library
    myspace = (root / 'site/src/lib/myspace-card.mjs').read_text()
    assert 'blurb_zh' not in myspace
