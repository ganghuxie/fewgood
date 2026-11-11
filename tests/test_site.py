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
assert.equal(humanizeRecommendSpan(6144), '跨 17 年');
assert.equal(humanizeRecommendSpan(180), '跨 6 个月');
assert.equal(humanizeRecommendSpan(), '');

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

const community = card({ ...base, recommenders: 5, months: 18, span_days: 180, view_count: 123456, published_at: new Date().toISOString() }, '/v/abcdefghijk/');
assert.equal((community.match(/OpenAI/g) || []).length, 1);
assert.deepEqual(metas(community), ['OpenAI', '5 人推荐 · 跨 6 个月']);

const noSpan = card({ ...base, recommenders: 5, months: 116 }, '/v/abcdefghijk/');
assert.deepEqual(metas(noSpan), ['OpenAI', '5 人推荐']);

const sparse = card({ ...base }, '/v/abcdefghijk/');
assert.deepEqual(metas(sparse), ['OpenAI']);
'''], cwd=Path(__file__).resolve().parents[1], check=True)


def test_myspace_card_uses_zh_title_when_present():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';

const base = { id: 'abcdefghijk', title: 'A test video', channel: 'OpenAI', duration_seconds: 125 };
const html = card({ ...base, view_count: 1, published_at: new Date().toISOString() }, '/v/abcdefghijk/', {
  title_zh: '中文标题',
  blurb_zh: '中文简介',
});
assert.ok(html.includes('<h2 class="video-title">中文标题</h2>'));
assert.ok(html.includes('<p class="zh-title">A test video</p>'));
assert.ok(html.includes('<p class="zh-blurb">中文简介</p>'));

const plain = card(base, '/v/abcdefghijk/');
assert.ok(plain.includes('<h2 class="video-title">A test video</h2>'));
assert.ok(!plain.includes('zh-title'));
'''], cwd=Path(__file__).resolve().parents[1], check=True)


def test_about_page_copy_lists_sources_and_avoids_uncertain_language():
    about = (Path(__file__).resolve().parents[1] / 'site/src/pages/about.astro').read_text()
    assert 'YouTube' in about
    assert 'YouTube Data API' in about
    assert 'Hacker News' in about
    assert 'hello@fewgood.io' in about
    for banned in ('可能', '计划', '大概', 'sync.js', 'localStorage'):
        assert banned not in about


def test_video_page_heading_keeps_last_updated_outside_h1():
    source = (Path(__file__).resolve().parents[1] / 'site/src/components/VideoPage.astro').read_text()
    assert '<h1>{label}</h1>' in source
    assert '<h1>{label}{feed' not in source


def test_picks_labels_use_jingxuan_and_related_heading_is_other_jingxuan():
    root = Path(__file__).resolve().parents[1]
    brand = (root / 'site/src/lib/brand.mjs').read_text()
    catalog = (root / 'site/scripts/build-catalog.mjs').read_text()
    detail = (root / 'site/src/pages/v/[id].astro').read_text()
    assert "picks: '精选'" in brand
    assert "picks: '精选'" in catalog
    assert "'其他精选'" in detail
    for source in (brand, catalog, detail):
        assert '今日精选' not in source


def test_detail_community_comments_heading_is_shequ_guandian():
    detail = (Path(__file__).resolve().parents[1] / 'site/src/pages/v/[id].astro').read_text()
    assert '<h2>社区观点</h2>' in detail
    assert '精选评论' not in detail
    assert '其他精选' in detail


def test_recommendation_age_uses_span_days_everywhere():
    root = Path(__file__).resolve().parents[1]
    video_page = (root / 'site/src/components/VideoPage.astro').read_text()
    detail = (root / 'site/src/pages/v/[id].astro').read_text()
    myspace = (root / 'site/src/lib/myspace-card.mjs').read_text()
    assert 'humanizeRecommendSpan(video.span_days)' in video_page
    assert 'humanizeRecommendSpan(video.span_days)' in detail
    assert 'humanizeRecommendSpan(video.span_days)' in myspace
    for source in (video_page, detail, myspace):
        assert 'humanizeRecommendSpan(v.months)' not in source
        assert 'humanizeRecommendSpan(video.months)' not in source


def test_library_panel_footer_is_tab_driven_not_static_history_duplicate():
    header = (Path(__file__).resolve().parents[1] / 'site/src/components/Header.astro').read_text()
    footer_line = next(line for line in header.splitlines() if 'data-panel-footer' in line)
    assert '/history/' not in footer_line
    assert 'href="#"' in footer_line
    assert "paths = { history: '/history/', favorites: '/favorites/', watchLater: '/watch-later/' }" in header
    assert 'footer.href = `${base}${paths[kind]}`' in header


def test_myspace_card_shows_community_classic_badge_only_when_flagged():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';

const base = { id: 'abcdefghijk', title: 'A test video', channel: 'OpenAI', duration_seconds: 125 };
const classic = card({ ...base, community_classic: true }, '/v/abcdefghijk/');
assert.ok(classic.includes('<span class="community-classic-badge">社区经典</span>'));
assert.ok(classic.indexOf('社区经典') < classic.indexOf('class="duration"'));
assert.ok(!card(base, '/v/abcdefghijk/').includes('社区经典'));
'''], cwd=Path(__file__).resolve().parents[1], check=True)


def test_layout_keeps_global_styles_and_classic_badge():
    source = (Path(__file__).resolve().parents[1] / 'site/src/components/Layout.astro').read_text()
    assert ':root{' in source
    assert '.site-header' in source
    assert '.community-classic-badge' in source
    assert '.video-grid' in source
