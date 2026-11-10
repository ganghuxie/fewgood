import { getSupabase, supabaseEnabled } from './supabase.js';
import subtopicData from '../data/subtopics.json';
import aliasData from '../../../config/topic-aliases.json';

const featuredTopics = (subtopicData.categories || [])
  .filter(category => category.id !== 'trending')
  .flatMap(category => category.subtopics || []);
const normalizedName = value => String(value || '').normalize('NFC').trim().toLocaleLowerCase();
const featuredByName = new Map();
for (const topic of featuredTopics) {
  featuredByName.set(normalizedName(topic.id), topic);
  featuredByName.set(normalizedName(topic.name_zh), topic);
}
for (const [alias, canonicalName] of Object.entries(aliasData.aliases || {})) {
  const topic = featuredByName.get(normalizedName(canonicalName));
  if (topic) featuredByName.set(normalizedName(alias), topic);
}

/** Resolve a featured id, Chinese name, or configured alias to its stable static id. */
export function resolveFeaturedTopic(value) {
  return featuredByName.get(normalizedName(value)) || null;
}

export const mockTopicsEnabled = () => new URLSearchParams(location.search).get('mockTopics') === '1' || localStorage.getItem('fewgood:mockTopics') === '1' || String(import.meta.env.PUBLIC_V2_TOPICS_MOCK || '').toLowerCase() === 'true';
export async function topicSession() {
  if (mockTopicsEnabled()) return { user: { id: 'fixture-user', email: 'mock@fewgood.local' }, mock: true };
  const db = getSupabase(); if (!db) return null;
  const { data } = await db.auth.getSession(); return data.session || null;
}
async function rpc(name, args) {
  const db = getSupabase(); if (!db) throw new Error('请先登录后再管理栏目。');
  const { data, error } = await db.rpc(name, args); if (error) throw error; return data;
}
export const requestTopic = name => rpc('request_topic', { p_name: name });
export const renameUserTopic = (userTopicId, name) => rpc('rename_user_topic', { p_user_topic_id: userTopicId, p_display_name: name });
export const moveUserTopic = (userTopicId, position) => rpc('move_user_topic', { p_user_topic_id: userTopicId, p_sort_order: position });
export const removeUserTopic = userTopicId => rpc('remove_user_topic', { p_user_topic_id: userTopicId });

/** Match ytrec.topics.slug so published static pages line up with canonical names. */
export function topicSlug(value) {
  const special = { 'C++': 'c-plus-plus', 'C#': 'c-sharp' };
  if (special[value]) return special[value];
  const ascii = String(value || '').normalize('NFKD').replace(/[^\x00-\x7F]/g, '').toLowerCase();
  return ascii.replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || 'topic';
}

async function publicQueue() {
  const url = import.meta.env.PUBLIC_SUPABASE_URL;
  const key = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return [];
  // Use the anon role explicitly: the queue view is granted to anon, not authenticated.
  const response = await fetch(`${url}/rest/v1/public_topic_worker_queue?select=topic_id,canonical_name`, {
    headers: { apikey: key, Authorization: `Bearer ${key}`, Accept: 'application/json' },
  });
  if (!response.ok) throw new Error('无法读取公开主题队列。');
  const rows = await response.json();
  return Array.isArray(rows) ? rows : [];
}

export async function listMyTopics() {
  const db = getSupabase();
  if (!db) return [];
  const { data, error } = await db.from('user_topics').select('id,topic_id,display_name,sort_order,active').eq('active', true).order('sort_order');
  if (error) throw error;
  const names = new Map((await publicQueue()).map(row => [row.topic_id, row.canonical_name]));
  return (data || []).map(row => {
    const canonical = names.get(row.topic_id) || row.display_name || '';
    const featured = resolveFeaturedTopic(canonical);
    return {
      user_topic_id: row.id,
      topic_uuid: row.topic_id,
      // topicSlug intentionally collapses Chinese input to "topic".  Featured
      // topics have stable published ids, so resolve them before falling back.
      topic_id: featured?.id || topicSlug(canonical),
      canonical_name: canonical || '主题',
      display_name: row.display_name,
      sort_order: row.sort_order,
    };
  });
}
export { supabaseEnabled };
