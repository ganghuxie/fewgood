from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_safe_redirect_allows_single_slash_paths_and_rejects_redirect_forms():
    source = read('site/src/scripts/supabase.js')
    assert "!value.startsWith('/')" in source
    assert "value.startsWith('//')" in source
    assert "value.startsWith('/\\\\')" in source
    assert "value.includes('\\\\')" in source
    assert 'return value;' in source
    assert '/^(?:' not in source


def test_email_callback_is_stable_base_url_with_a_sanitized_redirect():
    source = read('site/src/scripts/supabase.js')
    assert 'const callback = new URL(import.meta.env.BASE_URL, location.origin);' in source
    assert "current.searchParams.delete('redirect');" in source
    assert "callback.searchParams.set('redirect', redirect);" in source
    assert 'new URL(redirect, location.origin)' not in source


def test_google_oauth_uses_explicit_redirect_and_visible_errors_without_popup():
    source = read('site/src/components/AuthMenu.astro')
    assert 'skipBrowserRedirect: true' in source
    assert 'location.assign(data.url)' in source
    assert 'window.open' not in source
    assert 'setMessage(friendlyError(error' in source


def test_signed_in_and_session_restore_consume_safe_redirects():
    source = read('site/src/components/AuthMenu.astro')
    assert 'const consumeRedirect' in source
    assert "safeRedirect(requested, '')" in source
    assert 'location.replace(target)' in source
    assert "event === 'SIGNED_IN'" in source
    assert 'consumeRedirect();' in source


def test_library_routes_use_dedicated_page_with_back_link_and_titles():
    page = read('site/src/components/LibraryPage.astro')
    assert 'library-back' in page and '返回' in page
    for path, title in (
        ('site/src/pages/history.astro', '历史'),
        ('site/src/pages/favorites.astro', '收藏'),
        ('site/src/pages/watch-later.astro', '稍后观看'),
    ):
        source = read(path)
        assert 'LibraryPage' in source and f'title="{title}"' in source


def test_drawer_links_and_auth_hook_use_shared_session_ui():
    source = read('site/src/components/Sidebar.astro')
    for href in ('/favorites/', '/history/', '/about/', '/about/#feedback'):
        assert f"link('{href}')" in source
    assert 'data-sidebar-auth' in source
    assert "document.querySelector('[data-auth-open]')?.click()" in source
    assert "document.querySelector('[data-auth-signout]')?.click()" in source
    assert 'width:80vw' in source


def test_mobile_header_has_one_four_item_sticky_row_and_nonsticky_controls():
    header = read('site/src/components/Header.astro')
    layout = read('site/src/components/Layout.astro')
    row, after_row = header.split('</div>', 1)
    assert 'mode-switch' not in row and 'class="search"' not in row and 'chipbar' not in row
    assert 'grid-template-areas:"menu logo library auth"' in header
    assert '.libraries .lib-item:not([data-lib-kind="watchLater"])' in header
    assert 'href={link(\'/watch-later/\')}' in header
    assert '.site-header .search input){height:36px}' in header
    assert '.header-row{position:sticky!important' in layout
    assert '.site-header{position:static!important}' in layout


def test_watch_later_tooltip_has_left_placement_timing_and_unclipped_icon():
    source = read('site/src/scripts/search-watch-later.js')
    assert 'right:calc(100% + 8px)' in source
    assert 'top:50%;transform:translateY(-50%)' in source
    assert 'transition-delay:150ms' in source
    assert 'visibility 0s linear .05s' in source
    assert 'background:rgba(255,255,255,.9)!important' in source
    assert 'border-radius:6px!important' in source
    assert '.thumbnail,.sr-thumbnail{overflow:visible}' in source
    assert 'data-tooltip-side="below"' in source
