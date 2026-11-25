import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_has_install_identity_and_icons():
    manifest = json.loads((ROOT / 'site/public/site.webmanifest').read_text())
    assert manifest['id'] == '/'
    assert manifest['start_url'] == '/'
    assert manifest['scope'] == '/'
    assert manifest['display'] == 'standalone'
    assert manifest['name'] == 'fewgood'
    assert manifest['short_name'] == 'fewgood'
    assert manifest['theme_color'] == '#49C987'
    assert manifest['background_color'] == '#F7F9F8'
    assert {icon['src'] for icon in manifest['icons']} == {'icon-192.png', 'icon-512.png', 'maskable-512.png'}
    assert next(icon for icon in manifest['icons'] if icon['src'] == 'maskable-512.png')['purpose'] == 'maskable'


def test_service_worker_is_lifecycle_only_and_does_not_cache_data_or_media():
    sw = (ROOT / 'site/public/sw.js').read_text()
    assert "addEventListener('install'" in sw
    assert "addEventListener('activate'" in sw
    assert "addEventListener('fetch'" in sw
    assert 'skipWaiting' in sw
    assert 'clients.claim' in sw
    assert 'respondWith' not in sw
    assert 'cache.addAll' not in sw
    assert 'caches.open' not in sw
    assert 'url.origin !== self.location.origin' in sw
    assert "event.request.mode === 'navigate'" in sw
    assert "url.pathname.endsWith('.json')" in sw


def test_layout_has_pwa_head_registration_and_safe_area_styles():
    layout = (ROOT / 'site/src/components/Layout.astro').read_text()
    assert 'width=device-width, initial-scale=1, viewport-fit=cover' in layout
    for tag in (
        'theme-color', 'mobile-web-app-capable', 'apple-mobile-web-app-capable',
        'application-name', 'apple-mobile-web-app-status-bar-style', 'apple-mobile-web-app-title',
    ):
        assert f'name="{tag}"' in layout
    assert '<link rel="apple-touch-icon"' in layout
    assert 'site.webmanifest' in layout
    assert "import '../scripts/pwa.js'" in layout
    assert 'safe-area-inset-top' in layout
    assert 'safe-area-inset-bottom' in layout
    assert 'application-name" content="fewgood"' in layout
    assert 'apple-mobile-web-app-title" content="fewgood"' in layout


def test_pwa_cold_start_splash_is_standalone_only_session_once_and_previewable():
    layout = (ROOT / 'site/src/components/Layout.astro').read_text()
    prompt = (ROOT / 'site/src/scripts/pwa.js').read_text()
    head = layout.split('<body>', 1)[0]
    for phrase in ('data-pwa-splash', 'logo-mark.svg', 'fewgood</strong>', 'a few good videos', '告别无尽刷屏，只看好内容', '#F7F9F8', 'z-index:1000'):
        assert phrase in layout
    assert 'data-pwa-splash-first' in head
    assert 'html[data-pwa-splash-first] .pwa-splash[hidden]{display:grid!important}' in head
    assert head.index('data-pwa-splash-first') < layout.index('<body>')
    for phrase in ('fewgood-splash-shown', 'sessionStorage', 'display-mode: standalone', 'navigator.standalone', 'preview_splash', 'URLSearchParams', 'prefers-reduced-motion', 'setTimeout(() => hideSplash(false), 1100)', 'splash.addEventListener'):
        assert phrase in prompt
    assert "if (!splash || (!isStandalone() && !isSplashPreview)" in prompt
    assert 'if (reducedMotion) hideSplash(true);' in prompt
    assert 'else setTimeout(() => hideSplash(false), 1100);' in prompt
    assert 'if (!isSplashPreview) markSplashShown();' in prompt


def test_install_prompt_covers_native_fallback_and_persistent_dismissal():
    prompt = (ROOT / 'site/src/scripts/pwa.js').read_text()
    layout = (ROOT / 'site/src/components/Layout.astro').read_text()
    assert 'beforeinstallprompt' in prompt
    assert 'deferredPrompt.prompt()' in prompt
    assert 'show(manualMode())' in prompt
    assert '添加到桌面：点底部分享 → 添加到主屏幕，像 App 一样打开' in layout
    assert 'localStorage.setItem(DISMISSED_KEY, \'1\')' in prompt
    assert "display-mode: standalone" in prompt
    assert 'navigator.standalone' in prompt
    assert 'max-width:700px' in layout
    assert 'fewgood-pwa-install-dismissed' in prompt


