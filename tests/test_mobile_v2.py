from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def _style_sources_in_page_order():
    """Return Header then Layout styles, matching their rendered page order."""
    sources = []
    for path in ('site/src/components/Header.astro', 'site/src/components/Layout.astro'):
        sources.extend(re.findall(r'<style[^>]*>(.*?)</style>', read(path), flags=re.DOTALL))
    return sources


def _media_matches(condition, viewport):
    max_widths = re.findall(r'max-width\s*:\s*(\d+)px', condition)
    min_widths = re.findall(r'min-width\s*:\s*(\d+)px', condition)
    return (not max_widths or viewport <= min(map(int, max_widths))) and (
        not min_widths or viewport >= max(map(int, min_widths))
    )


def _css_rules(css, viewport):
    """Yield (selector, declarations) in CSS source order for this viewport."""
    cursor = 0
    while cursor < len(css):
        brace = css.find('{', cursor)
        if brace < 0:
            return
        head = css[cursor:brace].strip()
        depth, end = 1, brace + 1
        while end < len(css) and depth:
            depth += (css[end] == '{') - (css[end] == '}')
            end += 1
        body = css[brace + 1:end - 1]
        cursor = end
        if head.startswith('@media'):
            if _media_matches(head, viewport):
                yield from _css_rules(body, viewport)
            continue
        if head.startswith('@'):
            continue
        declarations = {}
        for name, value in re.findall(r'([\w-]+)\s*:\s*([^;{}]+)', body):
            value = value.strip()
            important = value.endswith('!important')
            declarations[name] = (value.removesuffix('!important').strip(), important)
        for selector in head.split(','):
            yield selector.strip(), declarations


def _matches_target(selector, target):
    selector = selector.replace(':global(', '')
    if target == 'panel':
        return bool(re.search(r'\.lib-panel(?![\w-])', selector))
    if not re.search(r'\.lib-item(?![\w-])', selector):
        return False
    if ':not([data-lib-kind="watchLater"])' in selector:
        return False
    kinds = re.findall(r'\[data-lib-kind="([^"]+)"\]', selector)
    return not kinds or 'watchLater' in kinds


def _specificity(selector):
    return (
        len(re.findall(r'#[\w-]+', selector)),
        len(re.findall(r'\.[\w-]+|\[[^]]+\]|:(?!:)[\w-]+', selector)),
        len(re.findall(r'(?<![.#:\w-])[a-z][\w-]*', selector)),
    )


def _computed_css(target, viewport):
    """A deliberately small cascade evaluator for Header/Layout source CSS."""
    winning = {}
    order = 0
    for source in _style_sources_in_page_order():
        for selector, declarations in _css_rules(source, viewport):
            if not _matches_target(selector, target):
                order += 1
                continue
            specificity = _specificity(selector)
            for name, (value, important) in declarations.items():
                candidate = (important, specificity, order, value)
                if name not in winning or candidate[:3] >= winning[name][:3]:
                    winning[name] = candidate
            order += 1
    return {name: value for name, (*_, value) in winning.items()}


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


def test_drawer_keeps_library_links_without_account_actions():
    source = read('site/src/components/Sidebar.astro')
    for href in ('/favorites/', '/history/', '/following/'):
        assert f"link('{href}')" in source
    for removed in ('/about/', '/about/#feedback', 'data-sidebar-auth', '退出登录'):
        assert removed not in source
    assert 'width:80vw' in source


def test_mobile_header_has_one_four_item_sticky_row_and_nonsticky_controls():
    header = read('site/src/components/Header.astro')
    layout = read('site/src/components/Layout.astro')
    row, after_row = header.split('</div>', 1)
    assert 'chipbar' not in row
    assert 'grid-template-areas:"menu logo library auth"' in header
    assert '.site-header .mode-switch){display:none}' in header
    assert 'href={link(\'/watch-later/\')}' in header
    assert '.site-header .search input){height:36px}' in header
    assert '.header-row{position:sticky!important' in layout
    assert '.site-header{position:static!important}' in layout


def test_mobile_watch_later_wins_the_actual_css_cascade_at_375_and_767():
    """Guard the desktop hide rules against a later mobile-cascade regression."""
    header = read('site/src/components/Header.astro')
    for viewport in (375, 767):
        watch_later = _computed_css('watch-later', viewport)
        assert watch_later['display'] in {'block', 'flex', 'inline', 'inline-block', 'inline-flex', 'grid', 'inline-grid'}
        assert int(re.search(r'\d+', watch_later['min-width']).group()) > 0
        assert _computed_css('panel', viewport)['display'] == 'none'
    assert re.search(
        r'<div class="lib-item" data-lib-kind="watchLater"><a[^>]+href=\{link\(\'/watch-later/\'\)\}',
        header,
    )


def test_header_watch_later_trigger_is_icon_only_at_desktop_and_mobile_breakpoints():
    header = read('site/src/components/Header.astro')
    trigger = re.search(
        r"<a class=\"lib-trigger\"[^>]*href=\{link\('/watch-later/'\)\}[^>]*>(.*?)</a>",
        header,
        flags=re.DOTALL,
    )
    assert trigger, 'watch-later trigger should retain its /watch-later/ href'
    open_tag, body = trigger.group(0).split('>', 1)[0], trigger.group(1)
    assert 'aria-label="稍后观看"' in open_tag
    assert 'title="稍后观看"' in open_tag
    assert 'data-library-count="watchLater"' in body
    assert '<svg class="library-icon"' in body
    assert '<span' not in body
    assert not re.sub(r'<[^>]+>', '', body).strip(), 'trigger must not render visible caption text'
    assert not re.search(r'\.lib-trigger[^{}]*::(?:before|after)', header)
    for viewport in (375, 767, 1280):
        assert _computed_css('watch-later', viewport)['display'] in {
            'block', 'flex', 'inline', 'inline-block', 'inline-flex', 'grid', 'inline-grid'
        }


def test_desktop_library_panel_wins_as_a_viewport_right_aligned_fixed_panel():
    for viewport in (768, 1280):
        panel = _computed_css('panel', viewport)
        assert panel['position'] == 'fixed'
        assert panel['width'] == '400px'
        assert panel['right'] == '0'
        assert panel.get('left') in (None, 'auto')
        assert panel['max-width'] == 'min(400px,calc(100vw - 16px))'
        panel_width = min(400, viewport - 16)
        left = viewport - panel_width
        assert panel_width == 400
        assert left >= 0


def test_watch_later_control_expands_left_inside_its_own_bar():
    source = read('site/src/scripts/search-watch-later.js')
    assert 'right:8px!important;top:8px!important' in source
    assert 'width:92px!important' in source
    assert 'watch-later-label' in source
    assert 'background:rgb(15 15 15 / .82)!important' in source
    assert '::after' not in source
    assert 'data-tooltip-side' not in source
