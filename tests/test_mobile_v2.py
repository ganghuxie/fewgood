from pathlib import Path
import colorsys
import re


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def _style_sources_in_page_order():
    """Return component styles in the order needed to evaluate shared the shell."""
    sources = []
    for path in (
        'site/src/components/AuthMenu.astro',
        'site/src/components/Header.astro',
        'site/src/components/Layout.astro',
        'site/src/components/VideoPage.astro',
        'site/src/components/AudioPodcastLayout.astro',
    ):
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
    selector = re.sub(r':global\(([^)]*)\)', r'\1', selector).strip()
    if target == 'panel':
        return bool(re.search(r'\.lib-panel(?![\w-])', selector))
    if target == 'watch-later':
        if not re.search(r'\.lib-item(?![\w-])', selector):
            return False
        if ':not([data-lib-kind="watchLater"])' in selector:
            return False
        kinds = re.findall(r'\[data-lib-kind="([^"]+)"\]', selector)
        return not kinds or 'watchLater' in kinds
    if target == 'html':
        return selector in {':root', 'html'} or bool(re.fullmatch(r'html\[data-theme="[^"]+"\]', selector))
    if target == 'body':
        return selector == 'body' or selector.endswith(' body')
    if target == 'mode-switch-selected':
        return selector.endswith('.mode-switch button[aria-pressed="true"]')
    suffixes = {
        'site-header': '.site-header',
        'header-row': '.header-row',
        'search-form': '.search',
        'search-input': '.search input',
        'search-button': '.search button',
        'menu-toggle': '.menu-toggle',
        'logo': '.logo',
        'logo-mark': '.logo-mark',
        'watch-trigger': '.lib-trigger',
        'library-icon': '.library-icon',
        'auth-login': '.auth-login',
        'auth-login-icon': '.auth-login svg',
        'site-sidebar': '.site-sidebar',
        'auth-dialog': '.auth-dialog',
        'audio-preview': '.audio-preview',
        'sort-row': '.sort-row',
    }
    suffix = suffixes.get(target)
    return bool(suffix and selector.endswith(suffix))


def _specificity(selector):
    return (
        len(re.findall(r'#[\w-]+', selector)),
        len(re.findall(r'\.[\w-]+|\[[^]]+\]|:(?!:)[\w-]+', selector)),
        len(re.findall(r'(?<![.#:\w-])[a-z][\w-]*', selector)),
    )


def _theme_matches(selector, theme):
    themed = re.search(r'html\[data-theme="([^"]+)"\]', selector)
    return not themed or themed.group(1) == theme


def _computed_css(target, viewport, theme='light'):
    """A deliberately small cascade evaluator for the shared shell CSS."""
    winning = {}
    order = 0
    for source in _style_sources_in_page_order():
        for selector, declarations in _css_rules(source, viewport):
            if not _theme_matches(selector, theme) or not _matches_target(selector, target):
                order += 1
                continue
            specificity = _specificity(selector)
            for name, (value, important) in declarations.items():
                candidate = (important, specificity, order, value)
                if name not in winning or candidate[:3] >= winning[name][:3]:
                    winning[name] = candidate
            order += 1
    return {name: value for name, (*_, value) in winning.items()}


def _number(value, default=0.0):
    match = re.search(r'-?\d+(?:\.\d+)?', value or '')
    return float(match.group()) if match else default


def _horizontal_padding(value):
    values = [_number(part) for part in re.findall(r'-?\d+(?:\.\d+)?(?:px)?', value or '')]
    if not values:
        return 0.0
    if len(values) == 1:
        return 2 * values[0]
    if len(values) == 2:
        return 2 * values[1]
    if len(values) >= 4:
        return values[1] + values[3]
    return values[0] + values[-1]


def _box(left, right):
    return {'left': left, 'right': right, 'width': right - left}


