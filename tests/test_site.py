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
assert.equal(pageUrl('picks', 1), '/');
assert.equal(pageUrl('trending', 1), '/trending/');
assert.equal(pageUrl('trending', 2), '/trending/page/2/');
assert.equal(pageUrl('ai', 1), '/ai/');
assert.equal(pageUrl('ai', 2), '/ai/page/2/');
assert.equal(pageUrl('community', 1), '/community/');
assert.equal(pageUrl('community', 2, '', 'newest'), '/community/newest/page/2/');
assert.equal(pageUrl('trending', 1, '/youtuber/'), '/youtuber/trending/');
assert.equal(pageUrl('picks', 1, '/youtuber/'), '/youtuber/');
assert.equal(videoUrl('ai', 'abcdefghijk'), '/v/abcdefghijk/');
assert.equal(videoUrl('community', 'abcdefghijk', '/youtuber/'), '/youtuber/v/abcdefghijk/');
assert.deepEqual(pageNumbers(5, 10), [1, null, 3, 4, 5, 6, 7, null, 10]);
assert.deepEqual(pageNumbers(1, 1), [1]);
import {humanizeRecommendSpan} from './site/src/lib/format.mjs';
assert.equal(humanizeRecommendSpan(116), '9 年前');
assert.equal(humanizeRecommendSpan(11), '11 个月');

'''], cwd=Path(__file__).resolve().parents[1], check=True)


def test_myspace_card_does_not_repeat_channel_name():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';

const metas = html => [...html.matchAll(/<p class="video-meta">(.*?)<\\/p>/g)].map(match => match[1]);
const base = { id: 'abcdefghijk', title: 'A test video', channel: 'OpenAI', duration_seconds: 125 };

const regular = card({ ...base, view_count: 123456, published_at: new Date().toISOString() }, '/v/abcdefghijk/');
assert.equal((regular.match(/OpenAI/g) || []).length, 1);
assert.deepEqual(metas(regular), ['OpenAI', '12.3万 次观看 · 今天']);

const community = card({ ...base, recommenders: 5, months: 18, view_count: 123456, published_at: new Date().toISOString() }, '/v/abcdefghijk/');
assert.equal((community.match(/OpenAI/g) || []).length, 1);
assert.deepEqual(metas(community), ['OpenAI', '5 人推荐 · 1 年前']);

const sparse = card({ ...base }, '/v/abcdefghijk/');
assert.deepEqual(metas(sparse), ['OpenAI']);
'''], cwd=Path(__file__).resolve().parents[1], check=True)
