import assert from 'node:assert/strict';
import { defaultState, validateState, mergeColumns, topicColumnId } from '../site/src/lib/myspace-schema.mjs';

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

console.log('myspace schema ok');
