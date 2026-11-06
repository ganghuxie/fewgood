const PREFIX = 'youtuber:';
export const KEYS = { favorites: `${PREFIX}favorites`, watchLater: `${PREFIX}watchLater`, history: `${PREFIX}history`, following: `${PREFIX}following` };
const raw = key => { try { const value = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(value) ? value : []; } catch { return []; } };
const first = (...values) => values.find(value => value !== undefined && value !== null && value !== '');
const incompleteTitle = (title, id) => !title || title === id;
const video = (item, catalog = {}, channels = {}) => {
  const source = typeof item === 'string' ? { id: item } : (item || {});
  const id = source.id || source.videoId;
  const channelId = first(source.channelId, source.channel_id, catalog.channelId, catalog.channel_id);
  const channelName = first(
    source.channel && source.channel !== id ? source.channel : undefined,
    catalog.channel, catalog.channelTitle, ''
  );
  const channelData = channels[channelId] || {};
  const title = first(
    !incompleteTitle(source.title, id) ? source.title : undefined,
    catalog.title, id
  );
  return {
    id,
    title,
    thumbnail: first(source.thumbnail, source.thumb, catalog.thumbnail, catalog.thumb, id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : ''),
    channelId,
    channel: channelName,
    avatar: first(source.avatar, source.channelAvatar, channelData.thumbnail, channelData.avatar, ''),
    duration: Number(first(source.duration, source.duration_seconds, catalog.duration, catalog.duration_seconds, 0)) || 0,
    views: Number(first(source.views, source.view_count, catalog.views, catalog.view_count, 0)) || 0,
    published_at: first(source.published_at, source.publishedAt, catalog.published_at, catalog.publishedAt, ''),
    saved_at: first(source.saved_at, source.savedAt, Date.now()),
    ...(source.watchedAt ? { watchedAt: source.watchedAt } : {}),
  };
};
const channel = (item, source = {}) => {
  const id = typeof item === 'string' ? item : first(item?.id, item?.channelId);
  const title = first(
    typeof item === 'object' && item?.title && item.title !== id ? item.title : undefined,
    source.title, id
  );
  return {
    id,
    title,
    thumbnail: first(item?.thumbnail, item?.avatar, source.thumbnail, source.avatar, ''),
    saved_at: first(item?.saved_at, item?.savedAt, Date.now()),
  };
};
export function migrate(key, catalog = [], channels = []) {
  const entries = raw(key);
  const catalogMap = new Map((Array.isArray(catalog) ? catalog : catalog.videos || []).map(item => [item.id, item]));
  const channelMap = Object.fromEntries((Array.isArray(channels) ? channels : channels.channels || []).map(item => [item.id, item]));
  const migrated = entries.map(item => key === KEYS.following
    ? channel(item, channelMap[item?.id || item] || {})
    : video(item, catalogMap.get(item?.id || item) || {}, channelMap));
  localStorage.setItem(key, JSON.stringify(migrated));
  return migrated;
}
export function get(key) {
  return raw(key).map(item => key === KEYS.following ? channel(item) : video(item));
}
export function list(key) { return get(key); }
export function set(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
  updateBadges();
  document.dispatchEvent(new CustomEvent('youtuber:library-change', { detail: { key } }));
}
export function ids(key) { return get(key).map(item => item.id).filter(Boolean); }
export function has(key, id) { return ids(key).includes(id); }
export function remove(key, id) { set(key, get(key).filter(item => item.id !== id)); }
export function toggleVideo(key, snapshot) {
  const item = video(snapshot);
  const present = has(key, item.id);
  if (present) remove(key, item.id);
  else set(key, [item, ...get(key)]);
  return !present;
}
export function toggle(key, idOrSnapshot) {
  return typeof idOrSnapshot === 'object' ? toggleVideo(key, idOrSnapshot) : toggleVideo(key, { id: idOrSnapshot });
}
export function addHistory(snapshot) {
  const item = { ...video(snapshot), watchedAt: Date.now() };
  set(KEYS.history, [item, ...get(KEYS.history).filter(existing => existing.id !== item.id)].slice(0, 100));
}
export function toggleChannel(snapshot) {
  const item = channel(snapshot);
  const present = has(KEYS.following, item.id);
  if (present) remove(KEYS.following, item.id);
  else set(KEYS.following, [item, ...get(KEYS.following)]);
  return !present;
}
export const follow = toggleChannel;
export function updateBadges() {
  document.querySelectorAll('[data-library-count]').forEach(node => {
    const count = ids(KEYS[node.dataset.libraryCount]).length;
    node.textContent = count || '';
    node.hidden = !count;
  });
}
