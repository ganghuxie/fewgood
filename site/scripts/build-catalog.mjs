import { mkdir, readFile, writeFile, access } from 'node:fs/promises';

const dataDir = new URL('../src/data/', import.meta.url);
const read = async (name, fallback = { videos: [] }) => { try { return JSON.parse(await readFile(new URL(name, dataDir), 'utf8')); } catch (error) { if (error.code === 'ENOENT') return fallback; throw error; } };
const [trending, ai, podcast, music, community, channels] = await Promise.all([read('trending.json'), read('ai.json'), read('podcast.json'), read('music.json'), read('videos.json'), read('channels.json', { channels: [] })]);
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
await mkdir(dataDir, { recursive: true });
await mkdir(new URL('../public/', import.meta.url), { recursive: true });
const channelSource = new URL('channels.json', dataDir);
const writes = [writeFile(new URL('catalog.json', dataDir), output), writeFile(new URL('../public/catalog.json', import.meta.url), output)];
try { await access(channelSource); writes.push(writeFile(new URL('../public/channels.json', import.meta.url), channelOutput)); } catch { /* channel refresh has not run yet */ }
await Promise.all(writes);
