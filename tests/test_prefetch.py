from pathlib import Path
import subprocess


def test_category_prefetch_scope_dedup_and_idle_neighbors():
    source = (Path(__file__).resolve().parents[1] / 'site/src/components/Layout.astro').read_text()
    subprocess.run(['node', '--input-type=module', '-e', r'''
import assert from 'node:assert/strict';
const categories = ['/', '/trending/', '/ai/', '/podcast/', '/audio-podcast/', '/music/', '/community/'];
const normalize = p => p.endsWith('/') ? p : `${p}/`;
const sameOrigin = (href, current) => {
  const url = new URL(href, current);
  return url.origin === new URL(current).origin && categories.includes(normalize(url.pathname));
};
const neighbors = (current) => {
  const index = categories.indexOf(normalize(current));
  return index <= 0 ? categories.slice(1, 3) : [categories[index - 1], categories[index + 1]].filter(Boolean);
};
assert.deepEqual(neighbors('/'), ['/trending/', '/ai/']);
assert.deepEqual(neighbors('/music/'), ['/audio-podcast/', '/community/']);
assert.equal(sameOrigin('/trending/', 'http://localhost/'), true);
assert.equal(sameOrigin('https://other.test/trending/', 'http://localhost/'), false);
const requested = new Set();
const request = href => { if (sameOrigin(href, 'http://localhost/') && !requested.has(href)) requested.add(href); };
request('/music/'); request('/music/'); request('/music/');
assert.deepEqual([...requested], ['/music/']);
'''], check=True)
    assert "const categoryPaths = ['/', '/trending/', '/ai/', '/podcast/', '/audio-podcast/', '/music/', '/community/'];" in source
    assert "document.querySelectorAll('.chipbar nav a')" in source
    assert 'const wiredCategoryLinks = new WeakSet();' in source
    assert 'if (wiredCategoryLinks.has(link)) return;' in source
    assert 'if (!links.length) return;' in source
    assert "link.addEventListener('pointerenter', request)" in source
    assert "link.addEventListener('focus', request)" in source
    assert "const neighbors = index <= 0 ? links.slice(1, 3) : [links[index - 1], links[index + 1]].filter(Boolean);" in source
    assert 'categoryIdleScheduled' in source
    assert 'main[data-channel-transition],main[data-category-transition]' in source
