const PREFIX = 'youtuber:';
import { track } from './analytics.js';
export const KEYS = {
  favorites: `${PREFIX}favorites`,
  watchLater: `${PREFIX}watchLater`,
  history: `${PREFIX}history`,
  following: `${PREFIX}following`,
  channelSeen: `${PREFIX}channelSeen`,
};
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
  const result = {
    id,
    title,
    thumbnail: first(source.thumbnail, source.thumb, catalog.thumbnail, catalog.thumb, id ? `https://i.ytimg.com/vi/${id}/maxresdefault.jpg` : ''),
    channelId,
    channel: channelName,
    avatar: first(source.avatar, source.channelAvatar, channelData.thumbnail, channelData.avatar, ''),
    duration: Number(first(source.duration, source.duration_seconds, catalog.duration, catalog.duration_seconds, 0)) || 0,
    views: Number(first(source.views, source.view_count, catalog.views, catalog.view_count, 0)) || 0,
    published_at: first(source.published_at, source.publishedAt, catalog.published_at, catalog.publishedAt, ''),
    saved_at: first(source.saved_at, source.savedAt, Date.now()),
    ...(source.watchedAt ? { watchedAt: source.watchedAt } : {}),
  };
  // Watch-later unseen: newly added items are unseen; preserve seen_at when present.
  if (source.seen_at !== undefined) result.seen_at = source.seen_at;
  else if (source.unseen === false) result.seen_at = source.seen_at || Date.now();
  return result;
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
export function remove(key, id) {
  set(key, get(key).filter(item => item.id !== id));
  if (key === KEYS.favorites) track('favorite_remove', { video_id: id });
  if (key === KEYS.watchLater) track('watch_later_remove', { video_id: id });
}
export function toggleVideo(key, snapshot) {
  const item = video(snapshot);
  const present = has(key, item.id);
  if (present) remove(key, item.id);
  else {
    // Newly added watch-later items are unseen (no seen_at).
    if (key === KEYS.watchLater) delete item.seen_at;
    set(key, [item, ...get(key)]);
    if (key === KEYS.favorites) track('favorite_add', { video_id: item.id });
    if (key === KEYS.watchLater) track('watch_later_add', { video_id: item.id });
  }
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
  track(present ? 'unfollow' : 'follow', { channel_id: item.id });
  return !present;
}
export const follow = toggleChannel;
export function getChannelSeen(id) {
  try {
    const seen = JSON.parse(localStorage.getItem(KEYS.channelSeen) || '{}');
    return seen && typeof seen === 'object' ? seen[id] || 0 : 0;
  } catch { return 0; }
}
export function markChannelSeen(id, at = Date.now()) {
  if (!id) return;
  try {
    const seen = JSON.parse(localStorage.getItem(KEYS.channelSeen) || '{}');
    seen[id] = Math.max(Number(seen[id]) || 0, typeof at === 'number' ? at : Date.parse(at) || Date.now());
    localStorage.setItem(KEYS.channelSeen, JSON.stringify(seen));
    document.dispatchEvent(new CustomEvent('youtuber:library-change', { detail: { key: KEYS.channelSeen } }));
  } catch { /* private browsing */ }
}
export function channelHasNew(channelId, latestPublishedAt) {
  return has(KEYS.following, channelId) && !!latestPublishedAt && Date.parse(latestPublishedAt) > Number(getChannelSeen(channelId) || 0);
}
export function isWatchLaterUnseen(item) {
  return !item?.seen_at;
}
export function unseenWatchLaterCount() {
  return get(KEYS.watchLater).filter(isWatchLaterUnseen).length;
}
export function markWatchLaterSeen(id) {
  if (!id) return false;
  const items = get(KEYS.watchLater);
  let changed = false;
  const next = items.map(item => {
    if (item.id !== id || item.seen_at) return item;
    changed = true;
    return { ...item, seen_at: Date.now() };
  });
  if (changed) set(KEYS.watchLater, next);
  return changed;
}
export function updateBadges() {
  document.querySelectorAll('[data-library-count]').forEach(node => {
    const kind = node.dataset.libraryCount;
    // Only 稍后再看 shows a badge, and only for unseen items.
    if (kind !== 'watchLater') {
      node.textContent = '';
      node.hidden = true;
      return;
    }
    const count = unseenWatchLaterCount();
    node.textContent = count || '';
    node.hidden = !count;
  });
}
