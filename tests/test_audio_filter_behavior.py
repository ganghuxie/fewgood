"""Behavioral regression for the audio category filter cascade."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_audio_category_filter_hides_cards_in_the_actual_layout_cascade():
    subprocess.run(['node', '--input-type=module', '-e', r'''
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const index = readFileSync('site/src/components/AudioPodcastIndex.astro', 'utf8');
const layout = readFileSync('site/src/components/AudioPodcastLayout.astro', 'utf8');
const inline = index.match(/<script is:inline>([\s\S]*?)<\/script>/)?.[1];
assert.ok(inline, 'audio index inline behavior is present');
assert.match(layout, /\.audio-preview \[hidden\]\{display:none !important\}/);

function classList() { const values = new Set(); return {toggle:(name,on) => on ? values.add(name) : values.delete(name), contains:name => values.has(name)}; }
function element({dataset = {}, id = '', hidden = false, controls = ''} = {}) {
  const listeners = new Map();
  return {
    dataset, id, hidden, tabIndex: 0, classList: classList(),
    attributes: controls ? {'aria-controls': controls} : {},
    addEventListener:(type, callback) => listeners.set(type, callback),
    fire:(type, event = {}) => listeners.get(type)?.(event),
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getAttribute(name) { return this.attributes[name] ?? null; },
    closest(selector) { return selector === '[data-audio-category]' ? this : null; },
  };
}
const categories = ['认知', '商业', '心理', '人文', '搞笑', '生活'];
const directoryCards = [
  ['纵横四海', '认知'], ['无人知晓', '认知'], ['自我进化论', '认知'],
  ['岩中花述', '心理'], ['玄而未决', '心理'], ['故事FM', '人文'],
  ['谐星聊天会', '搞笑'], ['宁浪别野', '生活'], ['半拿铁', '商业'],
].map(([name, category]) => Object.assign(element({dataset:{audioCardCategory:category}}), {name, dot:{hidden:false}}));
const recentCards = [Object.assign(element({dataset:{audioCardCategory:'认知'}}), {name:'近期认知'})];
const panels = {recent: element({id:'recent-panel'}), directory: element({id:'directory-panel', hidden:true})};
const tabs = [element({id:'recent-tab', controls:'recent-panel'}), element({id:'directory-tab', controls:'directory-panel'})];
const directoryButtons = [element({dataset:{audioCategory:'all'}}), ...categories.map(category => element({dataset:{audioCategory:category}}))];
const recentButtons = [element({dataset:{audioCategory:'all'}}), ...categories.map(category => element({dataset:{audioCategory:category}}))];
const directoryFilters = element({dataset:{categoryFilters:'directory'}});
const recentFilters = element({dataset:{categoryFilters:'recent'}});
directoryFilters.querySelectorAll = () => directoryButtons;
recentFilters.querySelectorAll = () => recentButtons;
const empty = {directory: element({hidden:true}), recent: element({hidden:true})};
const documentMock = {
  querySelectorAll(selector) {
    if (selector === '.audio-index-tabs [role="tab"]') return tabs;
    if (selector === '[data-category-filters]') return [recentFilters, directoryFilters];
    const view = selector.match(/data-audio-grid="([^"]+)"/)?.[1];
    if (view) return view === 'directory' ? directoryCards : recentCards;
    return [];
  },
  querySelector(selector) { const view = selector.match(/data-audio-empty="([^"]+)"/)?.[1]; return empty[view] || null; },
  getElementById(id) { return panels[id.replace('-panel', '')] || null; },
};
globalThis.document = documentMock;
eval(inline);

// Cascade evaluator deliberately consumes the actual layout CSS, not just the hidden property.
function computedDisplay(card) {
  const rules = [{selector:'[hidden]', display:'none', important:false, order:-1, specificity:10}];
  let order = 0;
  for (const match of layout.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const display = match[2].match(/display\s*:\s*([^;}]+)/)?.[1];
    if (!display) continue;
    for (const selector of match[1].split(',')) {
      const trimmed = selector.trim();
      const matches = (trimmed === '.audio-show-card' || trimmed === '.audio-recent-card')
        || (card.hidden && trimmed === '[hidden]')
        || (card.hidden && trimmed === '.audio-preview [hidden]');
      if (!matches) continue;
      rules.push({selector:trimmed, display:display.replace(/\s*!important\s*$/, '').trim(), important:/!important/.test(display), order:order++, specificity:trimmed.includes('.audio-preview') ? 20 : 10});
    }
  }
  rules.sort((a, b) => Number(a.important) - Number(b.important) || a.specificity - b.specificity || a.order - b.order);
  return rules.at(-1).display;
}
const visible = cards => cards.filter(card => computedDisplay(card) !== 'none').map(card => card.name);
const click = (filters, buttons, category) => filters.fire('click', {target: buttons.find(button => button.dataset.audioCategory === category)});

// This is the user-reported failure: selected 心理 must not leave cognitive cards displayed.
tabs[1].fire('click');
click(directoryFilters, directoryButtons, '心理');
assert.deepEqual(visible(directoryCards), ['岩中花述', '玄而未决']);
assert.equal(computedDisplay(directoryCards[0]), 'none');
assert.equal(computedDisplay(directoryCards[1]), 'none');
assert.equal(computedDisplay(directoryCards[2]), 'none');
assert.equal(directoryCards[3].dot.hidden, false, 'newness-dot presence does not interfere with filtering');

for (const category of categories) {
  click(directoryFilters, directoryButtons, category);
  assert.ok(visible(directoryCards).every(name => directoryCards.find(card => card.name === name).dataset.audioCardCategory === category), category);
}
click(directoryFilters, directoryButtons, 'all');
assert.equal(visible(directoryCards).length, directoryCards.length);
tabs[0].fire('click'); assert.equal(panels.directory.hidden, true); assert.equal(panels.recent.hidden, false);
tabs[1].fire('click'); assert.equal(panels.directory.hidden, false);
click(directoryFilters, directoryButtons, '认知'); click(directoryFilters, directoryButtons, '心理'); click(directoryFilters, directoryButtons, '认知'); click(directoryFilters, directoryButtons, '心理');
assert.deepEqual(visible(directoryCards), ['岩中花述', '玄而未决'], 'rapid changes leave only the final category visible');
for (const category of categories) {
  click(recentFilters, recentButtons, category);
  assert.ok(visible(recentCards).every(name => recentCards.find(card => card.name === name).dataset.audioCardCategory === category), `recent ${category}`);
}
click(recentFilters, recentButtons, '生活');
assert.equal(visible(recentCards).length, 0); assert.equal(empty.recent.hidden, false, 'empty state is visible');
click(recentFilters, recentButtons, 'all'); assert.equal(visible(recentCards).length, 1); assert.equal(empty.recent.hidden, true);
console.log('audio filter visibility/cascade behavior passed');
'''], cwd=ROOT, check=True)
