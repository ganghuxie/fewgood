import re
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


def test_music_preserves_curated_order_in_helpers_and_page_paths():
    subprocess.run(['node', '--input-type=module', '-e', r'''
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { paginate, pageUrl, sortVideos } from './site/src/lib/pagination.mjs';

const videos = [
  { id: 'npr-1', channel: 'NPR', view_count: 1000 },
  { id: 'kexp', channel: 'KEXP', view_count: 100 },
  { id: 'bbc', channel: 'BBC', view_count: 200 },
  { id: 'colors', channel: 'COLORS', view_count: 300 },
  { id: 'npr-2', channel: 'NPR', view_count: 100000 },
  { id: 'npr-3', channel: 'NPR', view_count: 200000 },
  { id: 'npr-4', channel: 'NPR', view_count: 300000 },
];
const original = structuredClone(videos);
assert.deepEqual(sortVideos(videos, 'music'), original);
assert.notEqual(sortVideos(videos, 'music'), videos);
assert.deepEqual(paginate(videos, 'music')[0].videos, original);
assert.equal(new Set(paginate(videos, 'music')[0].videos.slice(0, 4).map(v => v.channel)).size, 4);
const byViews = [...videos].sort((a, b) => b.view_count - a.view_count);
assert.deepEqual(byViews.slice(0, 4).map(v => v.channel), ['NPR', 'NPR', 'NPR', 'NPR']);
assert.deepEqual(sortVideos(videos, 'trending'), byViews);
assert.deepEqual(sortVideos(videos, 'picks'), original);
assert.deepEqual(videos, original);

const music = JSON.parse(readFileSync('./site/src/data/music.json', 'utf8'));
const firstIds = items => items.slice(0, 8).map(v => v.id);
const feedIds = firstIds(music.videos);
assert.equal(feedIds.length, 8, 'music feed should have at least 8 videos');
// Compare against the live feed order, not a daily-refresh snapshot of IDs.
assert.deepEqual(firstIds(paginate(music.videos, 'music')[0].videos), feedIds);
const viewSortedIds = firstIds(sortVideos(music.videos, 'trending'));
assert.notDeepEqual(feedIds, viewSortedIds);

// Execute the actual Astro path builder with local feeds and its real helpers.
const source = readFileSync('./site/src/pages/[...path].astro', 'utf8');
assert.ok(source.includes("import music from '../data/music.json'"));
assert.ok(source.includes('paginate(feeds[section].videos, section, sort)'));
assert.ok(source.includes('allVideos: sortVideos(feeds[section].videos, section, sort)'));
assert.ok(source.includes('<VideoPage {...pageProps} />'));
const builder = source.split('export function getStaticPaths() {')[1].split('const { redirectTo, ...pageProps }')[0];
assert.ok(builder, 'Astro must expose getStaticPaths');
const empty = { videos: [] };
const paths = new Function('picks', 'trending', 'ai', 'podcast', 'music', 'community',
  'paginate', 'pageUrl', 'sortVideos', 'return (function() {' + builder + ')();')(
    empty, empty, empty, empty, music, empty, paginate, pageUrl, sortVideos);
const page = paths.find(p => p.params.path === 'music');
assert.ok(page, 'getStaticPaths must build /music/');
assert.equal(page.props.section, 'music');
assert.deepEqual(firstIds(page.props.videos), feedIds);
assert.deepEqual(firstIds(page.props.allVideos), feedIds);
assert.deepEqual(page.props.feed, music);
'''], cwd=Path(__file__).resolve().parents[1], check=True)


def test_myspace_card_does_not_repeat_channel_name():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';

const metas = html => [...html.matchAll(/<p class="video-meta">(.*?)<\\/p>/g)].map(match => match[1]);
const base = { id: 'abcdefghijk', title: 'A test video', channel: 'OpenAI', duration_seconds: 125 };

const regular = card({ ...base, view_count: 123456, published_at: new Date().toISOString() }, '/v/abcdefghijk/');
assert.equal((regular.match(/OpenAI/g) || []).length, 2);
assert.ok(regular.includes('video-meta-channel">OpenAI'));
assert.ok(regular.includes('video-meta-time">今天'));

