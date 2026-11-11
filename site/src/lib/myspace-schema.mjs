export const MYSPACE_KEY = 'youtuber:myspace:v1';
export const MYSPACE_VERSION = 2;
export const MAX_ACTIVE_COLUMNS = 5;
export const DEFAULT_COLUMNS = ['picks', 'trending', 'ai', 'podcast', 'music'];

export const topicColumnId = topicId => `topic:${topicId}`;
export const isTopicColumn = column => column?.kind === 'topic' || Boolean(column?.topic_id);

export function defaultState() {
  return {
    version: MYSPACE_VERSION,
    columns: DEFAULT_COLUMNS.map(id => ({ id, source: id, kind: 'feed', topic_id: null, label: null, enabled: true })),
  };
}

function normalizeColumn(column, sources, topics) {
  if (!column || typeof column.id !== 'string' || typeof column.source !== 'string' || typeof column.enabled !== 'boolean') return null;
  const sourceIds = new Set(sources.map(source => source.id));
  const topicIds = new Set(topics.map(topic => topic.id));
  const wantsTopic = column.kind === 'topic' || column.topic_id;
  if (wantsTopic) {
    const topicId = column.topic_id || column.source;
    if (!topicIds.has(topicId)) return null;
    if (column.source !== topicId) return null;
    if (column.id !== topicColumnId(topicId)) return null;
    return {
      id: column.id,
      source: topicId,
      kind: 'topic',
      topic_id: topicId,
      label: typeof column.label === 'string' ? column.label : null,
      enabled: column.enabled,
    };
  }
  if (!sourceIds.has(column.source)) return null;
  return {
    id: column.id,
    source: column.source,
    kind: 'feed',
    topic_id: null,
    label: null,
    enabled: column.enabled,
  };
}

export function validateState(value, sources, topics = []) {
  if (!value || !Array.isArray(value.columns) || !Array.isArray(sources)) return null;
  if (value.version !== 1 && value.version !== MYSPACE_VERSION) return null;
  const seen = new Set();
  const columns = [];
  for (const column of value.columns) {
    let normalized;
    if (value.version === 1) {
      // v1 states force id === source and only knew the old feeds.
      if (!column || typeof column.id !== 'string' || typeof column.source !== 'string' || typeof column.enabled !== 'boolean') return null;
      if (column.id !== column.source) return null;
      normalized = normalizeColumn({ ...column, kind: 'feed' }, sources, topics);
    } else {
      normalized = normalizeColumn(column, sources, topics);
    }
    if (!normalized || seen.has(normalized.id)) return null;
    seen.add(normalized.id);
    columns.push(normalized);
  }
  if (!columns.length || columns.filter(column => column.enabled).length > MAX_ACTIVE_COLUMNS) return null;
  return { version: MYSPACE_VERSION, columns };
}

export function mergeColumns(local, cloud) {
  if (!Array.isArray(local) || !local.length) return Array.isArray(cloud) ? cloud.map(column => ({ ...column })) : [];
  if (!Array.isArray(cloud) || !cloud.length) return local.map(column => ({ ...column }));
  const merged = [];
  const seen = new Set();
  for (const column of local) {
    if (!column || seen.has(column.id)) continue;
    seen.add(column.id);
    merged.push({ ...column });
  }
  for (const column of cloud) {
    if (!column || seen.has(column.id)) continue;
    seen.add(column.id);
    merged.push({ ...column });
  }
  return merged;
}
