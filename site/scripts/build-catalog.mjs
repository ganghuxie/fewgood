import { mkdir, readFile, writeFile, access } from 'node:fs/promises';

const dataDir = new URL('../src/data/', import.meta.url);
const read = async (name, fallback = { videos: [] }) => { try { return JSON.parse(await readFile(new URL(name, dataDir), 'utf8')); } catch (error) { if (error.code === 'ENOENT') return fallback; throw error; } };
const [trending, ai, podcast, music, community, channels, zh] = await Promise.all([read('trending.json'), read('ai.json'), read('podcast.json'), read('music.json'), read('videos.json'), read('channels.json', { channels: [] }), read('zh.json', { videos: {} })]);
const index = new Map();
const channelLabels = new Map();
const sectionLabels = { trending: '全部', ai: 'AI前沿', podcast: '播客', music: '音乐', community: '社区推荐' };
const sectionCodes = { trending: 0, ai: 1, podcast: 2, music: 3, community: 4 };
const addLabel = (map, id, section) => { if (!id) return; const labels = map.get(id) || new Set(); labels.add(sectionLabels[section]); map.set(id, labels); };
const addVideo = (video, section, channelId = video.channel_id, external = false) => {
  if (!video?.id) return;
  const prior = index.get(video.id);
  index.set(video.id, { ...prior, ...video, channel_id: video.channel_id || prior?.channel_id || channelId || '', section: prior?.section || section, sections: [...new Set([...(prior?.sections || []), section])], external: prior?.external || external });
  addLabel(channelLabels, channelId || video.channel_id, section);
};
for (const [section, feed] of [['trending', trending], ['ai', ai], ['podcast', podcast], ['music', music], ['community', community]]) {
  for (const video of feed.videos || []) addVideo(video, section);
}
const catalogIndex = new Map(index);
const compact = value => Array.isArray(value) ? compact(value.join(' ')) : typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, 500) : '';
const description = value => { const text = typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, 120) : ''; return text === '在 YouTube 上发现更多精彩内容。' ? '' : text; };
const recentChannelVideos = channel => [...(channel.videos || [])]
  .sort((a, b) => (Date.parse(b.published_at || '') || 0) - (Date.parse(a.published_at || '') || 0))
  .slice(0, 30);
for (const channel of channels.channels || []) for (const video of channel.videos || []) {
  const prior = catalogIndex.get(video.id);
  catalogIndex.set(video.id, { ...prior, ...video, channel: channel.title, channel_id: channel.id, section: prior?.section || 'trending', sections: [...new Set([...(prior?.sections || []), 'trending'])], external: true });
}
const searchIndex = new Map(index);
const channelIndex = new Map((channels.channels || []).map((channel, index) => [channel.id, index]));
for (const channel of channels.channels || []) for (const video of recentChannelVideos(channel)) {
  const prior = searchIndex.get(video.id);
  searchIndex.set(video.id, { ...prior, ...video, channel: channel.title, channel_id: channel.id, section: prior?.section || 'trending', sections: [...new Set([...(prior?.sections || []), 'trending'])], external: true });
}
const output = JSON.stringify([...catalogIndex.values()], null, 2) + '\n';
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
const writes = [writeFile(new URL('catalog.json', dataDir), output), writeFile(new URL('../public/catalog.json', import.meta.url), output), writeFile(new URL('../public/search-index.json', import.meta.url), searchOutput)];
try { await access(channelSource); writes.push(writeFile(new URL('../public/channels.json', import.meta.url), channelOutput)); } catch { /* channel refresh has not run yet */ }
await Promise.all(writes);