const community = card({ ...base, recommenders: 5, months: 18, span_days: 180, view_count: 123456, published_at: new Date().toISOString() }, '/v/abcdefghijk/');
assert.equal((community.match(/OpenAI/g) || []).length, 2);
assert.ok(community.includes('video-meta-channel">OpenAI'));

const noSpan = card({ ...base, recommenders: 5, months: 116 }, '/v/abcdefghijk/');
assert.ok(noSpan.includes('video-meta-channel">OpenAI'));

const sparse = card({ ...base }, '/v/abcdefghijk/');
assert.ok(sparse.includes('video-meta-channel">OpenAI'));
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
assert.ok(!html.includes('<p class="zh-title">A test video</p>'));
assert.ok(!html.includes('<p class="zh-blurb">中文简介</p>'));

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
    for banned in (
        'Reddit', '可能', '计划', '大概', 'sync.js', 'end-to-end', '端到端',
        '今日精选', '服务器不收集任何痕迹', '安全加密同步', '为什么有 fewgood',
        '内容从哪里来', '数据与隐私', '联系我们', '第三方播放器', '稍后观看',
    ):
        assert banned not in about
    assert '前往精选' in about
    assert 'fewgood/issues' in about
    assert '通过加密连接同步到云端数据库' in about
    assert 'mailto:' in about
    assert 'localStorage' in about
    assert 'a few good videos · 告别无尽刷屏，只看好内容' in about
    assert '不必在海量视频里迷失，从今天精选的几条开始看起。' in about
    assert '为什么做 fewgood？' in about
    assert '我们给你的三个承诺' in about
    assert '少而精，拒绝信息过载' in about
    assert '高信噪比的硬核来源' in about
    assert '纯净、克制、诚实' in about
    assert '关于视频广告的诚实说明：视频通过 YouTube 官方播放器嵌入展示' in about
    assert '隐私与数据承诺' in about
    assert '你的个人数据属于你，我们不做用户画像追踪：' in about
    assert '站内点击播放后会通过 YouTube 官方标准播放器加载，播放体验与 Cookie 受 YouTube 服务及其政策影响。' in about
    assert '稍后看 100%' in about
    assert '不会同步到我们的数据库' in about
    assert 'PostHog 会尊重「请勿追踪」设置' in about
    assert '版权与内容归属' in about
    assert '开启今天的发现' in about
    assert '交流与反馈' in about
    assert 'fewgood 是一个持续生长的独立产品' in about


def test_video_page_heading_keeps_last_updated_outside_h1():
    source = (Path(__file__).resolve().parents[1] / 'site/src/components/VideoPage.astro').read_text()
    assert '<h1>{label}</h1>' not in source
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
    assert 'humanizeRecommendSpan(video.span_days)' not in video_page
    assert 'humanizeRecommendSpan(video.span_days)' in detail
    assert 'humanizeRecommendSpan(video.span_days)' not in myspace
    for source in (video_page, detail, myspace):
        assert 'humanizeRecommendSpan(v.months)' not in source
        assert 'humanizeRecommendSpan(video.months)' not in source


def test_library_panel_footer_is_watch_later_only():
    header = (Path(__file__).resolve().parents[1] / 'site/src/components/Header.astro').read_text()
    footer_line = next(line for line in header.splitlines() if 'data-panel-footer' in line)
    assert "href={link('/watch-later/')}" in footer_line
    assert 'href="#"' not in footer_line
    assert "paths = { watchLater: '/watch-later/' }" in header
    assert 'footer.href = `${base}${paths[kind]}`' in header
    assert "document.querySelector('.library-cluster')" in header
    nav = re.search(r'<nav class="libraries"[^>]*>(.*?)</nav>', header, re.S)
    assert nav
    nav_body = nav.group(1)
    assert 'lib-panel' not in nav_body
    assert '查看全部' not in nav_body
    assert nav_body.count('data-lib-kind=') == 1


def test_myspace_card_shows_community_classic_badge_only_when_flagged():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';

const base = { id: 'abcdefghijk', title: 'A test video', channel: 'OpenAI', duration_seconds: 125 };
const classic = card({ ...base, community_classic: true }, '/v/abcdefghijk/');
    assert.ok(classic.includes('<span class="community-classic-badge">社区精选</span>'));
    assert.ok(classic.indexOf('社区精选') < classic.indexOf('class="duration"'));
    const hn = card({ ...base, community_classic: true, recommenders: 198 }, '/v/abcdefghijk/');
    assert.ok(hn.includes('HN 198 人推荐'));
    assert.ok(!card(base, '/v/abcdefghijk/').includes('社区精选'));