def _header_hit_boxes(viewport, theme):
    """Resolve the mobile grid to on-screen boxes from the winning cascade."""
    row = _computed_css('header-row', viewport, theme)
    search = _computed_css('search-form', viewport, theme)
    search_input = _computed_css('search-input', viewport, theme)
    search_button = _computed_css('search-button', viewport, theme)
    menu = _computed_css('menu-toggle', viewport, theme)
    mark = _computed_css('logo-mark', viewport, theme)
    watch = _computed_css('watch-later', viewport, theme)
    trigger = _computed_css('watch-trigger', viewport, theme)
    icon = _computed_css('library-icon', viewport, theme)
    auth = _computed_css('auth-login', viewport, theme)
    auth_icon = _computed_css('auth-login-icon', viewport, theme)

    assert row['display'] == 'grid'
    assert row['grid-template-columns'] == 'auto auto minmax(72px,1fr) auto auto'
    assert row['grid-template-areas'] == '"menu logo search library auth" "mode mode mode mode mode"'

    padding = _horizontal_padding(row['padding'])
    gap = _number(row['gap'])
    menu_width = _number(menu['width'])
    logo_width = _number(mark['width'])
    watch_width = max(_number(watch['min-width']), _number(icon['width']) + _horizontal_padding(trigger['padding']))
    auth_width = (
        _horizontal_padding(auth['padding'])
        + _number(auth['gap'])
        + _number(auth_icon['width'])
        + 2 * _number(auth['border'])
        + 72  # worst-case visible 13px label: 登录/注册
    )
    content_width = viewport - padding
    search_track = content_width - menu_width - logo_width - watch_width - auth_width - 4 * gap
    assert search_track >= 72, (viewport, theme, search_track)

    cursor = padding / 2
    menu_box = _box(cursor, cursor + menu_width)
    cursor = menu_box['right'] + gap
    logo_box = _box(cursor, cursor + logo_width)
    cursor = logo_box['right'] + gap
    search_width = max(search_track, _number(search['min-width']))
    search_box = _box(cursor, cursor + search_width)
    button_width = _number(search_button['width'])
    button_box = _box(search_box['right'] - button_width, search_box['right'])
    input_box = _box(search_box['left'], button_box['left'])
    watch_start = cursor + search_track + gap
    watch_box = _box(watch_start, watch_start + watch_width)
    auth_box = _box(watch_box['right'] + gap, watch_box['right'] + gap + auth_width)
    return {
        'menu': menu_box,
        'logo': logo_box,
        'search': search_box,
        'search_input': input_box,
        'search_button': button_box,
        'watch_later': watch_box,
        'account': auth_box,
    }


def _rgb(hex_color):
    value = hex_color.strip().lstrip('#')
    assert re.fullmatch(r'[0-9a-fA-F]{6}', value), hex_color
    return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))


def _hsl(hex_color):
    hue, lightness, saturation = colorsys.rgb_to_hls(*_rgb(hex_color))
    return hue * 360, saturation, lightness


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
    assert '"menu logo search library auth" "mode mode mode mode mode"' in header
    assert '.site-header .mode-switch){grid-area:mode;display:flex' in header
    assert 'href={link(\'/watch-later/\')}' in header
    assert '.site-header .search input){height:34px' in header
    assert '.header-row{position:sticky!important' in layout
    assert '@media(max-width:767px){.header-row{position:static!important}' in layout
    assert '.site-header{position:static!important}' in layout


def test_mobile_header_hit_boxes_do_not_overlap_at_375_390_767_in_both_themes():
    """The search column may shrink, but the watch-later and account hit areas may not."""
    for viewport in (375, 390, 767):
        for theme in ('light', 'pale-green'):
            boxes = _header_hit_boxes(viewport, theme)
            assert boxes['menu']['right'] <= boxes['logo']['left'], (viewport, theme, boxes)
            assert boxes['logo']['right'] <= boxes['search']['left'], (viewport, theme, boxes)
            assert boxes['search_input']['right'] <= boxes['search_button']['left'], (viewport, theme, boxes)
            assert boxes['search']['right'] <= boxes['watch_later']['left'], (viewport, theme, boxes)
            assert boxes['search_button']['right'] <= boxes['watch_later']['left'], (viewport, theme, boxes)
            assert boxes['watch_later']['right'] <= boxes['account']['left'], (viewport, theme, boxes)
            assert boxes['account']['right'] <= viewport, (viewport, theme, boxes)
            search = _computed_css('search-form', viewport, theme)
            search_input = _computed_css('search-input', viewport, theme)
            search_button = _computed_css('search-button', viewport, theme)
            assert _number(search['min-width']) == 0, (viewport, theme, search)
            assert search_input['min-width'] == '0', (viewport, theme, search_input)
            assert search_button['flex'] == '0 0 34px', (viewport, theme, search_button)
            assert search_button['min-width'] == '34px', (viewport, theme, search_button)


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


