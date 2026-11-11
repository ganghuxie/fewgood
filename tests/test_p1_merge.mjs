import assert from 'node:assert/strict';
import { mergeColumns } from '../site/src/lib/myspace-schema.mjs';

// 1. local empty, cloud has columns -> result = cloud
assert.deepEqual(mergeColumns([], [{ id: 'topic:ai', label: '人工智能', enabled: true }]), [{ id: 'topic:ai', label: '人工智能', enabled: true }]);

// 2. cloud empty, local has columns -> result = local
const local = [{ id: 'topic:math', label: '数学', enabled: true }, { id: 'topic:ai', label: '人工智能', enabled: true }];
assert.deepEqual(mergeColumns(local, []), local);

// 3. same topic/column id on both -> local display_name/order wins
const cloud = [{ id: 'topic:ai', label: '云端的旧名字', enabled: false }, { id: 'topic:cpp', label: 'C++', enabled: true }];
const merged = mergeColumns(local, cloud);
assert.deepEqual(merged, [
  { id: 'topic:math', label: '数学', enabled: true },
  { id: 'topic:ai', label: '人工智能', enabled: true },
  { id: 'topic:cpp', label: 'C++', enabled: true },
]);
assert.equal(merged[1].label, '人工智能');
assert.equal(merged.find(column => column.id === 'topic:ai').enabled, true);

console.log('merge cases ok');
