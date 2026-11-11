import json
from pathlib import Path

from ytrec.thumbnails import (
    backfill_thumbnail_sizes,
    jpeg_dimensions,
    probe_thumbnail,
    thumbnail_url,
)


def _jpeg(width, height):
    sof = b'\x08' + height.to_bytes(2, 'big') + width.to_bytes(2, 'big') + b'\x03' + b'\x00' * 9
    return b'\xff\xd8\xff\xe0\x00\x02\xff\xc0' + (len(sof) + 2).to_bytes(2, 'big') + sof


class Response:
    def __init__(self, width=None, height=None, status=200):
        self.status_code = status
        self.payload = _jpeg(width, height) if width and height else b''

    def iter_content(self, _size):
        if self.payload:
            yield self.payload


class Session:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    def get(self, url, **_kwargs):
        self.urls.append(url)
        return self.responses[url.rsplit('/', 1)[-1]]


def test_jpeg_dimensions_reads_sof_segment():
    assert jpeg_dimensions(_jpeg(480, 360)) == (480, 360)
    assert jpeg_dimensions(b'not-a-jpeg') is None


def test_probe_skips_grey_placeholder_and_uses_hqdefault():
    video_id = 'hQVTIJBZook'
    session = Session({
        'maxresdefault.jpg': Response(120, 90),
        'hqdefault.jpg': Response(480, 360),
        'mqdefault.jpg': Response(320, 180),
    })
    result = probe_thumbnail(video_id, session=session)
    assert result == {'kind': 'hqdefault', 'url': thumbnail_url(video_id, 'hqdefault')}
    assert session.urls == [thumbnail_url(video_id, 'maxresdefault'), thumbnail_url(video_id, 'hqdefault')]


def test_probe_uses_verified_maxres_when_real():
    video_id = 'jVkLVRt6c1U'
    session = Session({'maxresdefault.jpg': Response(1280, 720, status=206)})
    assert probe_thumbnail(video_id, session=session) == {
        'kind': 'maxresdefault',
        'url': thumbnail_url(video_id, 'maxresdefault'),
    }


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + '\n')


def test_backfill_persists_preferred_thumb_in_all_sources(tmp_path):
    root = tmp_path / 'data'
    bad = {'id': 'hQVTIJBZook', 'title': 'JavaScript: The Good Parts'}
    good = {'id': 'jVkLVRt6c1U', 'title': 'F*ck You, Pay Me'}
    _write(root / 'picks.json', {'videos': [dict(bad), dict(good)]})
    _write(root / 'catalog.json', [dict(bad), dict(good)])
    _write(root / 'hn_pool.json', {'videos': [dict(bad)]})
    cache = tmp_path / 'thumbnails.json'

    def probe(video_id, **_kwargs):
        kind = 'maxresdefault' if video_id == good['id'] else 'hqdefault'
        return {'kind': kind, 'url': thumbnail_url(video_id, kind)}

    summary = backfill_thumbnail_sizes(root=root, cache_path=cache, probe=probe)
    assert summary == {'checked': 2, 'from_cache': 0, 'updated': 5, 'network_failures': 0}
    for name in ('picks', 'catalog', 'hn_pool'):
        payload = json.loads((root / f'{name}.json').read_text())
        videos = payload if isinstance(payload, list) else payload['videos']
        for video in videos:
            kind = 'maxresdefault' if video['id'] == good['id'] else 'hqdefault'
            assert video['thumb'] == thumbnail_url(video['id'], kind)
            assert video['thumb_kind'] == kind
            assert video['thumb_verified'] is True
    assert set(json.loads(cache.read_text())['entries']) == {bad['id'], good['id']}


def test_backfill_leaves_files_unchanged_when_cdn_is_down(tmp_path):
    root = tmp_path / 'data'
    _write(root / 'picks.json', {'videos': [{'id': f'video{index:06d}'} for index in range(8)]})
    before = (root / 'picks.json').read_text()

    def offline(_video_id, **_kwargs):
        raise OSError('network down')

    summary = backfill_thumbnail_sizes(
        root=root, cache_path=tmp_path / 'thumbnails.json', probe=offline,
        max_network_failures=3,
    )
    assert summary['network_failures'] == 3
    assert summary['updated'] == 0
    assert (root / 'picks.json').read_text() == before
    assert not (tmp_path / 'thumbnails.json').exists()
