from pathlib import Path
import json
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_splash_is_prepainted_only_for_cold_standalone_or_preview_and_respects_reduced_motion():
    layout = read('site/src/components/Layout.astro')
    prompt = read('site/src/scripts/pwa.js')
    head = layout.split('<body>', 1)[0]

    assert 'data-pwa-splash-first' in head
    assert 'html[data-pwa-splash-first] .pwa-splash[hidden]{display:grid!important}' in head
    assert "if(preview||(standalone&&!seen))document.documentElement.dataset.pwaSplashFirst='1'" in head
    assert "sessionStorage.getItem('fewgood-splash-shown')" in head
    assert head.index('data-pwa-splash-first') < layout.index('<body>')

    assert 'if (!isSplashPreview) markSplashShown();' in prompt
    assert 'clearSplashFirstPaint();' in prompt
    assert 'if (reducedMotion) hideSplash(true);' in prompt
    assert 'else setTimeout(() => hideSplash(false), 1100);' in prompt
    assert 'splash.addEventListener' in prompt


def test_library_flyout_is_measured_below_chipbar_and_chipbar_cancels_hover_open():
    header = read('site/src/components/Header.astro')

    assert ':global(.lib-panel){position:fixed;top:var(--lib-panel-top,112px);' in header
    assert 'top:104px' not in header
    assert "panel.style.setProperty('--lib-panel-top'" in header
    assert "chipbar?.getBoundingClientRect().bottom" in header
    assert 'data-panel-footer' in header and "href={link('/watch-later/')}" in header

    manifest = json.loads(read('site/public/site.webmanifest'))
    assert manifest['start_url'] == '/'
    assert manifest['scope'] == '/'
    service_worker = read('site/public/sw.js')
    assert 'respondWith' not in service_worker
    assert 'location.href' not in service_worker and 'location.replace' not in service_worker


def test_watch_later_badge_and_rendered_queue_share_renderable_items_without_wiping_storage():
    library = read('site/src/scripts/library.js')
    page = read('site/src/components/LibraryPage.astro')
    tabs = read('site/src/components/LibraryTabs.astro')
    source = library.split('const hasRenderableId', 1)[1].split('export function unseenWatchLaterCount', 1)[0]

    assert 'return get(KEYS.watchLater).filter(hasRenderableId);' in source
    assert 'localStorage' not in source
    assert 'localStorage.removeItem' not in library
    assert 'return watchLaterItems().filter(isWatchLaterUnseen).length;' in library
    assert "kind === 'watchLater' ? watchLaterItems() : libraryList(key)" in page
    assert "kind === 'watchLater' ? watchLaterItems() : list(KEYS[kind])" in tabs


def test_auth_paints_real_avatar_without_destroying_badge_and_keeps_dialog_bindings_on_dialog():
    auth = read('site/src/components/AuthMenu.astro')
    script = re.search(r'<script>(.*?)</script>', auth, flags=re.DOTALL).group(1)
    after_append = script.split('document.body.append(backdrop, dialog);', 1)[1]

    assert 'avatarVisual.replaceChildren' in script
    assert 'avatar.textContent' not in script
    assert 'user_metadata?.avatar_url' in script and 'user_metadata?.picture' in script
    assert 'identity_data?.avatar_url' in script and 'identity_data?.picture' in script
    assert "addEventListener('error'" in script and 'fallback()' in script
    assert 'data-auth-avatar-visual' in auth
    assert '<b data-library-count="watchLater" hidden></b>' in auth

    assert "passwordToggle.addEventListener('click'" in after_append
    assert "dialog.querySelector('[data-auth-forgot]')" in after_append
    assert 'dialog.querySelectorAll(\'[data-auth-oauth]\')' in after_append
    assert "root.querySelector('[data-auth-forgot]')" not in after_append
    assert "root.querySelectorAll('[data-auth-oauth]')" not in after_append


def test_login_password_toggle_and_form_autocomplete_semantics():
    auth = read('site/src/components/AuthMenu.astro')
    script = re.search(r'<script>(.*?)</script>', auth, flags=re.DOTALL).group(1)
    email = re.search(r'<input id="auth-email"[^>]*>', auth)
    password = re.search(r'<input id="auth-password"[^>]*>', auth)
    toggle = re.search(r'<button class="auth-password-toggle"[^>]*>', auth)

    assert email and 'type="email"' in email.group(0) and 'autocomplete="username"' in email.group(0)
    assert password and 'type="password"' in password.group(0) and 'autocomplete="current-password"' in password.group(0)
    assert toggle and 'type="button"' in toggle.group(0)
    assert 'aria-pressed="false"' in toggle.group(0) and 'aria-label="显示密码"' in toggle.group(0)
    assert "passwordInput.type = visible ? 'text' : 'password'" in script
    assert "passwordToggle.setAttribute('aria-pressed', String(visible))" in script
    assert 'passwordInput.value' not in script
    assert 'event.preventDefault()' in script