def test_install_prompt_handles_in_app_browsers_and_hidden_state():
    prompt = (ROOT / 'site/src/scripts/pwa.js').read_text()
    layout = (ROOT / 'site/src/components/Layout.astro').read_text()
    mobile_styles = layout.index('@media(max-width:700px){')
    assert layout.index('.pwa-install{display:flex') < mobile_styles
    assert '.pwa-install[hidden]{display:none}' in layout[:mobile_styles]
    media_blocks = layout.split('@media(max-width:700px){')[1:]
    assert media_blocks
    assert any('.pwa-install[hidden]{display:none}' in block for block in media_blocks)
    assert layout.index('.pwa-install[hidden]{display:none}') > layout.index('.pwa-install{display:flex')
    assert 'data-pwa-mode="inapp"' in layout
    assert '.pwa-install[data-pwa-mode="inapp"] .pwa-install-action{display:none}' not in layout
    assert '把 fewgood 添加到桌面：点右上角 … 用系统浏览器打开' in layout
    assert 'MicroMessenger' in prompt
    assert 'isInApp' in prompt
    assert "isInApp ? 'inapp'" in prompt


def test_android_manual_install_fallback_and_browser_detection_regressions():
    prompt = (ROOT / 'site/src/scripts/pwa.js').read_text()
    layout = (ROOT / 'site/src/components/Layout.astro').read_text()
    assert '把 fewgood 添加到桌面：点浏览器菜单 → 添加到桌面' in layout
    assert 'data-pwa-mode="manual"' in layout
    assert '.pwa-install[data-pwa-mode="manual"] .pwa-install-action{display:none}' not in layout
    assert '.pwa-install[data-pwa-mode="manual"] .pwa-install-manual{display:block}' in layout
    assert 'data-pwa-install-action type="button">添加到桌面</button>' in layout
    assert "isIOS ? 'ios' : 'manual'" in prompt
    assert 'isNarrow' not in prompt
    assert 'manualTimer' not in prompt
    assert 'delete promptBar.dataset.pwaMode' in prompt
    assert "addEventListener('appinstalled'" in prompt
    assert 'localStorage.setItem(DISMISSED_KEY, \'1\')' in prompt
    assert 'MicroMessenger|QQ\\/' in prompt
    in_app = re.search(r'const isInApp = (/(?:\\.|[^/])+/i)\.test', prompt).group(1)
    for ua in ('MicroMessenger', 'QQ/'): assert re.search(in_app[1:in_app.rfind('/')], ua, re.I)
    for ua in ('MQQBrowser', 'HuaweiBrowser', 'MiuiBrowser', 'HeyTapBrowser', 'OPPOBrowser', 'VivoBrowser', 'HonorBrowser', 'Quark', 'UCBrowser'):
        assert not re.search(in_app[1:in_app.rfind('/')], ua, re.I)


def test_install_prompt_keeps_action_visible_and_expands_honest_guide():
    prompt = (ROOT / 'site/src/scripts/pwa.js').read_text()
    layout = (ROOT / 'site/src/components/Layout.astro').read_text()
    sidebar = (ROOT / 'site/src/components/Sidebar.astro').read_text()
    assert 'data-pwa-install-guide' in layout
    assert 'guideText' in prompt and 'expandGuide: true' in prompt
    assert "if (!deferredPrompt) { show(manualMode(), { force: true, expandGuide: true }); return; }" in prompt
    for mode in ('ios', 'inapp', 'manual'):
        assert f'.pwa-install[data-pwa-mode="{mode}"] .pwa-install-action{{display:none}}' not in layout
    assert 'data-pwa-reopen' in sidebar
    assert "new Event('fewgood:pwa-reopen')" in sidebar
    assert "document.querySelector('.menu-toggle[data-sidebar-close]')?.click()" in sidebar
    assert "document.addEventListener('fewgood:pwa-reopen'" in prompt
    assert "if (deferredPrompt) show(undefined, { force: true, expandGuide: false });" in prompt
    assert "else show(manualMode(), { force: true, expandGuide: true });" in prompt
    assert "promptBar?.scrollIntoView?.({ block: 'nearest' });" in prompt
