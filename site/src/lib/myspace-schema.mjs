export const MYSPACE_KEY = 'youtuber:myspace:v1';
export const MYSPACE_VERSION = 1;
export const MAX_ACTIVE_COLUMNS = 5;
export const DEFAULT_COLUMNS = ['trending', 'ai', 'podcast', 'music', 'community:people'];

export function defaultState() {
  return { version: MYSPACE_VERSION, columns: DEFAULT_COLUMNS.map(id => ({ id, source: id, enabled: true })) };
}

export function validateState(value, sources, maxActive = MAX_ACTIVE_COLUMNS) {
  if (!value || value.version !== MYSPACE_VERSION || !Array.isArray(value.columns) || !Array.isArray(sources)) return null;
  const allowed = new Set(sources.map(source => source.id));
  const seen = new Set();
  const columns = [];
  for (const column of value.columns) {
    if (!column || typeof column.id !== 'string' || typeof column.source !== 'string' || typeof column.enabled !== 'boolean') return null;
    if (!allowed.has(column.source) || seen.has(column.id) || column.id !== column.source) return null;
    seen.add(column.id);
    columns.push({ id: column.id, source: column.source, enabled: column.enabled });
  }
  if (!columns.length || columns.filter(column => column.enabled).length > maxActive) return null;
  return { version: MYSPACE_VERSION, columns };
}
