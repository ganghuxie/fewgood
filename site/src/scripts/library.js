const PREFIX = 'youtuber:';
export const KEYS = { favorites: `${PREFIX}favorites`, watchLater: `${PREFIX}watchLater`, history: `${PREFIX}history` };

export function get(key) {
  try { const value = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(value) ? value : []; } catch { return []; }
}
export function set(key, value) { localStorage.setItem(key, JSON.stringify(value)); updateBadges(); }
export function ids(key) { return get(key).map(item => typeof item === 'string' ? item : item.id); }
export function has(key, id) { return ids(key).includes(id); }
export function toggle(key, id) {
  const value = get(key); const next = has(key, id) ? value.filter(item => (typeof item === 'string' ? item : item.id) !== id) : [{ id, savedAt: Date.now() }, ...value];
  set(key, next); return has(key, id);
}
export function addHistory(id) {
  const rest = get(KEYS.history).filter(item => (typeof item === 'string' ? item : item.id) !== id);
  set(KEYS.history, [{ id, watchedAt: Date.now() }, ...rest].slice(0, 100));
}
export function updateBadges() { document.querySelectorAll('[data-library-count]').forEach(node => { const count = ids(KEYS[node.dataset.libraryCount]).length; node.textContent = count || ''; node.hidden = !count; }); }
