"""Layout checks for the white-page audio index and its responsive card grids."""

import re
from dataclasses import dataclass
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / 'site/src/components/AudioPodcastIndex.astro'
LAYOUT_PATH = ROOT / 'site/src/components/AudioPodcastLayout.astro'


@dataclass(frozen=True)
class CssRule:
    media: tuple[str, ...]
    selector: str
    declarations: dict[str, str]


def _read(path: Path) -> str:
    return path.read_text(encoding='utf8')


def _style_text(astro_source: str) -> str:
    styles = re.findall(r'<style\b[^>]*>(.*?)</style>', astro_source, re.S)
    return re.sub(r'/\*.*?\*/', '', '\n'.join(styles), flags=re.S)


def _matching_brace(css: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(css)):
        if css[index] == '{':
            depth += 1
        elif css[index] == '}':
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError('unbalanced CSS braces')


def _parse_css(css: str, media: tuple[str, ...] = ()) -> list[CssRule]:
    rules = []
    cursor = 0
    while True:
        opening = css.find('{', cursor)
        if opening < 0:
            break
        prelude = css[cursor:opening].strip()
        closing = _matching_brace(css, opening)
        body = css[opening + 1:closing]
        if prelude.startswith('@media'):
            rules.extend(_parse_css(body, media + (prelude,)))
        elif prelude.startswith('@'):
            rules.extend(_parse_css(body, media))
        else:
            declarations = {}
            for declaration in body.split(';'):
                if ':' not in declaration:
                    continue
                prop, value = declaration.split(':', 1)
                declarations[prop.strip().lower()] = value.strip()
            for selector in prelude.split(','):
                rules.append(CssRule(media, selector.strip(), declarations))
        cursor = closing + 1
    return rules


def _media_applies(media: tuple[str, ...], width: int) -> bool:
    for condition in media:
        for bound, pixels in re.findall(r'\((min|max)-width\s*:\s*(\d+)px\)', condition):
            if bound == 'min' and width < int(pixels):
                return False
            if bound == 'max' and width > int(pixels):
                return False
    return True


def _resolved(rules: list[CssRule], selector: str, prop: str, width: int) -> str | None:
    value = None
    for rule in rules:
        if rule.selector == selector and _media_applies(rule.media, width):
            value = rule.declarations.get(prop, value)
    return value


def _rules() -> list[CssRule]:
    return _parse_css(_style_text(_read(LAYOUT_PATH)))


def test_audio_index_grids_auto_fill_with_comfortable_cards():
    rules = _rules()
    for selector in ('.audio-recent-grid', '.audio-show-grid'):
        columns = _resolved(rules, selector, 'grid-template-columns', 1280)
        assert columns == 'repeat(auto-fill,minmax(190px,1fr))'
        assert _resolved(rules, selector, 'gap', 1280) == '20px'
        assert _resolved(rules, selector, 'gap', 390) == '16px'


def test_audio_index_is_plain_white_page_without_magazine_tokens():
    index = _read(INDEX_PATH)
    layout = _read(LAYOUT_PATH)
    source = index + layout

    for token in (
        '#faf8f3',
        '#fffefb',
        'font-size:42px',
        '好节目，慢慢听。',
        'FEWGOOD / AUDIO',
        'audio-local-nav',
        'audio-heading-number',
        '.audio-preview-lede',
    ):
        assert token not in source

    assert '--paper:#fff' in layout
    assert '--surface:#fff' in layout
    assert '--ink:#0f0f0f' in layout
    assert '--muted:#606060' in layout
    assert '--line:#e5e5e5' in layout
    assert '<h1>音频播客</h1>' not in index
    assert _resolved(_rules(), '.audio-preview', 'background', 1280) == '#fff'


