import { track } from './analytics.js';
import { fetchPublicTopic } from '../lib/topics.mjs';
import { getSupabase } from './supabase.js';
import { mockTopicsEnabled, topicSession, requestTopic, removeUserTopic, listMyTopics, resolveFeaturedTopic } from './topics.js';
import subtopicData from '../data/subtopics.json';

const FEATURED_KEY = 'fewgood:featured-subtopics';
const MAX_TOPICS = 5;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const duration = seconds => `${Math.floor((Number(seconds) || 0) / 60)}:${String((Number(seconds) || 0) % 60).padStart(2, '0')}`;
const categories = (subtopicData.categories || []).filter(category => category.id !== 'trending');
const featured = categories.flatMap(category => category.subtopics || []);
const byId = new Map(featured.map(topic => [topic.id, topic]));
const localSelected = () => { try { return [...new Set(JSON.parse(localStorage.getItem(FEATURED_KEY) || '[]').filter(id => byId.has(id)))].slice(0, MAX_TOPICS); } catch { return []; } };
const saveSelected = ids => { try { localStorage.setItem(FEATURED_KEY, JSON.stringify(ids.filter(id => byId.has(id)))); } catch {} };
const avatar = video => video.channel_thumbnail
  ? `<img class="channel-avatar" src="${esc(video.channel_thumbnail)}" alt="">`
  : (() => { const name = video.channel_title || video.channel || '频道'; const letter = [...name.trim()][0] || '频'; let hash = 0; for (const ch of name) hash = (hash * 31 + ch.codePointAt(0)) >>> 0; const color = ['#d14b4b','#b06b2f','#8a6d1d','#4f8a3d','#357a8a','#5367a6','#7a5795'][hash % 7]; return `<span class="channel-avatar channel-avatar-letter" style="background-color:${color}" aria-hidden="true">${esc(letter)}</span>`; })();
function card(video, source, base) { const id = video.video_id || video.id; const channel = video.channel_title || video.channel || '频道'; return `<a class="video-card" href="${base}/v/${encodeURIComponent(id)}/?from=${encodeURIComponent(source)}"><div class="thumbnail"><img loading="lazy" src="https://i.ytimg.com/vi/${encodeURIComponent(id)}/hqdefault.jpg" alt=""><span class="duration">${duration(video.duration_seconds)}</span></div><div class="video-info">${avatar(video)}<div><h2 class="video-title">${esc(video.title)}</h2><p class="video-meta">${esc(channel)}</p></div></div></a>`; }

