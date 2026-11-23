import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_has_install_identity_and_icons():
    manifest = json.loads((ROOT / 'site/public/site.webmanifest').read_text())
    assert manifest['id'] == '/'
    assert manifest['start_url'] == '/'
    assert manifest['scope'] == '/'
    assert manifest['display'] == 'standalone'
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
        'apple-mobile-web-app-status-bar-style', 'apple-mobile-web-app-title',
    ):
        assert f'name="{tag}"' in layout
    assert 'site.webmanifest' in layout
    assert "import '../scripts/pwa.js'" in layout
    assert 'safe-area-inset-top' in layout
    assert 'safe-area-inset-bottom' in layout


def test_install_prompt_covers_android_ios_dismissal_and_mobile_only_behavior():
    prompt = (ROOT / 'site/src/scripts/pwa.js').read_text()
    layout = (ROOT / 'site/src/components/Layout.astro').read_text()
    assert 'beforeinstallprompt' in prompt
    assert 'deferredPrompt.prompt()' in prompt
    assert '点底部分享 → 添加到主屏幕，像 App 一样打开' in layout
    assert 'localStorage.setItem(DISMISSED_KEY, \'1\')' in prompt
    assert "display-mode: standalone" in prompt
    assert 'navigator.standalone' in prompt
    assert 'max-width:700px' in layout
    assert 'fewgood-pwa-install-dismissed' in prompt


def test_install_prompt_handles_in_app_browsers_and_hidden_state():
    prompt = (ROOT / 'site/src/scripts/pwa.js').read_text()
    layout = (ROOT / 'site/src/components/Layout.astro').read_text()
    media_blocks = layout.split('@media(max-width:700px){')[1:]
    assert media_blocks
    assert any('.pwa-install[hidden]{display:none}' in block for block in media_blocks)
    assert layout.index('.pwa-install[hidden]{display:none}') > layout.index('.pwa-install{display:flex')
    assert 'data-pwa-mode="inapp"' in layout
    assert '.pwa-install[data-pwa-mode="inapp"] .pwa-install-action{display:none}' in layout
    assert '点右上角 … 用系统浏览器打开，即可添加到桌面' in layout
    assert 'MicroMessenger' in prompt
    assert 'isInApp' in prompt
    assert "pwaMode = 'inapp'" in prompt
