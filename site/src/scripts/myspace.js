import { track } from './analytics.js';
import { MYSPACE_KEY, MAX_ACTIVE_COLUMNS, defaultState, validateState } from '../lib/myspace-schema.mjs';
import { MYSPACE_SOURCES } from '../lib/brand.mjs';

const enabled = String(import.meta.env.PUBLIC_ALPHA_MYSPACE ?? 'true').toLowerCase() !== 'false';
const sourceById = new Map(MYSPACE_SOURCES.map(source => [source.id, source]));
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const duration = seconds => `${Math.floor((Number(seconds) || 0) / 60)}:${String((Number(seconds) || 0) % 60).padStart(2, '0')}`;

function load() {
  try { return validateState(JSON.parse(localStorage.getItem(MYSPACE_KEY) || 'null'), MYSPACE_SOURCES) || defaultState(); }
  catch { return defaultState(); }
}
function save(state) {
  const checked = validateState(state, MYSPACE_SOURCES);
  if (!checked) return false;
  try { localStorage.setItem(MYSPACE_KEY, JSON.stringify(checked)); } catch { return false; }
  track('myspace_save', { active_columns: checked.columns.filter(column => column.enabled).length });
  return true;
}
function avatar(video) {
  const name = video.channel || '频道';
  const letter = [...name.trim()][0] || '频';
  let hash = 0; for (const char of name) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  const color = ['#d14b4b', '#b06b2f', '#8a6d1d', '#4f8a3d', '#357a8a', '#5367a6', '#7a5795'][hash % 7];
  return `<span class="channel-avatar channel-avatar-letter" style="background-color:${color}" aria-hidden="true">${esc(letter)}</span>`;
}
function card(video, source, base) {
  return `<a class="video-card" href="${base}/v/${encodeURIComponent(video.id)}/"><div class="thumbnail"><img loading="lazy" src="https://i.ytimg.com/vi/${encodeURIComponent(video.id)}/maxresdefault.jpg" onerror="this.onerror=null;this.src='https://i.ytimg.com/vi/${encodeURIComponent(video.id)}/mqdefault.jpg'" alt=""><span class="duration">${duration(video.duration_seconds)}</span></div><div class="video-info">${avatar(video)}<div><h2 class="video-title">${esc(video.title)}</h2><p class="video-meta">${esc(video.channel)}</p><p class="video-meta">${esc(source.label)}</p></div></div></a>`;
}
function matching(videos, source) {
  const results = videos.filter(video => Array.isArray(video.sections) && video.sections.includes(source.section));
  if (source.id === 'community:newest') return results.sort((a, b) => Date.parse(b.selected_at || 0) - Date.parse(a.selected_at || 0));
  if (source.section === 'community') return results.sort((a, b) => (b.recommenders || 0) - (a.recommenders || 0) || (b.months || 0) - (a.months || 0));
  return results.sort((a, b) => (b.view_count || 0) - (a.view_count || 0));
}