'''], cwd=Path(__file__).resolve().parents[1], check=True)


def test_layout_keeps_global_styles_and_classic_badge():
    source = (Path(__file__).resolve().parents[1] / 'site/src/components/Layout.astro').read_text()
    assert ':root{' in source
    assert '.site-header' in source
    assert '.community-classic-badge' in source
    assert '.video-grid' in source


def test_compact_counts_have_no_space_before_units():
    root = Path(__file__).resolve().parents[1]
    sources = (
        'site/src/components/VideoPage.astro',
        'site/src/pages/v/[id].astro',
        'site/src/lib/myspace-card.mjs',
        'site/src/pages/channel/[id].astro',
        'site/src/pages/following.astro',
        'site/src/pages/search.astro',
    )
    for name in sources:
        source = (root / name).read_text()
        assert ' 次观看' not in source, name
        assert ' 位订阅者' not in source, name

    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';

const base = { id: 'abcdefghijk', title: 'A test video', channel: 'OpenAI', duration_seconds: 125 };
const rendered = card({ ...base, view_count: 123456 }, '/v/abcdefghijk/');
assert.ok(rendered.includes('video-meta-channel">OpenAI'));
assert.ok(!rendered.includes('次观看'));
'''], cwd=root, check=True)


def test_layout_og_dimensions_only_for_default_image():
    source = (Path(__file__).resolve().parents[1] / 'site/src/components/Layout.astro').read_text()
    assert 'const shareImage = ogImage || defaultOgImage;' in source
    assert source.count('property="og:image:width"') == 1
    assert source.count('property="og:image:height"') == 1
    assert '{!ogImage && <meta property="og:image:width" content="1200"/>}' in source
    assert '{!ogImage && <meta property="og:image:height" content="630"/>}' in source


def test_thumbnail_helpers_choose_available_sizes():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';
import { thumbCandidates, thumbFallbackAttr, thumbFor, thumbUrl } from './site/src/lib/format.mjs';

