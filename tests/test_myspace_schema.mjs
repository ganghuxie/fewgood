import assert from 'node:assert/strict';
import { defaultState, validateState } from '../site/src/lib/myspace-schema.mjs';
const sources = [{ id: 'trending' }, { id: 'ai' }, { id: 'podcast' }, { id: 'music' }, { id: 'community:people' }, { id: 'community:newest' }];
assert.equal(validateState(defaultState(), sources).columns.length, 5);
assert.equal(validateState({ version: 2, columns: [] }, sources), null);
assert.equal(validateState({ version: 1, columns: [{ id: 'bad', source: 'bad', enabled: true }] }, sources), null);
assert.equal(validateState({ version: 1, columns: Array.from({ length: 6 }, (_, i) => ({ id: String(i), source: 'trending', enabled: true })) }, sources), null);
