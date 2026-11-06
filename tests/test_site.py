import subprocess
from pathlib import Path


def test_pagination():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import {paginate, pageUrl, pageNumbers, videoUrl} from './site/src/lib/pagination.mjs';
const videos = Array.from({length: 121}, (_, i) => ({id: String(i),
  recommenders: i % 3, months: i, selected_at: i, last: i}));
for (const sort of ['people', 'newest']) {
  const pages = paginate(videos, 'community', sort);
  assert.deepEqual(pages.map(p => p.videos.length), [20, 20, 20, 20, 20, 20, 1]);
  assert.equal(new Set(pages.flatMap(p => p.videos.map(v => v.id))).size, 121);
}
assert.equal(paginate(videos, 'community', 'people')[0].videos[0].id, '119');
assert.equal(paginate(videos, 'community', 'newest')[0].videos[0].id, '120');
for (const count of [0, 1, 20]) {
  const pages = paginate(videos.slice(0, count), 'community');
  assert.equal(pages.length, 1);
  assert.equal(pages[0].videos.length, count);
}
assert.equal(pageUrl('trending', 1), '/');
assert.equal(pageUrl('trending', 2), '/page/2/');
assert.equal(pageUrl('ai', 1), '/ai/');
assert.equal(pageUrl('ai', 2), '/ai/page/2/');
assert.equal(pageUrl('community', 1), '/community/');
assert.equal(pageUrl('community', 2, '', 'newest'), '/community/newest/page/2/');
assert.equal(pageUrl('trending', 1, '/youtuber/'), '/youtuber/');
assert.equal(videoUrl('ai', 'abcdefghijk'), '/v/abcdefghijk/?from=ai');
assert.equal(videoUrl('community', 'abcdefghijk', '/youtuber/'), '/youtuber/v/abcdefghijk/?from=community');
assert.deepEqual(pageNumbers(5, 10), [1, null, 3, 4, 5, 6, 7, null, 10]);
assert.deepEqual(pageNumbers(1, 1), [1]);
'''], cwd=Path(__file__).resolve().parents[1], check=True)