const shell = document.querySelector('[data-alpha-myspace]');
const explore = document.querySelector('[data-explore-view]');
const space = document.querySelector('[data-myspace-view]');
if (enabled && shell && explore && space) {
  const header = document.querySelector('.site-header');
  const chipbar = header?.querySelector('.chipbar');
  if (header && chipbar) { header.classList.add('alpha-video-header'); header.insertBefore(shell, chipbar); }
  shell.hidden = false;
  let state = load();
  let catalog;
  let mode = 'myspace';
  const base = (document.querySelector('main')?.dataset.base || '').replace(/\/$/, '');
  const catalogPromise = fetch(`${base}/catalog.json`).then(response => response.ok ? response.json() : Promise.reject(new Error('catalog')));
  const activeColumns = () => state.columns.filter(column => column.enabled);

  if (chipbar) {
    chipbar.querySelectorAll('a').forEach(link => link.setAttribute('data-explore-tab', ''));
    chipbar.dataset.exploreTabs = chipbar.querySelector('nav')?.innerHTML || '';
  }
  const updateTabs = () => {
    if (!chipbar) return;
    const nav = chipbar.querySelector('nav');
    if (!nav) return;
    if (mode === 'explore') nav.innerHTML = chipbar.dataset.exploreTabs;
    else nav.innerHTML = activeColumns().map((column, index) => `<button type="button" data-myspace-tab="${esc(column.id)}" class="${index === 0 ? 'active' : ''}">${esc(sourceById.get(column.source)?.label || column.source)}</button>`).join('');
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
  const persist = keepEditor => { if (save(state)) render(keepEditor); };
  const renderEditor = () => {
    const dialog = space.querySelector('[data-myspace-editor]');
    if (!dialog) return;
    const available = MYSPACE_SOURCES.filter(source => !state.columns.some(column => column.source === source.id));
    dialog.innerHTML = `<div class="myspace-editor-inner"><div class="myspace-editor-title"><h2>管理栏目</h2><button class="myspace-editor-close" type="button" data-editor-close aria-label="关闭">×</button></div><p class="myspace-editor-note">显示至多 ${MAX_ACTIVE_COLUMNS} 个栏目；顺序会同步到上方标签。</p>${state.columns.map((column, index) => `<div class="myspace-row"><label><input type="checkbox" data-enable="${esc(column.id)}" ${column.enabled ? 'checked' : ''} aria-label="显示 ${esc(sourceById.get(column.source)?.label || column.source)}"></label><span class="myspace-row-name">${esc(sourceById.get(column.source)?.label || column.source)}</span><button type="button" data-up="${esc(column.id)}" ${index === 0 ? 'disabled' : ''} aria-label="上移">↑</button><button type="button" data-down="${esc(column.id)}" ${index === state.columns.length - 1 ? 'disabled' : ''} aria-label="下移">↓</button><button type="button" data-remove="${esc(column.id)}" aria-label="移除">×</button></div>`).join('')}<div class="myspace-add"><select data-add aria-label="添加栏目"><option value="">添加现有栏目…</option>${available.map(source => `<option value="${source.id}">${esc(source.label)}</option>`).join('')}</select></div></div>`;
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
      const source = event.target.value;
      if (!source || state.columns.length >= MYSPACE_SOURCES.length) return;
      state.columns.push({ id: source, source, enabled: activeColumns().length < MAX_ACTIVE_COLUMNS });
      persist(true);
    });
  };
  const renderColumns = async () => {
    const host = space.querySelector('[data-myspace-columns]');
    if (!host) return;
    host.innerHTML = '<p class="myspace-loading">正在读取现有内容池…</p>';
    try { catalog ||= await catalogPromise; if (!Array.isArray(catalog)) throw new Error('catalog'); }
    catch { host.innerHTML = '<p class="myspace-loading">内容目录暂时无法加载，请稍后再试。</p>'; return; }
    host.innerHTML = activeColumns().map(column => {
      const source = sourceById.get(column.source);
      const videos = matching(catalog, source).slice(0, 8);
      return `<section class="myspace-column" data-myspace-column="${esc(column.id)}"><h2>${esc(source.label)}</h2>${videos.length ? `<div class="video-grid">${videos.map(video => card(video, source, base)).join('')}</div>` : '<p class="myspace-loading">该栏目暂时没有匹配视频。</p>'}</section>`;
    }).join('') || '<p class="myspace-loading">还没有栏目。<a href="' + (base || '') + '/">从现有主题里挑几个开始</a></p>';
  };
  const render = (keepEditor = false) => {
    space.innerHTML = '<div class="myspace-heading"><div><h1>我的空间</h1><p>你的栏目、你的顺序。只使用现有内容池。</p></div><button class="myspace-manage" type="button" data-myspace-manage aria-label="管理栏目" title="管理栏目">⚙</button></div><dialog class="myspace-editor" data-myspace-editor aria-label="管理我的空间"></dialog><div class="myspace-columns" data-myspace-columns><p class="myspace-loading">正在读取现有内容池…</p></div>';
    space.querySelector('[data-myspace-manage]')?.addEventListener('click', () => { renderEditor(); space.querySelector('[data-myspace-editor]')?.showModal(); });
    renderColumns(); updateTabs();
    if (keepEditor) { renderEditor(); space.querySelector('[data-myspace-editor]')?.showModal(); }
  };
  const setMode = next => {
    mode = next;
    const mine = mode === 'myspace';
    explore.hidden = mine; space.hidden = !mine;
    shell.querySelectorAll('[data-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.mode === mode)));
    updateTabs();
    if (mine) render();
  };
  shell.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => {
    const next = button.dataset.mode;
    if (next === mode) return;
    setMode(next); track('mode_switch', { mode: next });
  }));
  setMode('explore');
}
