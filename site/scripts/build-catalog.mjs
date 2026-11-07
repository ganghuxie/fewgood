import { mkdir, readFile, writeFile, access } from 'node:fs/promises';

const dataDir = new URL('../src/data/', import.meta.url);
const read = async (name, fallback = { videos: [] }) => { try { return JSON.parse(await readFile(new URL(name, dataDir), 'utf8')); } catch (error) { if (error.code === 'ENOENT') return fallback; throw error; } };
const [trending, ai, podcast, music, community, channels, zh] = await Promise.all([read('trending.json'), read('ai.json'), read('podcast.json'), read('music.json'), read('videos.json'), read('channels.json', { channels: [] }), read('zh.json', { videos: {} })]);
const index = new Map();
for (const [section, feed] of [['trending', trending], ['ai', ai], ['podcast', podcast], ['music', music], ['community', community]]) {
  for (const video of feed.videos) {
    const prior = index.get(video.id);
    // Preserve one searchable record per ID while retaining every source in case
    // a video belongs to both editorial feeds.
    index.set(video.id, { ...prior, ...video, section: prior?.section || section, sections: [...new Set([...(prior?.sections || []), section])] });
  }
}
const output = JSON.stringify([...index.values()], null, 2) + '\n';
const channelOutput = JSON.stringify(channels, null, 2) + '\n';
const compact = value => Array.isArray(value) ? compact(value.join(' ')) : typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, 500) : '';
const searchVideos = [...index.values()].map(video => {
  const enrichment = zh.videos?.[video.id] || {};
  return { id: video.id, title: compact(video.title), channel: compact(video.channel), channel_id: video.channel_id || '', description: compact(video.description || video.summary || video.blurb || video.tags), title_zh: compact(enrichment.title_zh), summary_zh: compact(enrichment.blurb_zh || enrichment.summary_zh), published_at: video.published_at || '', selected_at: video.selected_at || '', duration_seconds: Number(video.duration_seconds) || 0, view_count: Number(video.view_count) || 0, section: video.section || 'trending' };
});
const searchChannels = (channels.channels || []).map(channel => ({ id: channel.id, title: compact(channel.title), thumbnail: channel.thumbnail || '', subscriber_count: Number(channel.subscriber_count) || 0, description: compact(channel.description || channel.about || channel.summary) }));
const searchOutput = JSON.stringify({ videos: searchVideos, channels: searchChannels }) + '\n';
await mkdir(dataDir, { recursive: true });
await mkdir(new URL('../public/', import.meta.url), { recursive: true });
const channelSource = new URL('channels.json', dataDir);
const writes = [writeFile(new URL('catalog.json', dataDir), output), writeFile(new URL('../public/catalog.json', import.meta.url), output), writeFile(new URL('../public/search-index.json', import.meta.url), searchOutput)];
try { await access(channelSource); writes.push(writeFile(new URL('../public/channels.json', import.meta.url), channelOutput)); } catch { /* channel refresh has not run yet */ }
await Promise.all(writes);