def test_audio_index_cards_use_real_square_cover_metadata_only():
    index = _read(INDEX_PATH)
    rules = _rules()

    assert 'episodePath(show, episode, base)' in index
    assert 'showPath(show.slug, 1, base)' in index
    assert 'const coverUrl = episode.cover_url || show?.feed?.cover_url;' in index
    assert 'const coverUrl = show.feed?.cover_url;' in index
    assert 'srcset={coverSrcset(coverUrl, CARD_COVER_WIDTHS)}' in index
    assert '{episode.title}' in index
    assert '{show.display_name}' in index
    assert '{show_name}' in index
    assert '{show.publisher}' in index
    assert '<time datetime={episode.published_at_utc}>{published}</time>' in index
    assert 'relativePublishedTime(episode.published_at_utc)' in index
    assert '{episode.duration_display}' in index
    assert '{EPISODE_COUNT_LABEL} {show.episodes.length} 集' in index
    assert '近 30 天无入选' not in index
    assert 'description_text' not in index and 'description_html' not in index

    for token in ('rating', 'subscriber', 'review_count', '评分', '订阅数', '收听数'):
        assert token not in index.lower()

    assert _resolved(rules, '.audio-card-media', 'aspect-ratio', 1280) == '1'
    assert _resolved(rules, '.audio-card-media', 'border-radius', 1280) == '12px'
    assert _resolved(rules, '.audio-card-cover', 'object-fit', 1280) == 'cover'
    assert _resolved(rules, '.audio-card-title', 'font-size', 1280) == '16px'
    assert _resolved(rules, '.audio-card-title', 'font-weight', 1280) == '500'
    assert _resolved(rules, '.audio-card-title', '-webkit-line-clamp', 1280) == '2'
    assert _resolved(rules, '.audio-card-title', 'min-height', 1280) == '44px'
    assert _resolved(rules, '.audio-recent-card', 'min-width', 1280) == '0'
    assert _resolved(rules, '.audio-show-card', 'min-width', 1280) == '0'


def test_audio_catalog_tabs_filter_each_view_and_keep_heat_claims_honest():
    index = _read(INDEX_PATH)
    layout = _read(LAYOUT_PATH)

    catalog = json.loads((ROOT / 'site/src/data/audio_podcast_catalog.json').read_text(encoding='utf-8'))
    categories = catalog['catalog']['categories']
    assert categories == ['认知', '商业', '心理', '人文', '搞笑', '生活']
    assert catalog['catalog']['requested_show_count'] == 40
    assert catalog['catalog']['confirmed_show_count'] == 40
    assert catalog['catalog']['missing_shows'] == []
    xuan = next(show for show in catalog['shows'] if show['slug'] == 'xuan-er-wei-jue')
    assert xuan['name'] == '玄而未决'
    assert xuan['category'] == '心理'
    assert xuan['source_status'] == 'rss_unavailable_limited_public_page'
    assert "data.catalog?.categories" in index
    assert "data-audio-category={category}" in index
    assert 'role="tablist"' in index
    assert 'recent-tab' in index and 'directory-tab' in index
    assert 'data-category-filters="recent"' in index
    assert 'data-category-filters="directory"' in index
    assert 'data-audio-card-category={show.category' in index
    assert '非热度排序 · 排除日更节目' not in index
    assert '周热度精选待可靠单集热度源' in index
    assert '日更节目 · 不进入近期精选' in index
    assert '悬而未决' not in index
    assert '张小珺' not in index
    assert "identity_verified_feed_unavailable" in index
    assert "show.episodes.length === 0" in index
    assert '暂未获取到单集' in index
    assert '内容暂不可用' in index
    show_page = _read(ROOT / 'site/src/components/AudioPodcastShowPage.astro')
    assert '仅收录近期公开免费单集，非完整历史' in index
    assert 'show.limited_public_page_fallback' in index
    assert '!show.limited_public_page_fallback && !recent.some' not in index
    assert '仅收录近期公开免费单集，非完整历史' in show_page
    assert "show.episodes.length === 0 &&" in show_page
    assert 'min-height:40px' in layout  # the show-page return link remains a usable target


def test_audio_index_uses_compact_source_backed_coverage_and_text_filters():
    index = _read(INDEX_PATH)
    layout = _read(LAYOUT_PATH)
    assert 'loading="lazy"' in index
    assert 'loading={index < 4 ?' not in index
    filter_css = layout.split('.audio-category-filters', 1)[1].split('.audio-picks-status', 1)[0]
    assert 'border-radius:18px' not in filter_css
