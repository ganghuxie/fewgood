from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_stage1_header_has_desktop_single_row_and_mobile_four_item_contract():
    header = read('site/src/components/Header.astro')
    layout = read('site/src/components/Layout.astro')
    assert 'data-header-mode-switch' in header
    assert '我的空间' in header and '探索世界' in header
    assert 'placeholder="搜索精选池"' in header
    assert 'href={link(\'/watch-later/\')}' in header
    assert '更新于 {updated}' in header
    assert 'contain:layout' in layout or 'contain:layout' in header
    assert 'grid-template-areas:"menu logo library auth"' in header


def test_stage1_library_tabs_use_existing_storage_and_independent_routes():
    tabs = read('site/src/components/LibraryTabs.astro')
    assert 'KEYS[kind]' in tabs
    assert 'migrate(KEYS[kind]' in tabs
    assert '稍后观看是空的' in tabs
    assert '还没有收藏视频' in tabs
    assert '还没有观看历史' in tabs
    assert 'LibraryTabs' in read('site/src/pages/library/index.astro')
    for path, title in (('site/src/pages/history.astro', '历史'), ('site/src/pages/favorites.astro', '收藏'), ('site/src/pages/watch-later.astro', '稍后观看')):
        page = read(path)
        assert 'LibraryPage' in page and f'title="{title}"' in page


def test_stage1_space_copy_and_avatar_shortcuts_are_present():
    myspace = read('site/src/scripts/myspace.js')
    auth = read('site/src/components/AuthMenu.astro')
    about = read('site/src/pages/about.astro')
    assert '我的空间' not in myspace.split('space.innerHTML =', 1)[1].split(';', 1)[0]
    assert 'data-myspace-new' in myspace
    assert 'href="/watch-later/"' not in auth
    assert 'data-auth-signout' in auth
    assert '本设备' not in auth and '订阅' in about


def test_stage1_header_watch_later_flyout_is_queue_only():
    header = read('site/src/components/Header.astro')
    assert '<div class="lib-item" data-lib-kind="watchLater">' in header
    assert 'data-panel-tab=' not in header
    assert 'data-panel-footer' in header and "'/watch-later/'" in header


def test_stage1_auth_dialog_escapes_header_and_has_safe_viewport_bounds():
    auth = read('site/src/components/AuthMenu.astro')
    assert 'document.body.append(backdrop, dialog)' in auth
    assert 'max-height:calc(100dvh - 32px)' in auth
    assert 'overflow-y:auto' in auth
    assert 'position:fixed' in auth

