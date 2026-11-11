import json
from pathlib import Path

from ytrec.build_topics import is_news_recap_title, retag_topic_lookup

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
        columns = template['columns']
        assert 4 <= len(columns) <= 5, template['id']
        for column in columns:
            assert column['kind'] in {'feed', 'topic'}, (template['id'], column)
            column_id = column.get('source') if column['kind'] == 'feed' else column.get('topic_id')
            column_id = column_id or column.get('id')
            assert column_id, (template['id'], column)
            if column['kind'] != 'topic':
                continue
            assert column_id in topics, f"{template['id']} references missing {column_id}"
            assert len(topics[column_id]['video_ids']) >= 6, f"{template['id']} column {column_id} under 6 videos"


def test_ai_practitioner_template_uses_live_ai_feed():
    templates = {template['id']: template for template in _templates()['templates']}
    columns = templates['ai-practitioner']['columns']
    assert len(columns) == 5
    feeds = [column.get('source') or column.get('id') for column in columns if column['kind'] == 'feed']
    topic_ids = [column.get('topic_id') or column.get('id') for column in columns if column['kind'] == 'topic']
    assert feeds == ['ai']
    assert topic_ids == ['ai', 'programming', 'mit', 'systems']


def test_public_templates_match_source():
    public = json.loads((ROOT / 'site/public/templates.json').read_text())
    assert _templates() == public


def test_hot_topics_strip_is_hidden_when_no_topic_added_today():
    topics = _topics()['topics']
    hot = [topic for topic in topics if int(topic.get('added_last_24h') or 0) > 0]
    assert hot == []
    script = (ROOT / 'site/src/scripts/myspace.js').read_text()
    assert 'topics.filter(topic => Number(topic.added_last_24h) > 0)' in script
    assert 'host.hidden = !hot.length' in script


def test_pool_ids_have_a_primary_topic():
    pool = _pool()
    lookup = json.loads((ROOT / 'site/src/data/topic_lookup.json').read_text())
    missing = [video['id'] for video in pool if video['id'] not in lookup]
    assert not missing


def test_news_recap_is_not_retagged_as_classic_talk():
    lookup = {
        'news-recap': 'classic-talks',
        'real-ted': 'classic-talks',
        'commencement': 'classic-talks',
    }
    metadata = {
        'news-recap': {'title': 'Google Loses $500B in 12 Hours | DoorDash Buys Instacart for $17B | Kalshi Raises $1B'},
        'real-ted': {'title': 'How Great Leaders Inspire Action | Simon Sinek | TED'},
        'commencement': {'title': 'Steve Jobs Stanford Commencement Speech 2005'},
    }
    retagged, changed = retag_topic_lookup(lookup, metadata)
    assert is_news_recap_title(metadata['news-recap']['title'])
    assert not is_news_recap_title(metadata['real-ted']['title'])
    assert not is_news_recap_title(metadata['commencement']['title'])
    assert changed == 1
    assert 'news-recap' not in retagged
    assert retagged['real-ted'] == 'classic-talks'
    assert retagged['commencement'] == 'classic-talks'


def test_20vc_news_episode_has_no_classic_talk_chip():
    lookup = json.loads((ROOT / 'site/src/data/topic_lookup.json').read_text())
    assert lookup.get('4nKt18AZDsQ') != 'classic-talks'
