import json

from ytrec.core import connect, youtube_cost
from ytrec.zh import enrich_zh, parse_json_response, truncate_transcript


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
