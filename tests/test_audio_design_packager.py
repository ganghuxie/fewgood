"""Preview remapping and built IA regression checks (no network)."""
import importlib.util
from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audio_packager', ROOT / 'scripts/package-audio-podcast-preview-site.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def test_preview_rewriter_retains_navigation_and_inline_player():
    base = packager.BASE
    original = f'''<html><head></head><body><header class="site-header"><div class="chipbar">音频播客</div></header>
<a href="{base}/audio-podcast/show/ep-123/">episode</a>
<script type="module" src="{base}/_astro/Header.astro_astro_type_script.123.js"></script>
<script src="https://static.cloudflareinsights.com/beacon.min.js"></script>
<script>audio.setAttribute('src', officialUrl)</script></body></html>'''
    result = packager.rewrite_html(original)
    assert f'{base}/audio-podcast-preview/show/ep-123/' in result
    assert f'{base}/audio-podcast/' not in result
    assert 'noindex,nofollow' in result
    assert 'Header.astro_astro_type_script' not in result
    assert 'cloudflareinsights' not in result
    assert 'audio.setAttribute' in result
    assert '.chipbar,' not in result
    assert 'class="chipbar"' in result


def test_built_catalog_ia_and_all_episode_pages():
    dist = ROOT / 'site/dist/audio-podcast'
    if not dist.exists():
        pytest.skip('requires local build')
    import json
    catalog = json.loads((ROOT / 'site/src/data/audio_podcast.json').read_text())
    count = 0
    for show in catalog['shows']:
        directory = dist / show['slug']
        for listing in [directory / 'index.html', *directory.glob('page/*/index.html')]:
            markup = listing.read_text()
            assert '<audio' not in markup
            assert 'audio-episode-description' not in markup
        for detail in directory.glob('*/index.html'):
            if detail.parent.name == 'page':
                continue
            count += 1
            markup = detail.read_text()
            assert len(re.findall(r'<audio\b', markup)) == 1
            assert 'preload="none"' in markup
            assert not re.search(r'<audio[^>]*\ssrc=', markup)
            assert '发布者单集说明' in markup
            assert 'audio-back' in markup and '页</a>' in markup
    assert count == sum(len(s['episodes']) for s in catalog['shows'])
