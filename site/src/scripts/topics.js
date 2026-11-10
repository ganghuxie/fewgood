import { getSupabase, supabaseEnabled } from './supabase.js';

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
export { supabaseEnabled };
