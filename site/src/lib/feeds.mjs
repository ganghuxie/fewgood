import { existsSync, readFileSync } from 'node:fs';

const data = new URL('../data/', import.meta.url);
export function optionalFeed(name, fallback = { videos: [] }) {
  const path = new URL(`${name}.json`, data);
  return existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : fallback;
}
