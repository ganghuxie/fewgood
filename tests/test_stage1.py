from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_stage1_header_has_stable_two_row_navigation_contract():
    header = read('site/src/components/Header.astro')
    layout = read('site/src/components/Layout.astro')
    assert 'data-header-mode-switch' in header
    assert '我的空间' in header and '探索世界' in header
    assert 'placeholder="搜索精选池"' in header
    assert 'href={link(\'/library/\')}' in header
    assert '更新于 {updated}' in header
    assert 'contain:layout' in layout or 'contain:layout' in header
    assert 'data-lib-kind="history"' in header
    assert '.lib-item[data-lib-kind="history"]' in header


def test_stage1_library_tabs_use_existing_storage_and_keep_legacy_routes():
    tabs = read('site/src/components/LibraryTabs.astro')
    assert 'KEYS[kind]' in tabs
    assert 'migrate(KEYS[kind]' in tabs
    assert '稍后再看是空的' in tabs
    assert '还没有收藏视频' in tabs
    assert '还没有观看历史' in tabs
    for path in ('site/src/pages/library/index.astro', 'site/src/pages/history.astro',
                 'site/src/pages/favorites.astro', 'site/src/pages/watch-later.astro'):
        assert 'LibraryTabs' in read(path)


def test_stage1_space_copy_and_avatar_shortcuts_are_present():
    myspace = read('site/src/scripts/myspace.js')
    auth = read('site/src/components/AuthMenu.astro')
    about = read('site/src/pages/about.astro')
    assert '我的空间' not in myspace.split('space.innerHTML =', 1)[1].split(';', 1)[0]
    assert 'data-myspace-new' in myspace
    assert '/library/?tab=watchLater' in auth
    assert '本设备' in auth and '订阅' in about

