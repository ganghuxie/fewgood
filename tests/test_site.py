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


def test_myspace_card_does_not_repeat_channel_name():
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';

const metas = html => [...html.matchAll(/<p class="video-meta">(.*?)<\\/p>/g)].map(match => match[1]);
const base = { id: 'abcdefghijk', title: 'A test video', channel: 'OpenAI', duration_seconds: 125 };

const regular = card({ ...base, view_count: 123456, published_at: new Date().toISOString() }, '/v/abcdefghijk/');
assert.equal((regular.match(/OpenAI/g) || []).length, 1);
assert.deepEqual(metas(regular), ['OpenAI', '12.3万次观看 · 今天']);

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
    for banned in ('Reddit', '可能', '计划', '大概', 'sync.js', 'end-to-end', '端到端', '今日精选', '服务器不收集任何痕迹'):
        assert banned not in about
    assert '前往精选' in about
    assert 'fewgood/issues' in about
    assert '通过加密连接同步' in about
    assert 'mailto:' in about
    assert 'localStorage' in about
    assert 'a few good videos · 告别无尽刷屏，只看好内容' in about
    assert '从今天精选的几条开始看起' in about
    assert '纯净、克制、诚实' in about
    assert '关于视频广告的诚实说明' in about


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
    assert "href={link('/history/')}" in footer_line
    assert 'href="#"' not in footer_line
    assert "paths = { history: '/history/', favorites: '/favorites/', watchLater: '/watch-later/' }" in header
    assert 'footer.href = `${base}${paths[kind]}`' in header
    assert "document.querySelector('.library-cluster')" in header
    nav = re.search(r'<nav class="libraries"[^>]*>(.*?)</nav>', header, re.S)
    assert nav
    nav_body = nav.group(1)
    assert 'lib-panel' not in nav_body
    assert '查看全部' not in nav_body
    assert nav_body.count('data-lib-kind=') == 3


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
const large = card({ ...base, view_count: 123456 }, '/v/abcdefghijk/');
assert.ok(large.includes('12.3万次观看'));
assert.ok(!large.includes('12.3万 次观看'));
const twentyThousand = card({ ...base, view_count: 20000 }, '/v/abcdefghijk/');
assert.ok(twentyThousand.includes('2万次观看'));
assert.ok(!twentyThousand.includes('2万 次观看'));
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
  'https://i.ytimg.com/vi/aAb7hSCtvGw/maxresdefault.jpg',
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
    assert 'topicSubscribeLabel(v.topic_name)' in page
    assert 'topicSubscribeTitle(v.topic_name)' in page
    assert "chip.className = 'topic-chip'" in page and 'article.append(chip)' in page
    assert 'paintTopicChip(button, active, button.dataset.topicName)' in myspace
    assert '<h2>管理订阅栏目</h2>' in myspace
    assert '添加订阅栏目…' in myspace
    assert 'aria-label="管理订阅栏目" title="管理订阅栏目"' in myspace
    assert '要不要订阅「${name}」栏目？' in affinity

    chip_rule = re.search(r'\.topic-chip\{([^}]*)\}', layout)
    assert chip_rule and 'position:absolute' in chip_rule.group(1)
    assert chip_rule and 'top:8px' in chip_rule.group(1)
    assert chip_rule and 'right:8px' in chip_rule.group(1)
    assert chip_rule and 'background:#0f0f0fcc' in chip_rule.group(1)
    assert chip_rule and 'border-radius:14px' in chip_rule.group(1)
    assert chip_rule and 'opacity:0' in chip_rule.group(1)
    assert chip_rule and 'pointer-events:none' in chip_rule.group(1)
    assert '.video-card:hover .topic-chip,.video-card:focus-within .topic-chip{opacity:1;pointer-events:auto}' in layout
    assert '.topic-chip.is-subscribed{background:#065fd4}' in layout
    assert '@media(hover:none){.topic-chip{opacity:1;pointer-events:auto}}' in layout
    template = next(line for line in page.splitlines() if 'data-topic-subscribe={v.topic_id}' in line)
    assert template.index('</div></a>') < template.index('class="topic-chip"')
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
