import { readdir, readFile, writeFile } from 'node:fs/promises';

const publicTopics = new URL('../public/topics/', import.meta.url);
const output = new URL('../src/data/topic-video-catalog.json', import.meta.url);
const files = (await readdir(publicTopics)).filter(name => name.endsWith('.json') && name !== 'index.json' && name !== 'status.json').sort();
const rows = new Map();
for (const file of files) {
  const topic = JSON.parse(await readFile(new URL(file, publicTopics), 'utf8'));
  if (topic.status !== 'ready') continue;
  for (const source of topic.videos || []) {
    const id = source.id || source.video_id;
    if (!id) continue;
    const prior = rows.get(id);
    const topicIds = [...new Set([...(prior?.topic_ids || []), topic.topic_id])].sort();
    // First fixture wins for display fields; every topic membership is retained.
    rows.set(id, { ...(prior || {}), id, title: prior?.title || source.title || id,
      channel: prior?.channel || source.channel || source.channel_title || 'YouTube',
      channel_title: prior?.channel_title || source.channel_title || source.channel || 'YouTube',
      published_at: prior?.published_at || source.published_at || '', duration_seconds: Number(prior?.duration_seconds || source.duration_seconds || 0),
      thumb: prior?.thumb || source.thumbnail || `https://i.ytimg.com/vi/${id}/mqdefault.jpg`, topic_ids: topicIds, topic_only: true });
  }
}
await writeFile(output, `${JSON.stringify([...rows.values()].sort((a, b) => a.id.localeCompare(b.id)), null, 2)}\n`);
