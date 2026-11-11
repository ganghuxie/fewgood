import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _topics():
    return json.loads((ROOT / 'site/src/data/topics.json').read_text())


def _templates():
    return json.loads((ROOT / 'site/src/data/templates.json').read_text())


def test_shipped_topic_count_is_honest():
    payload = _topics()
    assert 1 <= payload['count'] <= 25
    assert len(payload['topics']) == payload['count']


def test_every_topic_has_enough_videos_and_keywords():
    for topic in _topics()['topics']:
        assert len(topic['video_ids']) >= 8, topic['id']
        assert len(set(topic['video_ids'])) == len(topic['video_ids']), topic['id']
        assert len(topic['keywords']) >= 5, topic['id']
        assert topic['name_zh'] and topic['aliases_en']
        assert topic['source_channel_ids']


def test_templates_reference_known_topics_with_six_videos():
    topics = {topic['id']: topic for topic in _topics()['topics']}
    templates = _templates()['templates']
    assert len(templates) == 3
    for template in templates:
        assert 4 <= len(template['topic_ids']) <= 5, template['id']
        for topic_id in template['topic_ids']:
            assert topic_id in topics, f"{template['id']} references missing {topic_id}"
            assert len(topics[topic_id]['video_ids']) >= 6, f"{template['id']} column {topic_id} under 6 videos"


def test_pool_ids_have_a_primary_topic():
    pool = json.loads((ROOT / 'site/src/data/hn_pool.json').read_text())['videos']
    lookup = json.loads((ROOT / 'site/src/data/topic_lookup.json').read_text())
    missing = [video['id'] for video in pool if video['id'] not in lookup]
    assert not missing
