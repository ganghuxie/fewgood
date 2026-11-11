import { MYSPACE_KEY, isTopicColumn } from '../lib/myspace-schema.mjs';
import { showPrompt, dismissPrompt } from './prompts.js';

const AFFINITY_KEY = 'fewgood:affinity';
const SUGGEST_THRESHOLD = 3;
const MUTE_DAYS = 90;
const DAY_MS = 24 * 60 * 60 * 1000;

let topicsPromise;

const read = () => {
  try {
    const value = JSON.parse(localStorage.getItem(AFFINITY_KEY) || 'null');
    if (!value || typeof value !== 'object') return { counts: {}, muted: {}, lastSuggestedAt: 0 };
    return {
      counts: value.counts && typeof value.counts === 'object' ? value.counts : {},
      muted: value.muted && typeof value.muted === 'object' ? value.muted : {},
      lastSuggestedAt: Number(value.lastSuggestedAt) || 0,
    };
  } catch { return { counts: {}, muted: {}, lastSuggestedAt: 0 }; }
};

const write = value => { try { localStorage.setItem(AFFINITY_KEY, JSON.stringify(value)); } catch { /* private browsing */ } };

const subscribedTopicIds = () => {
  try {
    const state = JSON.parse(localStorage.getItem(MYSPACE_KEY) || 'null');
    return new Set((state?.columns || []).filter(isTopicColumn).map(column => column.topic_id || column.source));
  } catch { return new Set(); }
};

const topicName = async topicId => {
  topicsPromise ||= fetch(`${(document.querySelector('main')?.dataset.base || '').replace(/\/$/, '')}/topics.json`)
    .then(response => response.ok ? response.json() : { topics: [] })
    .catch(() => ({ topics: [] }));
  const payload = await topicsPromise;
  return (payload.topics || []).find(topic => topic.id === topicId)?.name_zh || topicId;
};

function suggest(topicId) {
  const store = read();
  if (store.muted[topicId] && Date.now() - Number(store.muted[topicId]) < MUTE_DAYS * DAY_MS) return;
  if (Date.now() - store.lastSuggestedAt < DAY_MS) return;
  store.lastSuggestedAt = Date.now();
  write(store);
  topicName(topicId).then(name => {
    const prompt = showPrompt(`要不要订阅「${name}」这个主题？`, {
      ttl: 0,
      actions: [
        { id: 'subscribe', label: '订阅', onClick: () => { document.dispatchEvent(new CustomEvent('fewgood:subscribe-topic', { detail: { topicId } })); dismissPrompt(prompt); } },
        { id: 'mute', label: '不用了', onClick: () => { const next = read(); next.muted[topicId] = Date.now(); write(next); dismissPrompt(prompt); } },
      ],
    });
  });
}

export function recordFavoriteFromTopic(topicId) {
  if (!topicId) return;
  const store = read();
  store.counts[topicId] = (Number(store.counts[topicId]) || 0) + 1;
  write(store);
  if (store.counts[topicId] >= SUGGEST_THRESHOLD && !subscribedTopicIds().has(topicId)) suggest(topicId);
}