const shell = document.querySelector('[data-alpha-myspace]');
const explore = document.querySelector('[data-explore-view]');
const space = document.querySelector('[data-myspace-view]');
if (shell && explore && space) {
  const header = document.querySelector('.site-header'), chipbar = header?.querySelector('.chipbar');
  if (header && chipbar) { header.classList.add('alpha-video-header'); header.insertBefore(shell, chipbar); }
  shell.hidden = false;
  const base = (document.querySelector('main')?.dataset.base || '').replace(/\/$/, '');
  const cache = new Map(); let selected = localSelected(), serverTopics = [], loggedIn = false, mode = 'myspace', activeTab = 'all', notice = '';
  const selectedTopics = () => selected.filter(id => byId.has(id)).map(id => byId.get(id));
  const membership = id => serverTopics.find(topic => topic.topic_id === id);
  const say = text => { notice = text; const node = space.querySelector('[data-topic-message]'); if (node) node.textContent = text; };
  const loadVideos = async id => { if (cache.has(id)) return cache.get(id); const job = fetchPublicTopic(id, base).then(data => Array.isArray(data.videos) ? data.videos : []).catch(() => []); cache.set(id, job); const data = await job; cache.set(id, data); return data; };
  const prefetch = () => featured.forEach(topic => { loadVideos(topic.id); });
  const refreshMemberships = async () => { if (!loggedIn || mockTopicsEnabled()) return; serverTopics = await listMyTopics(); };
  const hydrateFromServer = async () => {
    if (!loggedIn || mockTopicsEnabled()) return;
    await refreshMemberships();
    selected = [...new Set([...selected, ...serverTopics.map(t => t.topic_id).filter(id => byId.has(id))])].slice(0, MAX_TOPICS);
    saveSelected(selected);
  };
  const renderVideos = async () => {
    const host = space.querySelector('[data-room-videos]'); if (!host) return;
    const topics = selectedTopics(); if (!topics.length) { host.innerHTML = ''; return; }
    const ids = activeTab === 'all' ? topics.map(t => t.id) : [activeTab];
    const ready = ids.every(id => Array.isArray(cache.get(id)));
    if (!ready) host.innerHTML = '<p class="myspace-loading">正在读取你的小房间…</p>';
    const groups = await Promise.all(ids.map(async id => [id, await loadVideos(id)])); if (!host.isConnected) return;
    if (activeTab === 'all') { const unique = new Map(); groups.flatMap(([, list]) => list).forEach(video => { const id = video.video_id || video.id; if (!unique.has(id)) unique.set(id, video); }); const all = [...unique.values()].sort((a,b) => Date.parse(b.published_at || 0) - Date.parse(a.published_at || 0)); host.innerHTML = all.length ? `<div class="video-grid">${all.map(video => card(video, 'topic:all', base)).join('')}</div>` : '<p class="myspace-loading">已选主题暂时还没有视频。</p>'; }
    else { const topic = byId.get(activeTab), list = groups[0]?.[1] || []; host.innerHTML = `<section class="myspace-column"><h2>${esc(topic?.name_zh || '小主题')}</h2>${list.length ? `<div class="video-grid">${list.map(video => card(video, `topic:${activeTab}`, base)).join('')}</div>` : '<p class="myspace-loading">该主题暂时还没有视频。</p>'}</section>`; }
  };
  const updateTabs = () => { if (!chipbar) return; const nav = chipbar.querySelector('nav'); if (!nav) return; if (mode === 'explore') { nav.innerHTML = chipbar.dataset.exploreTabs || ''; return; } const topics = selectedTopics(); if (!topics.some(t => t.id === activeTab)) activeTab = 'all'; nav.innerHTML = `<button type="button" data-room-tab="all" class="${activeTab === 'all' ? 'active' : ''}">全部</button>${topics.map(t => `<button type="button" data-room-tab="${esc(t.id)}" class="${activeTab === t.id ? 'active' : ''}">${esc(t.name_zh)}</button>`).join('')}`; nav.querySelectorAll('[data-room-tab]').forEach(button => button.addEventListener('click', () => { activeTab = button.dataset.roomTab; updateTabs(); renderVideos(); })); };
  const chips = () => categories.map(category => `<section class="topic-chip-group"><h3>${esc(category.name_zh)}</h3><div class="topic-chips">${category.subtopics.map(topic => { const on = selected.includes(topic.id), disabled = !on && selected.length >= MAX_TOPICS; return `<button type="button" class="topic-chip ${on ? 'selected' : ''}" data-featured-toggle="${esc(topic.id)}" aria-pressed="${on}" ${disabled ? 'disabled' : ''}>${on ? '✓ ' : ''}${esc(topic.name_zh)}</button>`; }).join('')}</div></section>`).join('');
  const login = () => document.querySelector('[data-auth-open]')?.click();
  const backgroundSync = (id, adding) => {
    if (mockTopicsEnabled() || !loggedIn) return;
    const job = adding ? requestTopic(byId.get(id).name_zh) : (membership(id) ? removeUserTopic(membership(id).user_topic_id) : Promise.resolve());
    Promise.resolve(job).then(async result => {
      if (result?.status && result.status !== 'ok') throw new Error(result.error || result.status);
      await refreshMemberships();
      if (adding && !selected.includes(id) && membership(id)) {
        await removeUserTopic(membership(id).user_topic_id);
        await refreshMemberships();
      }
    }).catch(() => say('已保存在此设备，稍后再同步。'));
  };
  const toggle = id => { if (!loggedIn && !mockTopicsEnabled()) { login(); return; } const on = selected.includes(id); if (!on && selected.length >= MAX_TOPICS) { say('最多可保留 5 个主题。'); return; } selected = on ? selected.filter(item => item !== id) : [...selected, id]; saveSelected(selected); notice = ''; render(); backgroundSync(id, !on); };
  const bindCreate = host => { host.querySelector('[data-topic-login]')?.addEventListener('click', login); host.querySelector('[data-topic-create-open]')?.addEventListener('click', event => { event.currentTarget.hidden = true; host.querySelector('[data-topic-create]').hidden = false; host.querySelector('[name="topic"]')?.focus(); }); host.querySelector('[data-topic-create]')?.addEventListener('submit', async event => { event.preventDefault(); const input = event.currentTarget.elements.topic, name = input.value.trim(); if (!name) return say('请输入主题名称。'); const match = resolveFeaturedTopic(name); if (match) { toggle(match.id); input.value = ''; return; } if (selected.length >= MAX_TOPICS) return say('最多可保留 5 个主题。'); try { if (mockTopicsEnabled()) return say('本地演示只支持精选小主题。'); const result = await requestTopic(name); if (result?.status && result.status !== 'ok') { const copy = { daily_cap:'今天的新建额度已用完。', invalid_input:'名称无效。', limit_reached:'最多可保留 5 个主题。', alias_conflict:'这个名称和已有主题冲突。' }; throw new Error(copy[result.error || result.status] || '创建失败，可稍后再试。'); } input.value = ''; await hydrateFromServer(); render(); say('已提交；主题公开后会显示处理状态。'); } catch (error) { say(error.message || '创建失败，可稍后再试。'); } }); };
  const renderEditor = () => { const dialog = space.querySelector('[data-myspace-editor]'); if (!dialog) return; const create = !loggedIn && !mockTopicsEnabled() ? '<button class="topic-login" type="button" data-topic-login>登录后选择小主题</button>' : '<button class="topic-create-link" type="button" data-topic-create-open>找不到？自己添加</button><form class="topic-create" data-topic-create hidden><input name="topic" maxlength="80" placeholder="新建公开主题" aria-label="主题名称"><button type="submit">新建</button></form>'; dialog.innerHTML = `<div class="myspace-editor-inner"><div class="myspace-editor-title"><h2>管理我的小主题</h2><button class="myspace-editor-close" type="button" aria-label="关闭">×</button></div><p class="myspace-editor-note">最多选择 ${MAX_TOPICS} 个。勾选后会立即保存到此设备并同步到账号。</p><div class="topic-chip-groups">${chips()}</div>${create}<p class="topic-message" data-topic-message aria-live="polite">${esc(notice)}</p></div>`; dialog.querySelector('.myspace-editor-close')?.addEventListener('click', () => dialog.close()); dialog.querySelectorAll('[data-featured-toggle]').forEach(button => button.addEventListener('click', () => toggle(button.dataset.featuredToggle))); bindCreate(dialog); prefetch(); };
  const render = () => { const empty = !selectedTopics().length, create = !loggedIn && !mockTopicsEnabled() ? '<button class="topic-login" type="button" data-topic-login>登录后选择小主题</button>' : '<button class="topic-create-link" type="button" data-topic-create-open>找不到？自己添加</button><form class="topic-create" data-topic-create hidden><input name="topic" maxlength="80" placeholder="新建公开主题" aria-label="主题名称"><button type="submit">新建</button></form>'; space.innerHTML = `<div class="myspace-heading"><div><h1>我的空间</h1><p>只看你勾选的小主题。</p></div><button class="myspace-manage" type="button" data-myspace-manage>管理我的小主题</button></div><dialog class="myspace-editor" data-myspace-editor aria-label="管理我的小主题"></dialog>${empty ? `<section class="myspace-empty"><h2>这里会成为你的小房间</h2><p>勾选小主题后，这里只会显示它们的视频。</p><div class="topic-chip-groups">${chips()}</div>${create}<p class="topic-message" data-topic-message aria-live="polite">${esc(notice)}</p></section>` : '<section class="myspace-columns" data-room-videos></section>'}`; space.querySelector('[data-myspace-manage]')?.addEventListener('click', () => { renderEditor(); space.querySelector('[data-myspace-editor]')?.showModal(); }); space.querySelectorAll('[data-featured-toggle]').forEach(button => button.addEventListener('click', () => toggle(button.dataset.featuredToggle))); bindCreate(space); updateTabs(); if (!empty) renderVideos(); prefetch(); };
  if (chipbar) { chipbar.querySelectorAll('a').forEach(link => link.setAttribute('data-explore-tab', '')); chipbar.dataset.exploreTabs = chipbar.querySelector('nav')?.innerHTML || ''; }
  const setMode = next => { mode = next; const mine = mode === 'myspace'; explore.hidden = mine; space.hidden = !mine; shell.querySelectorAll('[data-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.mode === mode))); updateTabs(); if (mine) render(); };
  shell.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => { if (button.dataset.mode !== mode) { setMode(button.dataset.mode); track('mode_switch', { mode }); } }));
  const syncAuth = async session => { loggedIn = Boolean(session); if (loggedIn && !mockTopicsEnabled()) try { await hydrateFromServer(); } catch {} render(); };
  getSupabase()?.auth.onAuthStateChange((event, session) => { if (event !== 'INITIAL_SESSION' && event !== 'TOKEN_REFRESHED') syncAuth(session); });
  topicSession().then(async session => { loggedIn = Boolean(session); if (mockTopicsEnabled() && new URLSearchParams(location.search).get('emptyTopics') !== '1' && !selected.length) selected = featured.slice(0, 2).map(topic => topic.id); if (loggedIn && !mockTopicsEnabled()) try { await hydrateFromServer(); } catch {} setMode(mockTopicsEnabled() ? 'myspace' : 'explore'); }).catch(() => setMode(mockTopicsEnabled() ? 'myspace' : 'explore'));
}
