import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PAGE_SIZE } from './pagination.mjs';
import catalogSnapshot from '../data/audio_podcast_catalog.json' with { type: 'json' };

export { PAGE_SIZE };

export const PREVIEW_ROOT = '/audio-podcast/';
export const EPISODE_COUNT_LABEL = '本站已收录单集';

export const HOST_KIND_LABELS = Object.freeze({
  xiaoyuzhou: '小宇宙（发布平台）',
  storyfm: '故事FM 官网',
  ximalaya: '喜马拉雅（发布平台）',
  wavpub: 'Wavpub（发布平台）',
  danlirencomedy: '单立人喜剧（发布平台）',
});

export function hostKindLabel(kind) {
  return HOST_KIND_LABELS[kind] || String(kind || '未知发布平台');
}

function withBase(base, path) {
  const prefix = String(base || '').replace(/\/$/, '');
  return prefix ? `${prefix}${path}` : path;
}

export function previewPath(base = '') {
  return withBase(base, PREVIEW_ROOT);
}

export function showPath(slug, page = 1, base = '') {
  const pageNumber = Number(page) || 1;
  const suffix = pageNumber > 1 ? `page/${pageNumber}/` : '';
  return withBase(base, `${PREVIEW_ROOT}${slug}/${suffix}`);
}

export function episodeAnchor(episode, index = 0) {
  const value = String(episode?.episode_id || episode?.guid || index + 1);
  return `episode-${value.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
}

export function episodeIndex(episodes, episode) {
  const id = episode?.episode_id || episode?.guid;
  return (episodes || []).findIndex(candidate =>
    (id && (candidate.episode_id === id || candidate.guid === id))
    || (!id && episode?.title && candidate.title === episode.title));
}

export function episodeRouteId(episode) {
  const raw = String(episode?.guid || episode?.episode_id || '');
  if (!raw) throw new Error('Episode identity is required');
  // Reserve ep- for hashes so literal GUIDs cannot collide with hashed GUIDs.
  if (/^[A-Za-z0-9._-]{1,96}$/.test(raw) && !['.', '..', 'page'].includes(raw) && !raw.startsWith('ep-')) return raw;
  return `ep-${createHash('sha256').update(raw, 'utf8').digest('hex')}`;
}

export function episodePath(show, episode, base = '') {
  return `${showPath(show.slug, 1, base)}${episodeRouteId(episode)}/`;
}

export function episodeEntries(show) {
  const seen = new Set();
  return latestFirst(show.episodes).map((episode, index) => {
    const id = episodeRouteId(episode);
    if (seen.has(id)) throw new Error(`Duplicate episode route: ${show.slug}/${id}`);
    seen.add(id);
    return { episode, id, page: Math.floor(index / PAGE_SIZE) + 1 };
  });
}

export function pageCount(total, pageSize = PAGE_SIZE) {
  const size = Math.max(1, Number(pageSize) || PAGE_SIZE);
  return Math.max(1, Math.ceil(Math.max(0, Number(total) || 0) / size));
}

export function latestFirst(episodes) {
  return (episodes || [])
    .map((episode, index) => ({
      episode,
      index,
      time: Date.parse(episode?.published_at_utc || episode?.published_at || '') || 0,
    }))
    .sort((a, b) => b.time - a.time || a.index - b.index)
    .map(({ episode }) => episode);
}

export function sliceEpisodePage(episodes, page = 1, pageSize = PAGE_SIZE) {
  const size = Math.max(1, Number(pageSize) || PAGE_SIZE);
  const pageNumber = Math.max(1, Number(page) || 1);
  return latestFirst(episodes).slice((pageNumber - 1) * size, pageNumber * size);
}

export function sortRecentSelection(items) {
  return (items || [])
    .map((item, index) => ({
      item,
      index,
      time: Date.parse(item?.episode?.published_at_utc || item?.episode?.published_at || '') || 0,
    }))
    .sort((a, b) => b.time - a.time || a.index - b.index)
    .map(({ item }) => item);
}

const DATA_CANDIDATES = [
  fileURLToPath(new URL('../data/audio_podcast.json', import.meta.url)),
  fileURLToPath(new URL('../../src/data/audio_podcast.json', import.meta.url)),
  resolve(process.cwd(), 'src/data/audio_podcast.json'),
  resolve(process.cwd(), 'site/src/data/audio_podcast.json'),
];
const DATA_FILE = DATA_CANDIDATES.find(candidate => existsSync(candidate)) || DATA_CANDIDATES[0];
let cachedData;

function mergeCatalogSnapshot(data) {
  try {
    if (!Array.isArray(catalogSnapshot.shows) || !catalogSnapshot.shows.length) return data;
    const existing = new Map(data.shows.map(show => [show.slug, show]));
    const shows = catalogSnapshot.shows.map(catalogShow => {
      const snapshotShow = existing.get(catalogShow.slug) || {};
      return {
        ...snapshotShow,
        ...catalogShow,
        daily_update: Boolean(catalogShow.daily_update),
        episodes: Array.isArray(snapshotShow.episodes) ? snapshotShow.episodes : [],
        feed: snapshotShow.feed || {},
      };
    });
    const dailySlugs = new Set(shows.filter(show => show.daily_update).map(show => show.slug));
    return {
      ...data,
      show_count: shows.length,
      catalog: catalogSnapshot.catalog,
      shows,
      // The old daily snapshot can contain a daily show's time-sorted items.
      // Keep the compatibility snapshot but never display those as a pick.
      recent_selection: {
        ...data.recent_selection,
        items: data.recent_selection.items.filter(item =>
          existing.has(item.show_slug) && !dailySlugs.has(item.show_slug)),
      },
    };
  } catch {
    return data;
  }
}

export function loadAudioPodcastData(file = DATA_FILE) {
  if (file === DATA_FILE && cachedData) return cachedData;
  try {
    const data = JSON.parse(readFileSync(file, 'utf8'));
    if (!Array.isArray(data.shows) || !data.shows.every(show =>
      show && typeof show.slug === 'string' && Array.isArray(show.episodes)
      && show.episodes.every(episode => episode && typeof episode === 'object'))
      || !data.recent_selection || !Array.isArray(data.recent_selection.items)
      || !data.recent_selection.items.every(item => item && typeof item.show_slug === 'string'
        && item.episode && typeof item.episode === 'object')
      || (data.planned_shows !== undefined && !Array.isArray(data.planned_shows))) {
      throw new Error('Invalid audio catalog');
    }
    const resolved = file === DATA_FILE ? mergeCatalogSnapshot(data) : data;
    if (file === DATA_FILE) cachedData = resolved;
    return resolved;
  } catch {
    return {
      available: false,
      unavailable_message: '当前音频目录暂不可用，请稍后再试。',
      shows: [], planned_shows: [], recent_selection: { items: [] },
    };
  }
}
