from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_video_cards_use_compact_three_group_contract_and_single_action():
    page = read('site/src/components/VideoPage.astro')
    card = read('site/src/lib/myspace-card.mjs')
    library = read('site/src/components/LibraryTabs.astro')
    for source in (page, card, library):
        assert 'data-watch-later' in source
        assert 'video-meta' in source
    assert '12px' in read('site/src/components/Layout.astro') or '12px' in page
    assert '次观看' not in page
    assert '来自.*频道' in page
    assert 'topicSubscribeTitle(v.topic_name)' not in page


def test_myspace_card_filters_boilerplate_and_uses_publication_time():
    script = """
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';
const base = { id: 'abc', title: '原始标题', channel: '频道名', duration_seconds: 125, published_at: '2025-01-01T00:00:00Z' };
const html = card({ ...base, why_good: '来自频道「频道名」的近期长视频' }, '/v/abc/');
assert.ok(html.includes('频道名'));
assert.ok(html.includes('data-published-at'));
assert.ok(html.includes('duration">2:05'));
assert.ok(!html.includes('近期长视频'));
assert.ok(html.includes('data-watch-later'));
"""
    subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, check=True)


def test_audio_header_uses_real_generated_timestamp_without_count_heading():
    index = read('site/src/components/AudioPodcastIndex.astro')
    layout = read('site/src/components/AudioPodcastLayout.astro')
    assert 'updatedAt={data.generated_at || \'\'}' in index
    assert 'updatedAt={updatedAt}' in layout
    assert '<h1>音频播客</h1>' not in index
    assert 'confirmedCount} 个已确认节目' not in index


def test_community_badge_has_valid_real_count_fallback():
    page = read('site/src/components/VideoPage.astro')
    assert "HN ${Number(v.recommenders)} 人推荐" in page
    assert "'社区精选'" in page
    assert 'undefined 人推荐' not in page
    assert 'NaN 人推荐' not in page


def test_relative_published_time_uses_shanghai_calendar_days_and_honest_fallbacks():
    script = """
import assert from 'node:assert/strict';
import { relativePublishedTime } from './site/src/lib/format.mjs';
const now = Date.parse('2026-11-24T01:00:00Z'); // 09:00 in Asia/Shanghai
assert.equal(relativePublishedTime('2026-11-24T00:00:00Z', now), '今天');
assert.equal(relativePublishedTime('2026-11-23T15:30:00Z', now), '昨天'); // Shanghai 23:30 yesterday
assert.equal(relativePublishedTime('2026-11-21T00:00:00Z', now), '3天前');
assert.equal(relativePublishedTime('2026-09-15T00:00:00Z', now), '2个月前');
assert.equal(relativePublishedTime('2025-11-24T00:00:00Z', now), '1年前');
assert.equal(relativePublishedTime('2009-11-24T00:00:00Z', now), '17年前');
for (const value of ['', 'not-a-date', '2026-11-25T00:00:00Z']) assert.equal(relativePublishedTime(value, now), '');
"""
    subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, check=True)


def test_list_cards_keep_duration_on_thumbnail_and_use_expanding_watch_later_control():
    files = [
        'site/src/components/VideoPage.astro',
        'site/src/lib/myspace-card.mjs',
        'site/src/components/LibraryTabs.astro',
        'site/src/components/LibraryPage.astro',
        'site/src/pages/following.astro',
        'site/src/pages/search.astro',
    ]
    for path in files:
        source = read(path)
        assert 'data-watch-later' in source
    assert '稍后观看</button>' not in '\n'.join(read(path) for path in files)
    action = read('site/src/scripts/search-watch-later.js')
    for token in ('width:28px', 'height:28px', 'right:8px', 'top:8px', 'watch-later-label'):
        assert token in action
    assert '::after' not in action
    assert "'已添加'" in action
    assert 'setTimeout' not in action
    assert 'duration">' in read('site/src/components/VideoPage.astro')
    assert 'relativePublishedTime(video.published_at)' in read('site/src/components/LibraryPage.astro')
    assert 'relativePublishedTime(item.video.published_at)' in read('site/src/pages/following.astro')


def test_watch_later_card_controls_are_thumbnail_scoped_hover_controls():
    action = read('site/src/scripts/search-watch-later.js')
    assert '.thumbnail .watch-later-action,.sr-thumbnail .watch-later-action' in action
    assert '@media(hover:hover) and (min-width:376px)' in action
    assert '.thumbnail .watch-later-action,.sr-thumbnail .watch-later-action{opacity:0;pointer-events:none}' in action
    assert '.video-card:hover .thumbnail .watch-later-action' in action
    assert '.thumbnail .watch-later-action:focus' in action
    assert '@media(max-width:375px)' in action
    assert '@media(max-width:375px),(hover:none)' in action
    assert 'opacity:1!important' not in action
    assert 'new MutationObserver' in action
    assert "document.addEventListener('youtuber:library-change'" in action


def test_detail_watch_later_remains_a_text_pill_with_detail_copy():
    detail = read('site/src/pages/v/[id].astro')
    assert 'data-library-toggle="watchLater"' in detail
    assert '◷ 稍后再看</button>' in detail
    assert "'◷ 已加入稍后再看'" in detail
    assert 'watch-later-action' not in detail
    assert 'width:26px' not in detail


def test_card_title_and_meta_rules_and_community_sort_row_are_explicit():
    layout = read('site/src/components/Layout.astro')
    page = read('site/src/components/VideoPage.astro')
    search = read('site/src/pages/search.astro')
    assert '.video-title{min-height:44px}' in layout
    assert '-webkit-line-clamp:2' in layout
    assert '.video-meta-channel{max-width:11em' in layout
    assert '.video-meta-time{flex-shrink:0' in layout
    assert '.sr-video-title' in search and 'min-height:44px' in search and '-webkit-line-clamp:2' in search
    assert '.sort-row{justify-content:flex-end;align-items:center;gap:16px' in page
    assert '.sort-row i{width:1px;height:12px' in page
    assert '.sort-row a[aria-current="page"]{color:#0f0f0f;font-weight:700}' in page
    assert '.sort-row a{color:#606060}' in page


def test_search_unpacks_publication_time_and_library_keeps_watch_later_navigation_copy():
    search = read('site/src/pages/search.astro')
    tabs = read('site/src/components/LibraryTabs.astro')
    assert '([i, t, h, d, z, u, s, e, b, published_at])' in search
    assert 'relativePublishedTime(v.published_at)' in search
    assert 'data-published-at="' in search
    assert 'data-tab="watchLater">稍后观看' in tabs
    assert '稍后观看是空的' in tabs
