import { track } from './analytics.js';
import { MYSPACE_KEY, MAX_ACTIVE_COLUMNS, defaultState, validateState, topicColumnId, isTopicColumn } from '../lib/myspace-schema.mjs';
import { MYSPACE_SOURCES } from '../lib/brand.mjs';
import { templateToColumns, templateColumnsReady } from '../lib/template-columns.mjs';
import { card as videoCard } from '../lib/myspace-card.mjs';
import { showPrompt } from './prompts.js';

const enabled = String(import.meta.env.PUBLIC_ALPHA_MYSPACE ?? 'true').toLowerCase() !== 'false';
const LAST_TAB_KEY = 'fewgood:lastTab';
const DEVICE_NOTICE = '这些栏目只存在这台设备的浏览器里';
const feedSourceById = new Map(MYSPACE_SOURCES.map(source => [source.id, source]));
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

const shell = document.querySelector('[data-alpha-myspace]');
const explore = document.querySelector('[data-explore-view]');
const space = document.querySelector('[data-myspace-view]');

if (enabled && shell && explore && space) {
  const header = document.querySelector('.site-header');
  const chipbar = header?.querySelector('.chipbar');
  if (header && chipbar) { header.classList.add('alpha-video-header'); header.insertBefore(shell, chipbar); }
  shell.hidden = false;
  const base = (document.querySelector('main')?.dataset.base || '').replace(/\/$/, '');
  const fetchJSON = path => fetch(`${base}${path}`).then(response => response.ok ? response.json() : Promise.reject(new Error(path))).catch(() => null);

  let state = null;
  let catalog = [];
  let topics = [];
  const topicsById = new Map();
  let pool = [];
  const poolById = new Map();
  const zhById = new Map();
  let templates = [];
  let mode = 'explore';

  const sourceFor = column => {
    if (isTopicColumn(column)) {
      const topic = topicsById.get(column.topic_id || column.source);
      return { id: column.topic_id || column.source, label: column.label || topic?.name_zh || column.source, kind: 'topic', section: 'topic' };
    }
    return feedSourceById.get(column.source) || { id: column.source, label: column.source, section: column.source };
  };
  const columnLabel = column => sourceFor(column).label;
  const load = () => {
    try { return validateState(JSON.parse(localStorage.getItem(MYSPACE_KEY) || 'null'), MYSPACE_SOURCES, topics) || defaultState(); }
    catch { return defaultState(); }
  };
  const save = current => {
    const checked = validateState(current, MYSPACE_SOURCES, topics);
    if (!checked) return false;
    try { localStorage.setItem(MYSPACE_KEY, JSON.stringify(checked)); } catch { return false; }
    track('myspace_save', { active_columns: checked.columns.filter(column => column.enabled).length });
    return true;
  };
  const activeColumns = () => (state?.columns || []).filter(column => column.enabled);

  function card(video, column) {
    const href = `${base}/v/${encodeURIComponent(video.id)}/${isTopicColumn(column) ? `?from=${encodeURIComponent('topic:' + (column.topic_id || column.source))}` : ''}`;
    return videoCard(video, href, zhById.get(video.id) || null);
  }
  function matching(videos, column) {
    if (isTopicColumn(column)) {
      const topic = topicsById.get(column.topic_id || column.source);
      const ids = new Set(topic?.video_ids || []);
      return videos.filter(video => ids.has(video.id)).sort((a, b) => (b.recommenders || 0) - (a.recommenders || 0) || (b.months || 0) - (a.months || 0));
    }
    const source = feedSourceById.get(column.source);
    const results = videos.filter(video => Array.isArray(video.sections) && video.sections.includes(source.section));
    if (source.id === 'community:newest') return results.sort((a, b) => Date.parse(b.selected_at || 0) - Date.parse(a.selected_at || 0));
    if (source.section === 'community') return results.sort((a, b) => (b.recommenders || 0) - (a.recommenders || 0) || (b.months || 0) - (a.months || 0));
    return results.sort((a, b) => (b.view_count || 0) - (a.view_count || 0));
  }

  if (chipbar) {
    chipbar.querySelectorAll('a').forEach(link => link.setAttribute('data-explore-tab', ''));
    chipbar.dataset.exploreTabs = chipbar.querySelector('nav')?.innerHTML || '';
  }
  const updateTabs = () => {
    if (!chipbar) return;
    const nav = chipbar.querySelector('nav');
    if (!nav) return;
    if (mode === 'explore') nav.innerHTML = chipbar.dataset.exploreTabs;
    else nav.innerHTML = activeColumns().map((column, index) => `<button type="button" data-myspace-tab="${esc(column.id)}" class="${index === 0 ? 'active' : ''}">${esc(columnLabel(column))}</button>`).join('');
    nav.querySelectorAll('[data-myspace-tab]').forEach(tab => tab.addEventListener('click', () => {
      const target = space.querySelector(`[data-myspace-column="${CSS.escape(tab.dataset.myspaceTab)}"]`);
      if (target) {
        const headerGap = 12;
        const headerHeight = header?.getBoundingClientRect().height || 0;
        target.style.scrollMarginTop = `${headerHeight + headerGap}px`;
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      nav.querySelectorAll('[data-myspace-tab]').forEach(item => item.classList.toggle('active', item === tab));
    }));
  };

  const subscribedTopicIds = () => new Set(state.columns.filter(isTopicColumn).map(column => column.topic_id || column.source));
  const subscribeTopic = topicId => {
    if (!topicId || !topicsById.has(topicId)) return false;
    if (subscribedTopicIds().has(topicId)) return false;
    if (activeColumns().length >= MAX_ACTIVE_COLUMNS) return false;
    const topic = topicsById.get(topicId);
    state.columns.push({ id: topicColumnId(topicId), source: topicId, kind: 'topic', topic_id: topicId, label: topic?.name_zh || topicId, enabled: true });
    if (!save(state)) { state.columns.pop(); return false; }
    render();
    paintTopicChips();
    if (activeColumns().length === 3) showPrompt('这 3 个栏目目前只存在这台电脑的浏览器里。注册后换手机也能看。', { ttl: 0 });
    return true;
  };

  const persist = keepEditor => { if (save(state)) render(keepEditor); };

  const renderEditor = () => {
    const dialog = space.querySelector('[data-myspace-editor]');
    if (!dialog) return;
    const topicOptions = topics
      .filter(topic => !state.columns.some(column => isTopicColumn(column) && (column.topic_id || column.source) === topic.id))
      .map(topic => `<option value="${esc('topic:' + topic.id)}">${esc(topic.name_zh)}</option>`).join('');
    const feedOptions = MYSPACE_SOURCES
      .filter(source => !state.columns.some(column => !isTopicColumn(column) && column.source === source.id))
      .map(source => `<option value="${esc(source.id)}">${esc(source.label)}</option>`).join('');
    dialog.innerHTML = `<div class="myspace-editor-inner"><div class="myspace-editor-title"><h2>管理栏目</h2><button class="myspace-editor-close" type="button" data-editor-close aria-label="关闭">×</button></div><p class="myspace-editor-note">显示至多 ${MAX_ACTIVE_COLUMNS} 个栏目；顺序会同步到上方标签。</p>${state.columns.map((column, index) => `<div class="myspace-row"><label><input type="checkbox" data-enable="${esc(column.id)}" ${column.enabled ? 'checked' : ''} aria-label="显示 ${esc(columnLabel(column))}"></label><span class="myspace-row-name">${esc(columnLabel(column))}</span><button type="button" data-up="${esc(column.id)}" ${index === 0 ? 'disabled' : ''} aria-label="上移">↑</button><button type="button" data-down="${esc(column.id)}" ${index === state.columns.length - 1 ? 'disabled' : ''} aria-label="下移">↓</button><button type="button" data-remove="${esc(column.id)}" aria-label="移除">×</button></div>`).join('')}<div class="myspace-add"><select data-add aria-label="添加栏目"><option value="">添加现有栏目…</option>${feedOptions}${topicOptions}</select></div></div>`;
    dialog.querySelector('[data-editor-close]')?.addEventListener('click', () => dialog.close());
    dialog.querySelectorAll('[data-enable]').forEach(input => input.addEventListener('change', () => {
      const column = state.columns.find(item => item.id === input.dataset.enable);
      if (!column) return;
      if (input.checked && activeColumns().length >= MAX_ACTIVE_COLUMNS) { input.checked = false; return; }
      column.enabled = input.checked; persist(true);
    }));
    dialog.querySelectorAll('[data-up],[data-down]').forEach(button => button.addEventListener('click', () => {
      const id = button.dataset.up || button.dataset.down;
      const index = state.columns.findIndex(item => item.id === id);
      const target = button.dataset.up ? index - 1 : index + 1;
      if (index >= 0 && state.columns[target]) [state.columns[index], state.columns[target]] = [state.columns[target], state.columns[index]];
      persist(true);
    }));
    dialog.querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => {
      state.columns = state.columns.filter(column => column.id !== button.dataset.remove);
      if (!state.columns.length) state = defaultState();
      persist(true);
    }));
    dialog.querySelector('[data-add]')?.addEventListener('change', event => {
      const value = event.target.value;
      if (!value) return;
      if (value.startsWith('topic:')) subscribeTopic(value.slice('topic:'.length));
      else {
        if (state.columns.length >= MYSPACE_SOURCES.length + topics.length) return;
        state.columns.push({ id: value, source: value, kind: 'feed', topic_id: null, label: null, enabled: activeColumns().length < MAX_ACTIVE_COLUMNS });
        if (activeColumns().length === 3) showPrompt('这 3 个栏目目前只存在这台电脑的浏览器里。注册后换手机也能看。', { ttl: 0 });
        persist(true);
      }
    });
  };

  const renderColumns = () => {
    const host = space.querySelector('[data-myspace-columns]');
    if (!host) return;
    host.innerHTML = '<p class="myspace-loading">正在读取现有内容池…</p>';
    if (!Array.isArray(catalog) && !Array.isArray(pool)) return;
    host.innerHTML = activeColumns().map(column => {
      const isTopic = isTopicColumn(column);
      const videos = matching(isTopic ? pool : catalog, column).slice(0, 8);
      return `<section class="myspace-column" data-myspace-column="${esc(column.id)}"><h2>${esc(columnLabel(column))}</h2>${videos.length ? `<div class="video-grid">${videos.map(video => card(video, column)).join('')}</div>` : '<p class="myspace-loading">该栏目暂时没有匹配视频。</p>'}</section>`;
    }).join('') || '<p class="myspace-loading">还没有栏目。<a href="' + (base || '') + '/">从现有主题里挑几个开始</a></p>';
  };

  const hasTopicColumns = () => state.columns.some(isTopicColumn);
  const renderTemplates = () => {
    const host = space.querySelector('[data-template-picker]');
    if (!host) return;
    if (!templates.length || hasTopicColumns()) { host.hidden = true; return; }
    host.hidden = false;
    host.innerHTML = `<div class="template-picker"><div><h2>从模板开始</h2><p>一键生成你的空间，随时可以调整。</p></div><div class="template-actions">${templates.map(template => `<button type="button" data-template="${esc(template.id)}">${esc(template.name_zh)}</button>`).join('')}<button type="button" class="template-skip" data-template-skip>跳过</button></div></div>`;
    host.querySelectorAll('[data-template]').forEach(button => button.addEventListener('click', () => {
      const template = templates.find(item => item.id === button.dataset.template);
      if (!template) return;
      const columns = templateToColumns(template, MYSPACE_SOURCES, topics).slice(0, MAX_ACTIVE_COLUMNS);
      if (!columns.length) return;
      state.columns = columns;
      save(state);
      render();
    }));
    host.querySelector('[data-template-skip]')?.addEventListener('click', () => { host.hidden = true; });
  };

  const paintTopicChips = () => {
    const subscribed = subscribedTopicIds();
    document.querySelectorAll('[data-topic-subscribe]').forEach(button => {
      const id = button.dataset.topicSubscribe;
      const active = subscribed.has(id);
      button.classList.toggle('is-subscribed', active);
      button.textContent = active ? '已订阅主题' : '订阅这个主题';
    });
  };
  const renderHotTopics = () => {
    const host = document.querySelector('[data-hot-topics]');
    if (!host) return;
    const hot = topics.filter(topic => Number(topic.added_last_24h) > 0).sort((a, b) => Number(b.added_last_24h) - Number(a.added_last_24h)).slice(0, 8);
    host.hidden = !hot.length;
    if (!hot.length) return;
    host.innerHTML = `<h2>热门主题</h2><div class="hot-topics-row">${hot.map(topic => `<button type="button" data-topic-subscribe="${esc(topic.id)}">${esc(topic.name_zh)} <span>今日新增 ${Number(topic.added_last_24h)} 条</span></button>`).join('')}</div>`;
    paintTopicChips();
  };

  const render = (keepEditor = false) => {
    space.innerHTML = `<div class="myspace-heading"><div><h1>我的空间</h1><p class="myspace-device-note">${esc(DEVICE_NOTICE)}</p></div><button class="myspace-manage" type="button" data-myspace-manage aria-label="管理栏目" title="管理栏目">⚙</button></div><div data-template-picker hidden></div><dialog class="myspace-editor" data-myspace-editor aria-label="管理我的空间"></dialog><div class="myspace-columns" data-myspace-columns><p class="myspace-loading">正在读取现有内容池…</p></div>`;
    space.querySelector('[data-myspace-manage]')?.addEventListener('click', () => { renderEditor(); space.querySelector('[data-myspace-editor]')?.showModal(); });
    renderTemplates();
    renderColumns();
    updateTabs();
    if (keepEditor) { renderEditor(); space.querySelector('[data-myspace-editor]')?.showModal(); }
  };

  const setMode = next => {
    mode = next;
    const mine = mode === 'myspace';
    explore.hidden = mine; space.hidden = !mine;
    shell.querySelectorAll('[data-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.mode === mode)));
    try { localStorage.setItem(LAST_TAB_KEY, mode); } catch { /* private browsing */ }
    updateTabs();
    if (mine) render();
  };

  shell.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => {
    const next = button.dataset.mode;
    if (next === mode) return;
    setMode(next); track('mode_switch', { mode: next });
  }));

  document.addEventListener('click', event => {
    const chip = event.target.closest('[data-topic-subscribe]');
    if (!chip) return;
    event.preventDefault();
    event.stopPropagation();
    subscribeTopic(chip.dataset.topicSubscribe);
  });
  document.addEventListener('fewgood:subscribe-topic', event => subscribeTopic(event.detail?.topicId));

  const templatesReady = list => list.length > 0 && list.every(template => templateColumnsReady(template, MYSPACE_SOURCES, topics, catalog));

  (async () => {
    const [topicsPayload, poolPayload, templatesPayload, catalogPayload, zhPayload] = await Promise.all([
      fetchJSON('/topics.json'), fetchJSON('/hn_pool.json'), fetchJSON('/templates.json'), fetchJSON('/catalog.json'), fetchJSON('/zh.json'),
    ]);
    topics = topicsPayload?.topics || [];
    topics.forEach(topic => topicsById.set(topic.id, topic));
    pool = poolPayload?.videos || [];
    pool.forEach(video => poolById.set(video.id, video));
    templates = templatesPayload?.templates || [];
    catalog = Array.isArray(catalogPayload) ? catalogPayload : [];
    Object.entries(zhPayload?.videos || {}).forEach(([id, entry]) => zhById.set(id, entry));
    state = load();
    const last = localStorage.getItem(LAST_TAB_KEY);
    const first = (last === 'myspace' || last === 'explore') ? last : (templatesReady(templates) ? 'myspace' : 'explore');
    setMode(first);
    renderHotTopics();
    paintTopicChips();
  })();
}