def test_card_meta_builder_orders_author_views_time_and_never_uses_recommendations_as_views():
    script = r"""
import assert from 'node:assert/strict';
import { videoMetaHtml } from './site/src/lib/format.mjs';

const html = videoMetaHtml({ channel: 'No Priors & Co', views: 5541, relative: '3天前' });
assert.match(html, /No Priors &amp; Co/);
assert.match(html, /5,541 次播放/);
assert.ok(html.indexOf('video-meta-channel') < html.indexOf('video-meta-views'));
assert.ok(html.indexOf('video-meta-views') < html.indexOf('video-meta-time'));

const noViews = videoMetaHtml({ channel: '作者', views: 0, relative: '昨天' });
assert.ok(noViews.includes('作者'));
assert.ok(!noViews.includes('次播放'));

const noVotes = videoMetaHtml({ channel: '作者', views: undefined, recommenders: 435546, relative: '今天' });
assert.ok(!noVotes.includes('435546'));
assert.ok(!noVotes.includes('次播放'));
"""
    subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, check=True)

    layout = read('site/src/components/Layout.astro')
    shared_rule = layout.split('.video-meta,.sr-video-meta{', 1)[1].split('}', 1)[0]
    assert 'white-space:nowrap' in shared_rule
    assert '.video-meta-channel{flex:0 1 auto;max-width:11em;min-width:3em' in layout
    assert '.video-meta-views{flex:none;white-space:nowrap;word-spacing:-.12em}' in layout
    assert '.video-meta-time{flex:none;white-space:nowrap}' in layout
    for theme_rule in re.findall(r'html\[data-theme="pale-green"\][^{}]*\{[^}]*\}', layout):
        if '.video-meta' in theme_rule.split('{', 1)[0]:
            declarations = theme_rule.split('{', 1)[1]
            for property_name in ('display:', 'flex:', 'white-space:', 'word-spacing:', 'overflow:'):
                assert property_name not in declarations

    for path in (
        'site/src/components/VideoPage.astro',
        'site/src/pages/search.astro',
        'site/src/components/LibraryPage.astro',
        'site/src/components/LibraryTabs.astro',
        'site/src/lib/myspace-card.mjs',
        'site/src/pages/following.astro',
        'site/src/pages/channel/[id].astro',
    ):
        assert 'videoMetaHtml' in read(path), path
    assert 'videoMetaHtml({ channel: v.channel, views: v.view_count' in read('site/src/components/VideoPage.astro')
    assert 'views: catalogViews.get(normalizeVideoId(v.i))' in read('site/src/pages/search.astro')


def test_search_focus_is_clean_rounded_and_narrow_placeholder_is_short():
    layout = read('site/src/components/Layout.astro')
    header = read('site/src/components/Header.astro')

    assert 'appearance:none;-webkit-appearance:none;outline:none' in layout
    assert '.search input::-webkit-search-decoration' in layout
    assert '.search input::-webkit-search-cancel-button' in layout
    assert '.search:focus-within{outline:2px solid #49C987;outline-offset:2px;border-radius:22px}' in layout
    assert ':global(.site-header .search){grid-area:search;grid-column:auto;min-width:0' in header
    assert "compactSearch.matches ? '搜索' : '搜索精选池'" in header


def test_updated_timestamp_is_not_rendered_in_the_chipbar():
    header = read('site/src/components/Header.astro')
    assert 'chipbar-status' not in header
    assert '更新于' not in header
    assert 'data-updated-at={updated || undefined}' in header
    assert "toLocaleTimeString('zh-CN'" in header


def test_mode_switch_is_prominent_and_stays_in_the_single_header_row():
    header = read('site/src/components/Header.astro')
    layout = read('site/src/components/Layout.astro')
    myspace = read('site/src/scripts/myspace.js')
    mode_rule = header.split('.mode-switch button{', 1)[1].split('}', 1)[0]
    chip_rule = layout.split('.chipbar a,.chipbar button{', 1)[1].split('}', 1)[0]

    assert 'height:36px' in mode_rule and 'font:600 15px' in mode_rule
    assert 'height:32px' in chip_rule and 'font:500 14px' in chip_rule
    assert 'insertBefore(shell, chipbar)' not in myspace
    assert "header?.classList.add('alpha-video-header')" in myspace


def test_first_visit_install_prompt_is_visible_without_bip_and_uses_honest_fallbacks():
    prompt = read('site/src/scripts/pwa.js')
    layout = read('site/src/components/Layout.astro')

    assert 'if (!isStandalone() && !dismissed()) {' in prompt
    assert prompt.index('show(manualMode());') < prompt.index("addEventListener('beforeinstallprompt'")
    assert "isInApp ? 'inapp' : isIOS ? 'ios' : 'manual'" in prompt
    assert 'isNarrow' not in prompt and 'manualTimer' not in prompt
    assert '.pwa-install[data-pwa-mode="manual"] .pwa-install-action{display:none}' not in layout
    assert 'data-pwa-install-action type="button">添加到桌面</button>' in layout
    assert 'deferredPrompt.prompt()' in prompt
    assert "localStorage.setItem(DISMISSED_KEY, '1')" in prompt
    assert 'if (!deferredPrompt) { show(manualMode()); return; }' in prompt
    for phrase in ('点底部分享 → 添加到主屏幕，像 App 一样打开', '点浏览器菜单 → 添加到桌面，像 App 一样打开', '点右上角 … 用系统浏览器打开，即可添加到桌面'):
        assert phrase in layout
