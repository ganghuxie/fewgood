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