def test_community_sort_row_has_real_direct_children_and_a_visible_gap_at_mobile_and_desktop():
    page = read('site/src/components/VideoPage.astro')
    match = re.search(r'<nav class="sort-row"[^>]*>(.*?)</nav>', page, flags=re.DOTALL)
    assert match, 'community page should render the real .sort-row nav'
    children = re.findall(r'<(a|i)\b[^>]*>.*?</\1>', match.group(1), flags=re.DOTALL)
    assert children == ['a', 'i', 'a']
    assert '<nav' not in match.group(1)
    for viewport in (375, 390, 767, 1280):
        sort_row = _computed_css('sort-row', viewport)
        assert sort_row['display'] in {'flex', 'grid'}, (viewport, sort_row)
        assert _number(sort_row['gap']) >= 16, (viewport, sort_row)


def test_pale_green_page_uses_visible_logo_family_green_while_light_stays_original():
    light_html = _computed_css('html', 375, 'light')
    assert light_html['background'] == '#fff'
    assert light_html['color'] == '#0f0f0f'
    for target in ('site-header', 'header-row'):
        assert _computed_css(target, 375, 'light')['background'] == '#fff'
    assert _computed_css('search-button', 375, 'light')['background'] == '#f8f8f8'
    assert _computed_css('mode-switch-selected', 375, 'light')['background'] == '#fff'
    assert _computed_css('audio-preview', 375, 'light')['background'] == '#fff'

    pale_html = _computed_css('html', 375, 'pale-green')
    page_background = pale_html['background']
    assert page_background.upper() not in {'#FFF', '#FFFFFF', '#F5FAF7'}
    assert pale_html['color'] == '#17221F'
    assert _computed_css('body', 375, 'pale-green')['background'] == page_background

    background_hue, background_saturation, background_lightness = _hsl(page_background)
    logo_hue, logo_saturation, logo_lightness = _hsl('#49C987')
    assert abs(background_hue - logo_hue) <= 6
    assert background_saturation >= 0.30
    assert 0.80 <= background_lightness <= 0.93
    assert logo_saturation > background_saturation and logo_lightness < background_lightness

    assert _computed_css('site-header', 375, 'pale-green')['background'] == '#CDEDDB'
    assert _computed_css('header-row', 375, 'pale-green')['background'] == '#CDEDDB'
    assert _computed_css('audio-preview', 375, 'pale-green')['background'] == page_background
    assert _computed_css('search-input', 375, 'pale-green')['background'] == '#EAF8F0'
    assert _computed_css('site-sidebar', 375, 'pale-green')['background'] == '#EAF8F0'
    assert _computed_css('auth-dialog', 375, 'pale-green')['background'] == '#EAF8F0'
    selected = _computed_css('mode-switch-selected', 375, 'pale-green')
    assert selected['background'] == '#49C987' and selected['color'] == '#17221F'


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


def test_library_flyout_is_positioned_below_the_measured_chipbar_so_it_cannot_capture_chip_clicks():
    header = read('site/src/components/Header.astro')
    assert ':global(.lib-panel){position:fixed;top:var(--lib-panel-top,112px);' in header
    assert "chipbar?.getBoundingClientRect().bottom" in header


def test_watch_later_control_expands_left_inside_its_own_bar():
    source = read('site/src/scripts/search-watch-later.js')
    assert 'right:8px!important;top:8px!important' in source
    assert 'width:92px!important' in source
    assert 'watch-later-label' in source
    assert 'background:rgb(15 15 15 / .82)!important' in source
    assert '::after' not in source
    assert 'data-tooltip-side' not in source
