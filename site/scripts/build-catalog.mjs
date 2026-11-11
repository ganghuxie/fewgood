import { mkdir, readFile, writeFile, access } from 'node:fs/promises';

const dataDir = new URL('../src/data/', import.meta.url);
const read = async (name, fallback = { videos: [] }) => { try { return JSON.parse(await readFile(new URL(name, dataDir), 'utf8')); } catch (error) { if (error.code === 'ENOENT') return fallback; throw error; } };
const [picks, trending, ai, podcast, music, editorial, community, channels, zh, topics, topicLookup, templates, hnPool] = await Promise.all([
  read('picks.json'), read('trending.json'), read('ai.json'), read('podcast.json'), read('music.json'), read('editorial.json'), read('videos.json'),
  read('channels.json', { channels: [] }), read('zh.json', { videos: {} }),
  read('topics.json', { topics: [] }), read('topic_lookup.json', {}), read('templates.json', { templates: [] }), read('hn_pool.json', { videos: [] }),
]);
const index = new Map();
const topicById = new Map((topics.topics || []).map(topic => [topic.id, topic]));
const channelLabels = new Map();
const sectionLabels = { picks: '精选', trending: '趋势', ai: 'AI前沿', podcast: '播客', music: '音乐', editorial: '科学教育', community: '社区推荐' };
const sectionCodes = { trending: 0, ai: 1, podcast: 2, music: 3, community: 4, picks: 5, editorial: 6 };
const addLabel = (map, id, section) => { if (!id) return; const labels = map.get(id) || new Set(); labels.add(sectionLabels[section]); map.set(id, labels); };
const addVideo = (video, section, channelId = video.channel_id, external = false) => {
  if (!video?.id) return;
  const prior = index.get(video.id);
  const merged = { ...prior, ...video, section: prior?.section || section, sections: [...new Set([...(prior?.sections || []), section])] };
  const channel = video.channel_id || prior?.channel_id || channelId;
  if (channel) merged.channel_id = channel;
  if (prior?.external || external) merged.external = true;
  index.set(video.id, merged);
  addLabel(channelLabels, channelId || video.channel_id, section);
};
for (const [section, feed] of [['community', community], ['ai', ai], ['podcast', podcast], ['music', music], ['editorial', editorial], ['trending', trending], ['picks', picks]]) {
  for (const video of feed.videos || []) addVideo(video, section);
}
const compact = value => Array.isArray(value) ? compact(value.join(' ')) : typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, 500) : '';
const description = value => { const text = typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, 120) : ''; return text === '在 YouTube 上发现更多精彩内容。' ? '' : text; };
const recentChannelVideos = channel => [...(channel.videos || [])]
  .sort((a, b) => (Date.parse(b.published_at || '') || 0) - (Date.parse(a.published_at || '') || 0))
  .slice(0, 30)
  .concat((channel.videos || []).filter(video => video.title === 'Taylor Swift at the 2026 MTV Video Music Awards'));

// Keep the catalog limited to editorial feeds. Channel videos are search-only data.
for (const video of index.values()) {
  const topicId = topicLookup[video.id];
  if (topicId) {
    video.topic_id = topicId;
    video.topic_name = topicById.get(topicId)?.name_zh || null;
  }
}
const output = JSON.stringify([...index.values()], null, 2) + '\n';

const normalizeVideoId = value => {
  if (typeof value !== 'string') return '';
  const raw = value.trim();
  try {
    const url = new URL(raw);
    if (url.hostname === 'youtu.be') return url.pathname.slice(1).split('/')[0];
    if (url.hostname.endsWith('youtube.com')) return url.searchParams.get('v') || url.pathname.split('/').filter(Boolean).pop() || raw;
  } catch { /* plain YouTube ID */ }
  return raw.replace(/[?#].*$/, '');
};
const normalizeTitle = value => String(value || '').normalize('NFKC').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');
const recordScore = video => [video.duration_seconds, video.view_count, video.thumb, video.thumbnail].reduce((score, value) => score + (value ? 1 : 0), 0);
const mergeVideo = (prior, video) => {
  if (!prior) return { ...video };
  const winner = recordScore(video) > recordScore(prior) ? video : prior;
  const loser = winner === video ? prior : video;
  return { ...loser, ...winner, id: normalizeVideoId(winner.id) || winner.id };
};
const searchIndex = new Map();
const searchKeys = new Map();
const addSearchVideo = (video, channel, external = false) => {
  if (!video?.id) return;
  const record = { ...video, channel: channel.title, channel_id: channel.id, external };
  const id = normalizeVideoId(record.id);
  const idKey = id ? `id:${id}` : '';
  const titleKey = `title:${normalizeVideoId(channel.id)}:${normalizeTitle(record.title)}`;
  const priorKey = (idKey && searchKeys.get(idKey)) || searchKeys.get(titleKey);
  const key = priorKey || idKey || titleKey;
  const prior = searchIndex.get(key);
  searchIndex.set(key, mergeVideo(prior, record));
  if (idKey) searchKeys.set(idKey, key);
  searchKeys.set(titleKey, key);
};
for (const video of index.values()) {
  const channel = (channels.channels || []).find(item => item.id === video.channel_id) || { id: video.channel_id || '', title: video.channel || '' };
  addSearchVideo({ ...video, external: false }, channel);
}
const channelIndex = new Map((channels.channels || []).map((channel, index) => [channel.id, index]));
for (const channel of channels.channels || []) for (const video of recentChannelVideos(channel)) {
  addSearchVideo(video, channel, true);
}
const channelOutput = JSON.stringify(channels, null, 2) + '\n';
const searchVideos = [...searchIndex.values()].map(video => {
  const enrichment = zh.videos?.[video.id] || {};
  return [video.id, compact(video.title), channelIndex.get(video.channel_id) ?? '', description(video.description || video.summary || video.blurb || video.tags), compact(enrichment.title_zh), Number(video.duration_seconds) || 0, sectionCodes[video.section] ?? 0, !!video.external];
});
const searchChannels = (channels.channels || []).map(channel => [channel.id, compact(channel.title), channel.thumbnail || '', Number(channel.subscriber_count) || 0, description(channel.description || channel.about || channel.summary), [...(channelLabels.get(channel.id) || [])].join(' ')]);
const searchOutput = JSON.stringify({ videos: searchVideos, channels: searchChannels }) + '\n';
await mkdir(dataDir, { recursive: true });
await mkdir(new URL('../public/', import.meta.url), { recursive: true });
const channelSource = new URL('channels.json', dataDir);
const writes = [
  writeFile(new URL('catalog.json', dataDir), output),
  writeFile(new URL('../public/catalog.json', import.meta.url), output),
  writeFile(new URL('../public/search-index.json', import.meta.url), searchOutput),
  writeFile(new URL('../public/topics.json', import.meta.url), JSON.stringify(topics, null, 2) + '\n'),
  writeFile(new URL('../public/topic_lookup.json', import.meta.url), JSON.stringify(topicLookup, null, 2) + '\n'),
  writeFile(new URL('../public/templates.json', import.meta.url), JSON.stringify(templates, null, 2) + '\n'),
  writeFile(new URL('../public/hn_pool.json', import.meta.url), JSON.stringify(hnPool, null, 2) + '\n'),
];
try { await access(channelSource); writes.push(writeFile(new URL('../public/channels.json', import.meta.url), channelOutput)); } catch { /* channel refresh has not run yet */ }
await Promise.all(writes);