for (const id of ['hQVTIJBZook', 'aAb7hSCtvGw', 'jVkLVRt6c1U']) {
  assert.equal(thumbFor({ id }), thumbUrl(id, 'hqdefault'));
  assert.ok(!thumbFor({ id }).includes('maxresdefault'));
}
assert.equal(
  thumbFor({ id: 'aAb7hSCtvGw', thumb: 'https://i.ytimg.com/vi/aAb7hSCtvGw/mqdefault.jpg' }),
  'https://i.ytimg.com/vi/aAb7hSCtvGw/mqdefault.jpg',
);
assert.equal(
  thumbFor({ id: 'aAb7hSCtvGw', thumbnail: 'https://i.ytimg.com/vi/aAb7hSCtvGw/maxresdefault.jpg' }),
  thumbUrl('aAb7hSCtvGw', 'hqdefault'),
);
assert.equal(
  thumbFor({ id: 'aAb7hSCtvGw', thumb: 'https://i.ytimg.com/vi/aAb7hSCtvGw/maxresdefault.jpg', thumb_verified: true }),
  thumbUrl('aAb7hSCtvGw', 'hqdefault'),
);
assert.deepEqual(thumbCandidates('hQVTIJBZook'), [
  thumbUrl('hQVTIJBZook', 'hqdefault'),
  thumbUrl('hQVTIJBZook', 'mqdefault'),
]);
assert.equal(thumbFallbackAttr('hQVTIJBZook'), 'data-thumb-id="hQVTIJBZook"');
const html = card({ id: 'hQVTIJBZook', title: 'JavaScript: The Good Parts', channel: 'Google TechTalks', duration_seconds: 3600 }, '/v/hQVTIJBZook/');
assert.ok(html.includes('hqdefault.jpg'));
assert.ok(html.includes('data-thumb-id="hQVTIJBZook"'));
assert.ok(!html.includes('maxresdefault'));
'''], cwd=Path(__file__).resolve().parents[1], check=True)


def test_thumbnail_fallback_is_wired_into_every_card_renderer():
    root = Path(__file__).resolve().parents[1]
    renderers = (
        'site/src/components/VideoPage.astro',
        'site/src/lib/myspace-card.mjs',
        'site/src/components/LibraryPage.astro',
        'site/src/components/Header.astro',
        'site/src/pages/search.astro',
        'site/src/pages/following.astro',
        'site/src/pages/channel/[id].astro',
        'site/src/pages/v/[id].astro',
    )
    for name in renderers:
        source = (root / name).read_text()
        assert 'data-thumb-id' in source or 'thumbFallbackAttr' in source, name
        assert 'maxresdefault' not in source, name

    layout = (root / 'site/src/components/Layout.astro').read_text()
    detector = (root / 'site/src/scripts/thumbnails.js').read_text()
    assert "import '../scripts/thumbnails.js'" in layout
    assert 'PLACEHOLDER_MAX_WIDTH = 120' in detector
    assert "image.naturalWidth > PLACEHOLDER_MAX_WIDTH" in detector
    assert "thumbUrl(id, 'hqdefault')" in detector or 'thumbCandidates(id)' in detector
    assert "thumbUrl(id, 'mqdefault')" in detector or 'thumbCandidates(id)' in detector


def test_card_text_layout_clamps_and_prevents_grid_overflow():
    root = Path(__file__).resolve().parents[1]
    layout = (root / 'site/src/components/Layout.astro').read_text()
    page = (root / 'site/src/components/VideoPage.astro').read_text()
    myspace = (root / 'site/src/lib/myspace-card.mjs').read_text()
    assert 'grid-template-columns:36px minmax(0,1fr)' in layout
    assert 'grid-row:span 2' not in layout
    assert '.video-copy{min-width:0' in layout
    assert '-webkit-line-clamp:1' in layout
    assert 'class="video-copy"' in page
    assert 'class="video-copy"' in myspace
    assert ':root{' in layout


def test_detail_share_modal_uses_canonical_fewgood_url_and_local_qr():
    root = Path(__file__).resolve().parents[1]
    detail = (root / 'site/src/pages/v/[id].astro').read_text()
    modal = (root / 'site/src/scripts/share-modal.js').read_text()
    share_lib = (root / 'site/src/lib/share.mjs').read_text()
    assert '生成分享链接需要登录' not in detail
    assert '不用验证邮箱' not in detail
    assert '请登录' not in detail
    assert "import { initShareModal } from '../../scripts/share-modal.js';" in detail
    assert 'initShareModal();' in detail
    assert 'data-share' in detail and 'data-share-id={video.id}' in detail
    assert 'navigator.share' in modal
    assert 'navigator.clipboard' in modal
    assert 'writeText' in modal
    assert "from 'uqr'" in modal and 'renderSVG' in modal
    assert '微信扫码分享' in modal
    assert '已复制' in modal
    assert 'shareUrlFor' in modal and "linkField.value = currentUrl" in modal
    assert "target = '_blank'" in modal and "rel = 'noopener noreferrer'" in modal
    assert "typeof navigator.share === 'function'" in modal and "'系统分享'" in modal
    for source in (detail, modal, share_lib):
        assert '发帖' not in source
        assert '嵌入' not in source
        assert '开始时间' not in source
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { shareUrlFor, shareIntents } from './site/src/lib/share.mjs';
assert.equal(shareUrlFor('abc123'), 'https://fewgood.io/v/abc123/');
const canonical = encodeURIComponent('https://fewgood.io/v/abc123/');
const intents = shareIntents({ id: 'abc123', title: '一条视频' });
assert.deepEqual(intents.map(item => item.label), ['X', 'Facebook', 'WhatsApp', 'Telegram', '微博', '邮件']);
for (const intent of intents) {
  assert.ok(intent.href.includes(canonical), intent.href);
  assert.ok(!intent.href.includes('youtube.com'), intent.href);
}
assert.ok(intents.find(item => item.key === 'email').href.startsWith('mailto:?subject='));
assert.ok(!JSON.stringify(intents).includes('localhost'));
'''], cwd=root, check=True)


