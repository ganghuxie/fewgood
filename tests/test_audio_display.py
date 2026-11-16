"""Display-only appendix boundaries, real RSS fixtures, and scoped UI behavior."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_display_filter_real_feeds_and_conservative_boundaries():
    subprocess.run(['node', '--input-type=module', '-e', r'''
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {displayNotes, episodeExcerpt} from './site/src/lib/audio-podcast-display.mjs';
for (const f of JSON.parse(readFileSync('tests/fixtures/audio-display-keep.json'))) {
 assert.ok(displayNotes(f.html).includes(f.keep), f.title);
}
const fixtures = JSON.parse(readFileSync('tests/fixtures/audio-display.json'));
for (const f of fixtures) {
 const result = displayNotes(f.html);
 assert.ok(result.includes(f.html.match(/<p>(.*?)<\/p>/s)[1]));
 assert.doesNotMatch(result, /相关播客：133|🎧 相关节目|我们还有这些播客/);
}
const wine = displayNotes(fixtures[1].html);
assert.match(wine, /相关书籍/); assert.match(wine, /夜晚的潜水艇/);
assert.doesNotMatch(wine, /E52 与少楠聊/);
assert.match(wine, /知行小酒馆公告牌/);
for (const title of ['【推荐播客】','🎧 相关节目','相关播客：','「节目推荐」','相关推荐']) {
 const html = `<p>实际介绍</p><p><strong>${title}</strong></p><ul><li><a href="https://www.xiaoyuzhoufm.com/episode/abc">其他单集</a></li></ul><h3>幕后制作</h3><p>制作：张三</p>`;
 const result = displayNotes(html);
 assert.doesNotMatch(result, /其他单集/);
 assert.match(result, /幕后制作/); assert.match(result, /张三/);
 assert.equal(episodeExcerpt({description_html:html}), '实际介绍 幕后制作 制作：张三');
}
for (const prose of ['1:22:08 节目推荐——不一定是宝藏','一直关注我们的听众','你有没有相关推荐？','把我们的节目推荐给朋友','感谢所有订阅我们节目的朋友','本期节目推荐作品清单','更多节目相关资讯，欢迎关注微博']) {
 assert.match(displayNotes(`<p>${prose}</p>`), new RegExp(prose));
}
assert.match(displayNotes('<p>本期我们谈<strong>相关节目</strong>在行业中的意义。</p>'), /相关节目/);
assert.match(displayNotes('<div><p>相关播客：133-旧节目</p><ul><li>129-旧节目</li></ul><h3>2. 制作</h3><p>制作人</p></div>'), /2. 制作/);
const reading = '<p>延伸阅读</p><ul><li><a href="https://book.douban.com/subject/1">本期书目</a></li></ul>';
assert.equal(displayNotes(reading), reading);
const uncertain = '<p>相关节目</p><p>这段解释本期讨论的作品，不能判断为推广。</p><ul><li>一本书</li></ul>';
assert.match(displayNotes(uncertain), /这段解释/); assert.match(displayNotes(uncertain), /一本书/);
assert.equal(displayNotes('', '介绍\n相关播客：133-其他单集\n129-其他单集'), '<p>介绍</p>');
assert.equal(episodeExcerpt({description_html:'<p>相关播客：133-其他单集</p><ul><li>129-另一集</li></ul>'}), '');
assert.equal(episodeExcerpt({description_html:'<p>简介 &amp; 内容</p>'}), '简介 & 内容');
assert.equal(fixtures[0].html.includes('相关播客：133'), true, 'raw input untouched');
'''], cwd=ROOT, check=True)


def test_player_copy_tabs_and_scoped_390_chip_scroll():
    detail = (ROOT / 'site/src/components/AudioPodcastEpisodePage.astro').read_text()
    layout = (ROOT / 'site/src/components/AudioPodcastLayout.astro').read_text()
    show = (ROOT / 'site/src/components/AudioPodcastShowPage.astro').read_text()
    for phrase in ['enclosure', '重定向', '不要立即认为失败', '发布者单集说明']:
        assert phrase not in detail + layout
    assert '播放失败' in detail
    assert 'episodeExcerpt(episode)' in show
    assert '单集更新' in show and '节目详情' in show
    assert 'show.feed?.description_text' in show
    assert 'aria-selected="true"' in show and 'about-panel' in show
    assert 'onerror="this.hidden=true"' in show
    # Execute the actual inline layout script with clipped 390px geometry.
    script = layout.split('<script is:inline>')[1].split('</script>')[0]
    subprocess.run(['node', '--input-type=module', '-e', '''
import assert from 'node:assert/strict';
const chip = {getBoundingClientRect:()=>({left:350,right:438,width:88})};
const bar = {scrollLeft:0,getBoundingClientRect:()=>({left:0,right:390,width:390}),querySelector:()=>chip};
globalThis.document = {querySelector:s=>s === '.audio-preview' ? {} : bar};
globalThis.requestAnimationFrame = fn => fn();
''' + script + '''
assert.equal(bar.scrollLeft, 199);
bar.scrollLeft=0;
document.querySelector=()=>null;
revealAudioChip();
assert.equal(bar.scrollLeft,0);
'''], cwd=ROOT, check=True)
