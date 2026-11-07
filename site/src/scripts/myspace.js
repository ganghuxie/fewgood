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
function sourceOptions(selected, claimed) {
  return MYSPACE_SOURCES.filter(source => source.id === selected || !claimed.has(source.id)).map(source => `<option value="${source.id}"${source.id === selected ? ' selected' : ''}>${esc(source.label)}</option>`).join('');
}
function card(video, source, base) {
  return `<a class="video-card" href="${base}/v/${encodeURIComponent(video.id)}/?from=${encodeURIComponent(source.section)}"><div class="thumbnail"><img loading="lazy" src="https://i.ytimg.com/vi/${encodeURIComponent(video.id)}/hqdefault.jpg" alt=""><span class="duration">${duration(video.duration_seconds)}</span></div><div class="video-info"><div></div><div><h2 class="video-title">${esc(video.title)}</h2><p class="video-meta">${esc(video.channel)}</p><p class="video-meta">${esc(source.label)}</p></div></div></a>`;
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
  shell.hidden = false;
  let state = load(); let catalog = null;
  const base = (document.querySelector('main')?.dataset.base || '').replace(/\/$/, '');
  const persist = () => { if (save(state)) render(); };
  const render = () => {
    const active = state.columns.filter(column => column.enabled);
    space.innerHTML = `<div class="myspace-heading"><div><h1>我的空间</h1><p>只使用你选择的现有栏目；不会根据观看记录自动调整。</p></div><span>${active.length}/${MAX_ACTIVE_COLUMNS} 个活动栏目</span></div><section class="myspace-editor" aria-label="管理我的空间"><h2>管理栏目</h2>${state.columns.map((column, index) => { const claimed = new Set(state.columns.filter(item => item.id !== column.id).map(item => item.source)); return `<div class="myspace-row"><label><input type="checkbox" data-enable="${column.id}" ${column.enabled ? 'checked' : ''}> 显示</label><select data-source="${column.id}" aria-label="选择栏目">${sourceOptions(column.source, claimed)}</select><button type="button" data-up="${column.id}" ${index === 0 ? 'disabled' : ''} aria-label="上移">↑</button><button type="button" data-down="${column.id}" ${index === state.columns.length - 1 ? 'disabled' : ''} aria-label="下移">↓</button><button type="button" data-remove="${column.id}">移除</button></div>`; }).join('')}<select data-add aria-label="添加栏目"><option value="">添加现有栏目…</option>${MYSPACE_SOURCES.filter(source => !state.columns.some(column => column.source === source.id)).map(source => `<option value="${source.id}">${esc(source.label)}</option>`).join('')}</select></section><div class="myspace-columns" data-myspace-columns><p class="myspace-loading">正在读取现有内容池…</p></div>`;
    wire(); renderColumns(active);
  };
  const wire = () => {
    space.querySelectorAll('[data-enable]').forEach(input => input.addEventListener('change', () => { const column = state.columns.find(item => item.id === input.dataset.enable); if (!column) return; if (input.checked && state.columns.filter(item => item.enabled).length >= MAX_ACTIVE_COLUMNS) { input.checked = false; return; } column.enabled = input.checked; persist(); }));
    space.querySelectorAll('[data-source]').forEach(select => select.addEventListener('change', () => { const column = state.columns.find(item => item.id === select.dataset.source); if (column && sourceById.has(select.value)) { column.id = select.value; column.source = select.value; persist(); } }));
    space.querySelectorAll('[data-up],[data-down]').forEach(button => button.addEventListener('click', () => { const id = button.dataset.up || button.dataset.down; const index = state.columns.findIndex(item => item.id === id); const target = button.dataset.up ? index - 1 : index + 1; if (index >= 0 && state.columns[target]) [state.columns[index], state.columns[target]] = [state.columns[target], state.columns[index]]; persist(); }));
    space.querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => { state.columns = state.columns.filter(column => column.id !== button.dataset.remove); if (!state.columns.length) state = defaultState(); persist(); }));
    space.querySelector('[data-add]')?.addEventListener('change', event => { const source = event.target.value; if (!source || state.columns.length >= MYSPACE_SOURCES.length) return; state.columns.push({ id: source, source, enabled: state.columns.filter(item => item.enabled).length < MAX_ACTIVE_COLUMNS }); persist(); });
  };
  const renderColumns = async active => {
    const host = space.querySelector('[data-myspace-columns]');
    try { catalog ||= await fetch(`${base}/catalog.json`).then(response => response.ok ? response.json() : Promise.reject(new Error('catalog'))); }
    catch { host.innerHTML = '<p class="myspace-loading">内容目录暂时无法加载，请稍后再试。</p>'; return; }
    host.innerHTML = active.map(column => { const source = sourceById.get(column.source); const videos = matching(catalog, source).slice(0, 8); return `<section class="myspace-column"><h2>${esc(source.label)}</h2>${videos.length ? `<div class="video-grid">${videos.map(video => card(video, source, base)).join('')}</div>` : '<p class="myspace-loading">该栏目暂时没有匹配视频。</p>'}</section>`; }).join('') || '<p class="myspace-loading">请在上方添加一个栏目。</p>';
  };
  shell.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => { const mine = button.dataset.mode === 'myspace'; explore.hidden = mine; space.hidden = !mine; shell.querySelectorAll('[data-mode]').forEach(item => item.setAttribute('aria-pressed', String(item === button))); track('mode_switch', { mode: mine ? 'myspace' : 'explore' }); if (mine) render(); }));
}
