export const TOPIC_PRIVACY_NOTICE = '你新建的栏目会变成公开可浏览的主题，别人也能看到里面的视频；只有你的订阅关系是私密的。';

export const topicStatus = status => ({
  ready: '就绪', empty: '空', refreshing: '等待中', pending: '等待中',
  retryable_failed: '失败', failed: '失败', quota_deferred: '额度延后',
}[status] || '等待中');

export const topicStatusCopy = status => ({
  ready: '视频已经可以浏览。', empty: '暂时没有匹配视频。',
  refreshing: '通常要等刷新，不保证即时。', pending: '通常要等刷新，不保证即时。',
  retryable_failed: '可稍后再试。', failed: '可稍后再试。', quota_deferred: '额度恢复后会再处理。',
}[status] || '通常要等刷新，不保证即时。');

export const topicUrl = (id, base = '') => `${String(base).replace(/\/$/, '')}/space/topic/${encodeURIComponent(id)}/`;
export const topicVideoUrl = (topicId, videoId, base = '') => `${String(base).replace(/\/$/, '')}/v/${encodeURIComponent(videoId)}/?from=${encodeURIComponent(`topic:${topicId}`)}`;
export const parseTopicSource = value => typeof value === 'string' && value.startsWith('topic:') ? value.slice(6) : '';
export async function fetchPublicTopics(base = '') {
  const root = String(base).replace(/\/$/, '');
  const response = await fetch(`${root}/topics/index.json`);
  if (!response.ok) throw new Error('topics-index');
  return response.json();
}
export async function fetchPublicTopic(id, base = '') {
  const root = String(base).replace(/\/$/, '');
  const response = await fetch(`${root}/topics/${encodeURIComponent(id)}.json`);
  if (!response.ok) throw new Error('topic');
  return response.json();
}
