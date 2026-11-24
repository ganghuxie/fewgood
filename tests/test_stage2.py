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


def test_myspace_card_filters_boilerplate_and_keeps_duration():
    script = """
import assert from 'node:assert/strict';
import { card } from './site/src/lib/myspace-card.mjs';
const base = { id: 'abc', title: '原始标题', channel: '频道名', duration_seconds: 125 };
const html = card({ ...base, why_good: '来自频道「频道名」的近期长视频' }, '/v/abc/');
assert.ok(html.includes('频道名 · 2:05'));
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