def test_detail_click_to_play_uses_standard_embed_only_after_user_action():
    detail = (Path(__file__).resolve().parents[1] / 'site/src/pages/v/[id].astro').read_text()
    initial_html = detail.split('</Layout>', 1)[0]
    assert '<iframe' not in initial_html
    assert 'youtube-nocookie.com/embed' not in detail
    assert 'data-player-load' in detail
    assert '>播放</button>' in detail
    assert "const STANDARD_EMBED_HOST = 'www.youtube.com';" in detail
    assert 'const embedSrc = (videoId, { start, autoplay } = {})' in detail
    assert "params.set('autoplay', '1')" in detail
    assert "document.querySelectorAll('[data-player-load]')" in detail
    assert "loadEmbed(detail, button.dataset.videoId, { autoplay: true })" in detail
    assert 'https://www.youtube.com/watch?v=${video.id}' in detail
    assert '在 YouTube 打开' in detail
    assert 'localStorage' not in detail
    for removed in ('data-player-host-toggle', 'player-host-choice', '隐私增强', '普通播放器', '确认你不是聊天机器人'):
        assert removed not in detail


def test_detail_seek_loads_or_controls_the_standard_embed_without_host_switching():
    detail = (Path(__file__).resolve().parents[1] / 'site/src/pages/v/[id].astro').read_text()
    assert 'const loadEmbed = (detail, videoId, { start, autoplay } = {})' in detail
    assert 'frame.src = embedSrc(videoId, { start, autoplay });' in detail
    assert "else loadEmbed(detail, button.dataset.videoId, { start: seconds, autoplay: true });" in detail
    assert 'if (player && player.seekTo)' in detail
    assert 'youtube-nocookie.com' not in detail


def test_topic_subscribe_copy_and_chip_is_on_thumbnail():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { TOPIC_SUBSCRIBED_LABEL, paintTopicChip, topicSubscribeLabel, topicSubscribeTitle } from './site/src/lib/topic-labels.mjs';
assert.equal(topicSubscribeLabel('经典演讲'), '+订阅栏目');
assert.equal(topicSubscribeTitle('经典演讲'), '订阅「经典演讲」栏目，它会作为一栏出现在我的空间');
assert.equal(TOPIC_SUBSCRIBED_LABEL, '✓ 已订阅');
const button = { classList: { toggle() {} }, dataset: {}, textContent: '', title: '', attrs: {}, setAttribute(name, value) { this.attrs[name] = value; } };
paintTopicChip(button, true, '经典演讲');
assert.equal(button.textContent, '✓ 已订阅');
assert.equal(button.title, '订阅「经典演讲」栏目，它会作为一栏出现在我的空间');
assert.equal(button.attrs['aria-pressed'], 'true');
paintTopicChip(button, false, '经典演讲');
assert.equal(button.textContent, '+订阅栏目');
assert.equal(button.attrs['aria-pressed'], 'false');
'''], cwd=root, check=True)

    page = (root / 'site/src/components/VideoPage.astro').read_text()
    layout = (root / 'site/src/components/Layout.astro').read_text()
    myspace = (root / 'site/src/scripts/myspace.js').read_text()
    affinity = (root / 'site/src/scripts/affinity.js').read_text()
    for source in (page, myspace):
        assert '订阅这个主题' not in source
        assert '已订阅主题' not in source
        assert '加到我的空间' not in source
        assert '已在我的空间' not in source
    assert 'data-watch-later' in page
    assert 'topicSubscribeTitle(v.topic_name)' not in page
    assert "chip.className = 'topic-chip'" not in page
    assert 'data-watch-later' in myspace or 'data-watch-later' in page
    assert '<h2>管理订阅栏目</h2>' in myspace
    assert '添加订阅栏目…' in myspace
    assert 'aria-label="管理订阅栏目" title="管理订阅栏目"' in myspace
    assert '要不要订阅「${name}」栏目？' in affinity

    assert 'watch-later-action' in page
    assert 'data-topic-subscribe' not in page
    assert '+ 订阅「' not in page and '✓ 已订阅，在我的空间' not in page


def test_search_orders_videos_before_channels_and_caps_expandable_channels():
    source = (Path(__file__).resolve().parents[1] / 'site/src/pages/search.astro').read_text()
    assert source.index('data-video-section') < source.index('data-channel-section')
    assert 'items.slice(0, 3)' in source
    assert 'items.length <= 3 || showAll' in source
    assert '更多频道' in source
    assert '更多频道' in source.split('data-channel-more', 1)[1].split('</button>', 1)[0]
    assert 'moreButton.onclick = () => renderChannels(channelMatches, true);' in source
    assert '显示更多' not in source
