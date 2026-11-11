import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _topics():
    return json.loads((ROOT / 'site/src/data/topics.json').read_text())


def _templates():
    return json.loads((ROOT / 'site/src/data/templates.json').read_text())


def _pool():
    return json.loads((ROOT / 'site/src/data/hn_pool.json').read_text())['videos']


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


def test_topic_display_names_are_unique():
    names = [topic['name_zh'] for topic in _topics()['topics']]
    assert len(names) == len(set(names))


def test_ai_topic_excludes_obvious_misplacements():
    topics = {topic['id']: topic for topic in _topics()['topics']}
    pool = {video['id']: video for video in _pool()}
    ai_titles = [(pool[video_id].get('title') or '').lower()
                 for video_id in topics['ai']['video_ids'] if video_id in pool]
    forbidden_titles = [
        'ruby on rails demo',
        "how we solved the worst minigame in zelda's history",
        'backyard squirrel maze 1.0',
        "the world's worst video card",
        'how does a usb keyboard work',
        'from scratch on a 6502',
        'building the perfect linux pc with linus torvalds',
        'steve jobs presents to the cupertino city council',
        'worst nuclear accidents in history',
        'elevator hacking: from the pit to the penthouse',
        'the insane battle to sabotage a new apartment building',
        'everything is a remix (original series)',
        'leap technology',
        'future computers will be radically different',
    ]
    for title in forbidden_titles:
        assert not any(title in ai_title for ai_title in ai_titles), title


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
    pool = _pool()
    lookup = json.loads((ROOT / 'site/src/data/topic_lookup.json').read_text())
    missing = [video['id'] for video in pool if video['id'] not in lookup]
    assert not missing
