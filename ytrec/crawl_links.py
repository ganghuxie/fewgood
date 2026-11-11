"""Crawl the built site for broken internal href/src and JS-provided targets.

The checker is intentionally dependency-free so the refresh pipeline and CI
can run it with the system Python.  It resolves same-origin paths (queries and
fragments do not affect file lookup), parses the inline ``feed-data`` payload
used by infinite scroll, and verifies the JSON assets and /v/ ids the client
renders at runtime.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

SKIP_SCHEMES = {'mailto', 'javascript', 'tel', 'data', 'blob', 'about', 'ftp'}
DEFAULT_SITE_HOSTS = {'fewgood.io', 'www.fewgood.io'}
PUBLIC_JSON = (
    'catalog.json', 'channels.json', 'hn_pool.json', 'search-index.json',
    'templates.json', 'topic_lookup.json', 'topics.json',
)


@dataclass(frozen=True, order=True)
class BrokenLink:
    source: str
    target: str
    kind: str

    def __str__(self):
        return f'{self.source}: {self.target} ({self.kind})'


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.feed_payloads = []
        self._capture = False
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ('href', 'src', 'poster') and value:
                self.links.append((tag, name, value))
        if tag == 'script' and dict(attrs).get('id') == 'feed-data':
            self._capture = True
            self._buffer = []

    def handle_data(self, data):
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self._capture:
            self.feed_payloads.append(''.join(self._buffer))
            self._capture = False


def _hosts(site='https://fewgood.io'):
    hosts = set(DEFAULT_SITE_HOSTS)
    host = (urlparse(site).hostname or '').lower()
    if host:
        hosts.add(host)
    return hosts


def _normalize_path(path, page_path):
    if not path.startswith('/'):
        base = page_path if page_path.endswith('/') else page_path.rsplit('/', 1)[0] + '/'
        path = base + path
    parts = []
    for part in unquote(path).split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            if parts:
                parts.pop()
            continue
        parts.append(part)
    normalized = '/' + '/'.join(parts)
    if path.endswith('/') and normalized != '/':
        normalized += '/'
    return normalized


def resolve_internal(raw, page_path, *, hosts=None, base=''):
    """Return a same-origin absolute path, or None for external/ignored URLs."""
    value = str(raw or '').strip()
    if not value or value.startswith('#'):
        return None
    parsed = urlparse(value)
    scheme = (parsed.scheme or '').lower()
    if scheme in SKIP_SCHEMES:
        return None
    if scheme and scheme not in ('http', 'https'):
        return None
    if parsed.netloc:
        if (parsed.hostname or '').lower() not in (hosts or DEFAULT_SITE_HOSTS):
            return None
        path = parsed.path or '/'
    else:
        path = parsed.path
        if not path:
            return None
    if base and base != '/':
        prefix = base.rstrip('/')
        if path == prefix:
            path = '/'
        elif path.startswith(prefix + '/'):
            path = path[len(prefix):]
    return _normalize_path(path, page_path)


def target_exists(dist, target):
    dist = Path(dist)
    rel = target.lstrip('/')
    if not rel:
        return (dist / 'index.html').is_file()
    candidate = dist / rel
    if target.endswith('/'):
        return (candidate / 'index.html').is_file()
    if candidate.is_file():
        return True
    return (candidate / 'index.html').is_file()


def _page_path(relative):
    if relative.name == 'index.html':
        parent = relative.parent.as_posix()
        return '/' if parent == '.' else '/' + parent + '/'
    return '/' + relative.as_posix()


def _load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _json_video_ids(dist):
    """Yield (source, video_id) for every id the client renders as /v/."""
    catalog = _load_json(dist / 'catalog.json')
    if isinstance(catalog, list):
        for video in catalog:
            if isinstance(video, dict) and video.get('id'):
                yield 'catalog.json', video['id']

    pool = _load_json(dist / 'hn_pool.json')
    if isinstance(pool, dict):
        for video in pool.get('videos', []):
            if isinstance(video, dict) and video.get('id'):
                yield 'hn_pool.json', video['id']

    topics = _load_json(dist / 'topics.json')
    if isinstance(topics, dict):
        for topic in topics.get('topics', []):
            for video_id in topic.get('video_ids', []) if isinstance(topic, dict) else []:
                if video_id:
                    yield f"topics.json#{topic.get('id', '')}", video_id

    index = _load_json(dist / 'search-index.json')
    if isinstance(index, dict):
        for entry in index.get('videos', []):
            if not isinstance(entry, list) or len(entry) < 8 or not entry[0]:
                continue
            external = bool(entry[7])
            if not external:
                yield 'search-index.json', entry[0]


def crawl_dist(dist='site/dist', *, project_root=None, base='',
               site='https://fewgood.io', hosts=None):
    """Return a sorted list of broken internal targets in a built site."""
    dist = Path(dist)
    project_root = Path(project_root) if project_root else dist.parent.parent
    hosts = set(hosts) if hosts else _hosts(site)
    broken = set()

    def add(source, target, kind):
        broken.add(BrokenLink(source, target, kind))

    def check(source, target, kind):
        if not target_exists(dist, target):
            add(source, target, kind)

    if not dist.is_dir():
        return [BrokenLink(str(dist), '/', 'missing-dist')]

    for html_path in sorted(dist.rglob('*.html')):
        relative = html_path.relative_to(dist)
        source = _page_path(relative)
        collector = _Collector()
        try:
            collector.feed(html_path.read_text(encoding='utf8'))
        except (OSError, UnicodeDecodeError) as error:
            add(source, '/', f'html-read-error:{error.__class__.__name__}')
            continue
        for _tag, _name, raw in collector.links:
            target = resolve_internal(raw, source, hosts=hosts, base=base)
            if target is not None:
                check(source, target, f'link:{raw}')
        for payload in collector.feed_payloads:
            try:
                videos = json.loads(payload)
            except json.JSONDecodeError:
                add(source, '/', 'feed-data-json')
                continue
            for video in videos if isinstance(videos, list) else []:
                video_id = video.get('id') if isinstance(video, dict) else None
                if video_id:
                    check(source, f'/v/{video_id}/', 'feed-data')

    public_dir = project_root / 'site' / 'public'
    public_json = sorted({*PUBLIC_JSON, *[path.name for path in public_dir.glob('*.json')]})
    for name in public_json:
        if not (dist / name).is_file():
            add(f'public/{name}', f'/{name}', 'missing-json')

    page_cache = {}
    for source, video_id in _json_video_ids(dist):
        target = f'/v/{video_id}/'
        if target not in page_cache:
            page_cache[target] = target_exists(dist, target)
        if not page_cache[target]:
            add(source, target, 'json-video')

    return sorted(broken)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description='Check site/dist for broken internal links')
    parser.add_argument('--dist', default='site/dist')
    parser.add_argument('--project-root', default=None)
    parser.add_argument('--base', default='')
    parser.add_argument('--site', default='https://fewgood.io')
    args = parser.parse_args(argv)
    broken = crawl_dist(args.dist, project_root=args.project_root,
                        base=args.base, site=args.site)
    if not broken:
        print('Internal link check: 0 broken links')
        return 0
    print(f'Internal link check: {len(broken)} broken link(s)')
    for item in broken:
        print(item)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
