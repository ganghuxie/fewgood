import assert from 'node:assert/strict';
import { defaultState, validateState, mergeColumns, topicColumnId } from '../site/src/lib/myspace-schema.mjs';
import { templateToColumns, templateColumnsReady } from '../site/src/lib/template-columns.mjs';

const sources = [{ id: 'picks' }, { id: 'trending' }, { id: 'ai' }, { id: 'podcast' }, { id: 'music' }, { id: 'community:people' }, { id: 'community:newest' }];
const topics = [{ id: 'ai' }, { id: 'math' }];

assert.equal(validateState(defaultState(), sources).columns.length, 5);
assert.equal(validateState({ version: 3, columns: [] }, sources), null);
assert.equal(validateState({ version: 1, columns: [{ id: 'bad', source: 'bad', enabled: true }] }, sources), null);
assert.equal(validateState({ version: 1, columns: Array.from({ length: 6 }, (_, i) => ({ id: String(i), source: 'trending', enabled: true })) }, sources), null);

// v1 stays backward compatible and is migrated to v2.
const migrated = validateState({ version: 1, columns: [{ id: 'trending', source: 'trending', enabled: true }] }, sources);
assert.equal(migrated.version, 2);
assert.equal(migrated.columns[0].kind, 'feed');

// Topic columns validate only with a known topic.
const topicColumn = { id: topicColumnId('ai'), source: 'ai', kind: 'topic', topic_id: 'ai', label: '人工智能', enabled: true };
const withTopic = validateState({ version: 2, columns: [topicColumn] }, sources, topics);
assert.equal(withTopic.columns[0].label, '人工智能');
assert.equal(validateState({ version: 2, columns: [topicColumn] }, sources, []), null);
assert.equal(validateState({ version: 2, columns: [{ id: topicColumnId('ai'), source: 'ai', kind: 'topic', topic_id: 'ai', enabled: true }] }, sources, topics).columns.length, 1);

// Merge semantics.
assert.deepEqual(mergeColumns([], [{ id: 'a', label: 'Cloud', enabled: true }]), [{ id: 'a', label: 'Cloud', enabled: true }]);
assert.deepEqual(mergeColumns([{ id: 'a', label: 'Local', enabled: true }], []), [{ id: 'a', label: 'Local', enabled: true }]);
assert.deepEqual(mergeColumns([{ id: 'a', label: 'Local', enabled: true }, { id: 'b', label: 'LocalB', enabled: true }], [{ id: 'a', label: 'Cloud', enabled: false }, { id: 'c', label: 'CloudC', enabled: true }]), [
  { id: 'a', label: 'Local', enabled: true },
  { id: 'b', label: 'LocalB', enabled: true },
  { id: 'c', label: 'CloudC', enabled: true },
]);

// Templates can mix live feed columns with topic columns without collapsing the ai id collision.
const templateSources = [{ id: 'ai', section: 'ai' }, { id: 'trending', section: 'trending' }];
const templateTopics = [{ id: 'ai', name_zh: '人工智能', video_ids: Array.from({ length: 6 }, (_, i) => `t${i}`) }];
const mixedTemplate = { columns: [{ kind: 'feed', source: 'ai' }, { kind: 'topic', topic_id: 'ai' }] };
const applied = templateToColumns(mixedTemplate, templateSources, templateTopics);
assert.deepEqual(applied.map(column => [column.kind, column.id, column.source, column.label]), [
  ['feed', 'ai', 'ai', null],
  ['topic', 'topic:ai', 'ai', '人工智能'],
]);
assert.equal(validateState({ version: 2, columns: applied }, sources, topics).columns.length, 2);

// Readiness requires six topic videos and six catalog videos in the feed section.
const aiCatalog = Array.from({ length: 6 }, (_, i) => ({ id: `v${i}`, sections: ['ai'] }));
assert.equal(templateColumnsReady(mixedTemplate, templateSources, templateTopics, aiCatalog), true);
assert.equal(templateColumnsReady(mixedTemplate, templateSources, templateTopics, aiCatalog.slice(0, 5)), false);
assert.equal(templateColumnsReady({ columns: [{ kind: 'topic', topic_id: 'ai' }] }, templateSources, [{ id: 'ai', video_ids: ['1', '2', '3', '4', '5'] }], aiCatalog), false);

// Legacy topic_ids templates still apply as topic columns.
assert.deepEqual(templateToColumns({ topic_ids: ['math'] }, templateSources, [...templateTopics, { id: 'math', name_zh: '数学' }]).map(column => [column.kind, column.id]), [
  ['topic', 'topic:math'],
]);

console.log('myspace schema ok');
