import pytest
from ytrec.links import extract_ids, video_id
V = 'dQw4w9WgXcQ'
@pytest.mark.parametrize('url', [
 f'https://youtube.com/watch?v={V}', f'http://www.youtube.com/watch?feature=share&v={V}&t=12',
 f'youtube.com/watch?v={V}&t=2', f'https://youtu.be/{V}?t=10', f'http://youtu.be/{V}&t=10',
 f'https://m.youtube.com/watch?v={V}', f'https://music.youtube.com/watch?v={V}',
 *[f'https://www.youtube.com/{p}/{V}?t=5' for p in ('embed','shorts','live','v')],
 f'https://www.youtube-nocookie.com/embed/{V}', f'//youtube.com/watch?v={V}',
 f'https://youtube.com/attribution_link?u=%2Fwatch%3Fv%3D{V}%26feature%3Dshare',
 f'https:&#x2F;&#x2F;youtube.com&#x2F;watch?v={V}&amp;t=1',
])
def test_urls(url):
    assert extract_ids(f'<a href="{url}">video</a>') == {V}

@pytest.mark.parametrize('url', ['https://youtube.com/channel/abcdefghijk','https://youtube.com/@someone', 'https://youtube.com/playlist?list=abcdefghijk', 'https://youtube.com/watch?v=short', 'https://youtube.com/watch?v=abcdefghijkl', 'https://evil.com/watch?v=dQw4w9WgXcQ', 'https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ', 'https://notyoutube.com/watch?v=dQw4w9WgXcQ'])
def test_negative(url):
    assert extract_ids(url) == set()
    assert video_id(url) is None

def test_dedup_and_plain_html():
    assert extract_ids(f'https://youtu.be/{V} https://youtube.com/watch?feature=x&amp;v={V}') == {V}

@pytest.mark.parametrize('url', [
    f'http://[youtube.com/watch?v={V}',
    'https://youtu.be/]',
    f'https://youtube.com/watch?v={V}&x=[oops',
    f'https://youtube.com/watch?v={V}&x=%FF',
    f'https://youtube.com/watch?v={V}&x=%ED%A0%80',
    f'https://youtube.com/watch?v={V}&x=%zz',
    f'https://youtube.com/watch?v={V}&x=%',
    f'https://youtube.com/attribution_link?u=http%3A%2F%2F%5Byoutube.com%2Fwatch%3Fv%3D{V}',
    f'https://youtube.com/attribution_link?u=%2Fwatch%3Fv%3D{V}%26x%3D%25FF',
    f'https://youtube.com\uff0f.example/watch?v={V}',
])
def test_malformed_urls(url):
    assert video_id(url) is None
    assert extract_ids(url) == set()
    assert extract_ids(f'{url} https://youtu.be/{V}') == {V}

@pytest.mark.parametrize('wrapped', [f'(https://youtu.be/{V})',
    f'[https://youtu.be/{V}]', f'[video](https://youtu.be/{V})',
    f'(https://youtube.com/watch?v={V}).'])
def test_markdown_punctuation(wrapped):
    assert extract_ids(wrapped) == {V}

@pytest.mark.parametrize('parser', ['urlparse', 'parse_qs', 'unquote'])
def test_parser_errors_are_local(monkeypatch, parser):
    import ytrec.links as links
    original = getattr(links, parser)
    def fail_bad(value, *args, **kwargs):
        if 'bad' in value:
            raise ValueError('malformed URL')
        return original(value, *args, **kwargs)
    monkeypatch.setattr(links, parser, fail_bad)
    assert extract_ids(f'https://youtube.com/watch?bad=1 https://youtu.be/{V}') == {V}
