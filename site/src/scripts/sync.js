import { KEYS, set, updateBadges } from './library.js';
import { getSupabase, supabaseEnabled } from './supabase.js';
import { MYSPACE_KEY, mergeColumns } from '../lib/myspace-schema.mjs';

const kinds = ['history', 'favorites', 'watchLater', 'following', 'channelSeen'];
const keyForKind = Object.fromEntries(kinds.filter(kind => kind !== 'channelSeen').map(kind => [kind, KEYS[kind]]));
let syncDisabled = false;
let syncing = false;
let warned = false;
let pushTimer;
const synced = new Map(kinds.map(kind => [kind, new Set()]));
const remoteUpdated = new Map(kinds.map(kind => [kind, new Map()]));

const warn = error => {
  if (!warned) console.warn('fewgood. cloud sync is unavailable; using local storage only.', error);
  warned = true;
  syncDisabled = true;
};
const parse = key => { try { const data = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(data) ? data : []; } catch { return []; } };
const timestamp = (item, kind) => Number(kind === 'history' ? item.watchedAt : kind === 'channelSeen' ? item.ts : Math.max(Number(item.saved_at) || 0, Number(item.seen_at) || 0)) || 0;
const localEntries = kind => {
  if (kind !== 'channelSeen') return parse(keyForKind[kind]).filter(item => item?.id).map(item => ({ item_id: String(item.id), snapshot: item, ts: timestamp(item, kind) }));
  try {
    const value = JSON.parse(localStorage.getItem(KEYS.channelSeen) || '{}');
    return Object.entries(value && typeof value === 'object' ? value : {}).map(([item_id, ts]) => ({ item_id, snapshot: { ts: Number(ts) || 0 }, ts: Number(ts) || 0 }));
  } catch { return []; }
};
const writeEntries = (kind, entries) => {
  if (kind === 'channelSeen') {
    localStorage.setItem(KEYS.channelSeen, JSON.stringify(Object.fromEntries(entries.map(entry => [entry.item_id, Number(entry.snapshot?.ts) || 0]))));
    document.dispatchEvent(new CustomEvent('youtuber:library-change', { detail: { key: KEYS.channelSeen } }));
    return;
  }
  set(keyForKind[kind], entries.map(entry => entry.snapshot));
};
const eventKind = key => Object.entries(keyForKind).find(([, value]) => value === key)?.[0] || (key === KEYS.channelSeen ? 'channelSeen' : null);

async function pushKind(user, kind) {
  if (syncDisabled || !user) return;
  const db = getSupabase();
  const entries = localEntries(kind);
  const present = new Set(entries.map(entry => entry.item_id));
  const previous = synced.get(kind) || new Set();
  const remote = remoteUpdated.get(kind) || new Map();
  const rows = [
    ...entries.filter(entry => !remote.has(entry.item_id) || entry.ts > remote.get(entry.item_id)).map(entry => ({ user_id: user.id, kind, item_id: entry.item_id, snapshot: entry.snapshot, deleted: false })),
    ...[...previous].filter(id => !present.has(id)).map(item_id => ({ user_id: user.id, kind, item_id, snapshot: {}, deleted: true })),
  ];
  if (!rows.length) return;
  const { error } = await db.from('library_items').upsert(rows, { onConflict: 'user_id,kind,item_id' });
  if (error) return warn(error);
  synced.set(kind, present);
  for (const row of rows) remote.set(row.item_id, Date.now());
}

function readLocalColumns() {
  try {
    const state = JSON.parse(localStorage.getItem(MYSPACE_KEY) || 'null');
    return state && Array.isArray(state.columns) ? state.columns.map(column => ({ ...column })) : null;
  } catch { return null; }
}

async function syncMySpaceColumns(user) {
  // Merge 我的空间 columns only when a fitting cloud table already exists.
  // No DDL here: if user_topics is absent we keep localStorage-only behavior.
  if (!user || syncDisabled) return;
  const db = getSupabase();
  const local = readLocalColumns();
  const { data: rows, error } = await db.from('user_topics')
    .select('column_id,source,kind,topic_id,label,enabled,position')
    .eq('user_id', user.id).order('position');
  if (error) return; // table not available in this environment
  const cloud = (rows || []).map(row => ({ id: row.column_id, source: row.source, kind: row.kind, topic_id: row.topic_id, label: row.label, enabled: row.enabled }));
  if (!local && !cloud.length) return;
  const merged = mergeColumns(local, cloud);
  const payload = merged.map((column, index) => ({ user_id: user.id, column_id: column.id, source: column.source, kind: column.kind, topic_id: column.topic_id || null, label: column.label || null, enabled: column.enabled, position: index }));
  const { error: upsertError } = await db.from('user_topics').upsert(payload, { onConflict: 'user_id,column_id' });
  if (upsertError) return warn(upsertError);
  localStorage.removeItem(MYSPACE_KEY);
  document.dispatchEvent(new CustomEvent('fewgood:myspace-merged'));
}

async function pullAndMerge(user) {
  const db = getSupabase();
  const { data: rows, error } = await db.from('library_items').select('kind,item_id,snapshot,updated_at,deleted').eq('user_id', user.id);
  if (error) return warn(error);
  for (const kind of kinds) {
    const local = new Map(localEntries(kind).map(entry => [entry.item_id, entry]));
    const cloud = (rows || []).filter(row => row.kind === kind);
    const remote = new Map();
    for (const row of cloud) {
      remote.set(row.item_id, Date.parse(row.updated_at) || 0);
      if (row.deleted) { local.delete(row.item_id); continue; }
      const candidate = { item_id: row.item_id, snapshot: row.snapshot || {}, ts: Date.parse(row.updated_at) || 0 };
      const existing = local.get(row.item_id);
      if (!existing || candidate.ts >= existing.ts) local.set(row.item_id, candidate);
    }
    writeEntries(kind, [...local.values()]);
    synced.set(kind, new Set([...cloud].filter(row => !row.deleted).map(row => row.item_id)));
    remoteUpdated.set(kind, remote);
    // Cloud rows absent for local entries, and local entries newer than cloud rows, are uploaded next.
    await pushKind(user, kind);
    if (syncDisabled) return;
  }
  updateBadges();
}

export function startSync() {
  if (!supabaseEnabled || syncDisabled) return;
  const db = getSupabase();
  const begin = async session => {
    if (!session?.user || syncDisabled) return;
    syncing = true;
    try { await pullAndMerge(session.user); await syncMySpaceColumns(session.user); } catch (error) { warn(error); } finally { syncing = false; }
  };
  db.auth.getSession().then(({ data, error }) => { if (error) warn(error); else begin(data.session); }).catch(warn);
  db.auth.onAuthStateChange((event, session) => { if (event === 'INITIAL_SESSION' || event === 'SIGNED_IN') begin(session); });
  document.addEventListener('youtuber:library-change', event => {
    const kind = eventKind(event.detail?.key);
    if (!kind || syncing || syncDisabled) return;
    clearTimeout(pushTimer);
    pushTimer = setTimeout(async () => {
      try { const { data } = await db.auth.getSession(); await pushKind(data.session?.user, kind); } catch (error) { warn(error); }
    }, 500);
  });
}
