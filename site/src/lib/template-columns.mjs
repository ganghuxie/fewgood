import { topicColumnId } from './myspace-schema.mjs';

export const templateColumnDefinitions = template => (Array.isArray(template?.columns)
  ? template.columns
  : (Array.isArray(template?.topic_ids) ? template.topic_ids.map(id => ({ kind: 'topic', id })) : []));

const columnKind = column => (column?.kind === 'topic' || column?.kind === 'feed' ? column.kind : (column?.topic_id ? 'topic' : 'feed'));
const columnId = column => (columnKind(column) === 'topic'
  ? (column?.topic_id || column?.source || column?.id)
  : (column?.source || column?.id));

export function templateToColumns(template, sources = [], topics = []) {
  const sourceById = new Map(sources.map(source => [source.id, source]));
  const topicById = new Map(topics.map(topic => [topic.id, topic]));
  const columns = [];
  const seen = new Set();
  for (const definition of templateColumnDefinitions(template)) {
    const kind = columnKind(definition);
    const id = columnId(definition);
    if (kind === 'topic') {
      if (!topicById.has(id)) continue;
      const columnIdValue = topicColumnId(id);
      if (seen.has(columnIdValue)) continue;
      seen.add(columnIdValue);
      columns.push({ id: columnIdValue, source: id, kind: 'topic', topic_id: id, label: topicById.get(id)?.name_zh || id, enabled: true });
      continue;
    }
    const source = sourceById.get(id);
    if (!source || seen.has(source.id)) continue;
    seen.add(source.id);
    columns.push({ id: source.id, source: source.id, kind: 'feed', topic_id: null, label: null, enabled: true });
  }
  return columns;
}

export function templateColumnsReady(template, sources = [], topics = [], catalog = []) {
  const definitions = templateColumnDefinitions(template);
  if (!definitions.length) return false;
  const sourceById = new Map(sources.map(source => [source.id, source]));
  const topicById = new Map(topics.map(topic => [topic.id, topic]));
  const videos = Array.isArray(catalog) ? catalog : [];
  return definitions.every(definition => {
    const kind = columnKind(definition);
    const id = columnId(definition);
    if (kind === 'topic') return (topicById.get(id)?.video_ids?.length || 0) >= 6;
    const source = sourceById.get(id);
    if (!source) return false;
    return videos.filter(video => Array.isArray(video.sections) && video.sections.includes(source.section)).length >= 6;
  });
}
