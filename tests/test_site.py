import subprocess
from pathlib import Path


def test_pagination():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import {paginate, pageUrl, pageNumbers} from './site/src/lib/pagination.mjs';
const videos = Array.from({length: 121}, (_, i) => ({id: String(i),
  recommenders: i % 3, months: i, selected_at: i, last: i}));
for (const sort of ['people', 'newest']) {
  const pages = paginate(videos, sort);
  assert.deepEqual(pages.map(p => p.videos.length), [50, 50, 21]);
  assert.equal(new Set(pages.flatMap(p => p.videos.map(v => v.id))).size, 121);
}
assert.equal(paginate(videos, 'people')[0].videos[0].id, '119');
assert.equal(paginate(videos, 'newest')[0].videos[0].id, '120');
for (const count of [0, 1, 50]) {
  const pages = paginate(videos.slice(0, count), 'people');
  assert.equal(pages.length, 1);
  assert.equal(pages[0].videos.length, count);
}
assert.equal(pageUrl('people', 1), '/');
assert.equal(pageUrl('people', 2), '/page/2/');
assert.equal(pageUrl('newest', 1), '/newest/');
assert.equal(pageUrl('newest', 2), '/newest/page/2/');
assert.deepEqual(pageNumbers(5, 10), [1, null, 3, 4, 5, 6, 7, null, 10]);
assert.deepEqual(pageNumbers(1, 1), [1]);
'''], cwd=Path(__file__).resolve().parents[1], check=True)
