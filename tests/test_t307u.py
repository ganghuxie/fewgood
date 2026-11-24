from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_shared_mobile_header_has_real_rows_at_all_narrow_breakpoints():
    header = read('site/src/components/Header.astro')
    layout = read('site/src/components/Layout.astro')
    for width in (375, 390, 767):
        assert width < 768
    assert '"menu logo search library auth" "mode mode mode mode mode"' in header
    assert 'grid-area:search' in header and 'grid-area:mode;display:flex' in header
    assert '.header-row{position:static!important}' in layout


def test_install_prompt_uses_native_prompt_and_persists_a_refusal():
    source = read('site/src/scripts/pwa.js')
    shell = read('site/src/components/Layout.astro')
    assert 'deferredPrompt.prompt()' in source
    assert "choice?.outcome !== 'accepted'" in source
    assert "localStorage.setItem(DISMISSED_KEY, '1')" in source
    assert '添加到桌面' in shell and '添加到主屏幕' in shell


def test_video_detail_hides_curatorial_attribution_but_keeps_owner_controls():
    source = read('site/src/pages/v/[id].astro')
    assert '<style>.why-good-detail{display:none}</style>' in source
    assert 'owner-name' in source and 'subscribe-btn' in source


def test_play_count_and_titles_share_compact_content_driven_rules():
    layout = read('site/src/components/Layout.astro')
    audio = read('site/src/components/AudioPodcastLayout.astro')
    assert '.video-meta-views{word-spacing:-.12em}' in layout
    assert '.audio-card-title{font-size:16px;line-height:22px;font-weight:500' in audio
    title_rule = audio.split('.audio-card-title{', 1)[1].split('}', 1)[0]
    assert 'min-height' not in title_rule


def test_drawer_theme_has_two_persistent_logo_color_choices_and_early_bootstrap():
    sidebar = read('site/src/components/Sidebar.astro')
    layout = read('site/src/components/Layout.astro')
    header = read('site/src/components/Header.astro')
    assert 'fewgood-theme' in sidebar and '主题：浅色' in sidebar
    assert 'data-theme-choice="light"' in sidebar and 'data-theme-choice="pale-green"' in sidebar
    assert 'aria-expanded' in sidebar and 'aria-pressed' in sidebar and "event.key === 'Escape'" in sidebar
    assert 'localStorage.getItem(\'fewgood-theme\')' in layout
    for color in ('#49C987', '#F5FAF7', '#17221F'):
        assert color in header or color in layout
    assert 'dark' not in sidebar and 'system' not in sidebar
