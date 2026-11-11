import json
import subprocess
from pathlib import Path

from ytrec.crawl_links import BrokenLink, PUBLIC_JSON, crawl_dist

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
DIST = SITE / 'dist'


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf8')


def _write_json(path, payload):
    _write(path, json.dumps(payload, ensure_ascii=False))


def _required_json(dist, *, catalog=None, pool=None, topics=None, search=None):
    payloads = {
        'catalog.json': catalog if catalog is not None else [],
        'channels.json': {},
        'hn_pool.json': pool if pool is not None else {'videos': []},
        'search-index.json': search if search is not None else {'videos': []},
        'templates.json': {},
        'topic_lookup.json': {},
        'topics.json': topics if topics is not None else {'topics': []},
    }
    for name in PUBLIC_JSON:
        _write_json(dist / name, payloads[name])


def test_crawler_resolves_queries_same_origin_and_ignores_external(tmp_path):
    dist = tmp_path / 'dist'
    _write(dist / 'index.html', '''
<html><head><link href="/ok/"/></head><body>
<a href="/ok/?from=topic:ai">ok query</a>
<a href="https://fewgood.io/ok/">same origin</a>
<a href="/missing/?from=topic:ai">missing query</a>
<a href="https://youtube.com/watch?v=dQw4w9WgXcQ">external</a>
<a href="https://i.ytimg.com/vi/x/hq.jpg">external asset</a>
<a href="mailto:test@example.com">mail</a>
<a href="javascript:void(0)">js</a>
<a href="#hash">hash</a>
<img src="/assets/a.png"/>
<script type="application/json" id="feed-data">[{"id":"vid00000001"}]</script>
</body></html>
''')
    _write(dist / 'ok' / 'index.html', '<html></html>')
    _write(dist / 'v' / 'vid00000001' / 'index.html', '<html></html>')
    _write(dist / 'assets' / 'a.png', 'png')
    _required_json(dist, catalog=[{'id': 'vid00000001'}])

    broken = crawl_dist(dist, project_root=tmp_path)
    assert [(item.source, item.target) for item in broken] == [('/', '/missing/')]
    assert broken[0].kind == 'link:/missing/?from=topic:ai'


def test_crawler_checks_search_internal_ids_and_topics(tmp_path):
    dist = tmp_path / 'dist'
    _write(dist / 'index.html', '<html></html>')
    _write(dist / 'v' / 'present0001' / 'index.html', '<html></html>')
    _required_json(
        dist,
        catalog=[{'id': 'present0001'}],
        pool={'videos': [{'id': 'poolmiss001'}]},
        topics={'topics': [{'id': 'topic-a', 'video_ids': ['topicmiss1']}]},
        search={'videos': [
            ['searchmiss1', 'internal', 0, '', '', 0, 0, False],
            ['external001', 'external', 0, '', '', 0, 0, True],
        ]},
    )

    broken = crawl_dist(dist, project_root=tmp_path)
    targets = {(item.source, item.target) for item in broken}
    assert ('hn_pool.json', '/v/poolmiss001/') in targets
    assert ('topics.json#topic-a', '/v/topicmiss1/') in targets
    assert ('search-index.json', '/v/searchmiss1/') in targets
    assert all('external001' not in item.target for item in broken)


def _dist_is_stale():
    index = DIST / 'index.html'
    if not index.exists():
        return True
    marker = index.stat().st_mtime
    for base in (SITE / 'src', SITE / 'public', SITE / 'scripts'):
        for path in base.rglob('*'):
            if path.is_file() and path.stat().st_mtime > marker:
                return True
    for name in ('package.json', 'astro.config.mjs'):
        if (SITE / name).stat().st_mtime > marker:
            return True
    return False


def test_built_dist_has_no_broken_internal_links():
    if _dist_is_stale():
        subprocess.run(['npm', 'run', 'build'], cwd=SITE, check=True)
    broken = crawl_dist(DIST, project_root=ROOT)
    assert broken == [], '\n'.join(str(item) for item in broken[:50])
