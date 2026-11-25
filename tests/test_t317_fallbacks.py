from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_static_404_recovers_rotated_video_from_local_snapshots():
    page = read('site/src/pages/404.astro')
    assert "import Layout from '../components/Layout.astro'" in page
    assert "location.pathname.match(/\\/v\\/([^/]+)\\/?$/)" in page
    assert '<div data-not-found-generic>' in page
    assert '<div data-not-found-generic hidden>' not in page
    assert '<article data-not-found-video hidden>' in page
    assert "const validId = value => /^[A-Za-z0-9_-]{11}$/.test(value || '');" in page
    assert '{6,}' not in page
    for key in ('youtuber:watchLater', 'youtuber:favorites', 'youtuber:history', 'fewgood.watchLater', 'fewgood.favorites', 'fewgood.history'):
        assert key in page
    assert 'https://www.youtube.com/embed/${encodeURIComponent(id)}' in page
    assert 'https://www.youtube.com/watch?v=${encodeURIComponent(id)}' in page
    valid_branch = page.split('if (validId(id)) {', 1)[1]
    assert "document.createElement('iframe')" in valid_branch
    assert "document.createElement('iframe')" not in page.split('if (validId(id)) {', 1)[0]


def test_library_and_header_never_render_missing_video_ids_or_unencoded_links():
    for path in ('site/src/components/LibraryPage.astro', 'site/src/components/LibraryTabs.astro', 'site/src/components/Header.astro'):
        source = read(path)
        assert 'renderable = item =>' in source
        assert '.filter(renderable)' in source
        assert 'encodeURIComponent(' in source
    assert 'readItems = () => (kind === \'watchLater\' ? watchLaterItems() : list(KEYS[kind])).filter(renderable)' in read('site/src/components/LibraryTabs.astro')


def test_synthetic_channel_never_gets_an_empty_playlist_link():
    page = read('site/src/pages/channel/[id].astro')
    assert 'const youtubeUrl = channel.uploads_playlist_id' in page
    assert "String(channel.id || '').startsWith('UC')" in page
    assert '{youtubeUrl && <a class="youtube" href={youtubeUrl}' in page
    assert 'playlist?list=${channel.uploads_playlist_id}' in page


def test_avatar_thumbnail_and_search_focus_regressions_are_guarded():
    avatar = read('site/src/components/AuthMenu.astro')
    thumbs = read('site/src/scripts/thumbnails.js')
    layout = read('site/src/components/Layout.astro')
    assert '.auth-avatar-visual :global(img){display:block;width:100%;height:100%;object-fit:cover}' in avatar
    assert 'min-width:0;min-height:0' in avatar
    assert "image.removeAttribute('srcset');" in thumbs
    assert '.search:focus-within{outline:none;border-radius:20px;box-shadow:0 0 0 2px rgba(73,201,135,.3)}' in layout
    assert 'outline-offset:2px' not in layout
