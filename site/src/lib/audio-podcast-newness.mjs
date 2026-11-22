const STORAGE_PREFIX = 'fewgood.audio-podcast.seen.v1.';
export const FIRST_VISIT_WINDOW_DAYS = 14;

function dateValue(value) {
  const raw = String(value || '');
  // The ingestion export carries date-only RSS values in the site's
  // Asia/Shanghai display convention; preserve that convention at the edge.
  const timestamp = Date.parse(/^\d{4}-\d{2}-\d{2}$/.test(raw) ? `${raw}T00:00:00+08:00` : raw);
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function stableEpisodeId(episode) {
  for (const value of [episode?.guid, episode?.episode_id, episode?.episode_link, episode?.audio_url]) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

export function latestEpisodeMarker(show) {
  const episodes = Array.isArray(show?.episodes) ? show.episodes : [];
  const latest = episodes
    .map((episode, index) => ({ episode, index, publishedAt: episode?.published_at_asia_shanghai || episode?.published_at_utc || episode?.published_at || null }))
    .filter(item => stableEpisodeId(item.episode) && dateValue(item.publishedAt) !== null)
    .sort((left, right) => dateValue(right.publishedAt) - dateValue(left.publishedAt) || left.index - right.index)[0];
  if (!latest || !show?.slug) return null;
  return {
    slug: String(show.slug),
    episodeId: stableEpisodeId(latest.episode),
    publishedAt: latest.publishedAt,
  };
}

export function markerFromDataset(dataset) {
  if (!dataset?.audioShow || !dataset?.audioLatestId || !dataset?.audioLatestPublishedAt) return null;
  return {
    slug: dataset.audioShow,
    episodeId: dataset.audioLatestId,
    publishedAt: dataset.audioLatestPublishedAt,
  };
}

function storageKey(slug) {
  return `${STORAGE_PREFIX}${slug}`;
}

function readSeen(storage, slug) {
  if (!storage || typeof storage.getItem !== 'function') return { available: false, value: null };
  try {
    const raw = storage?.getItem(storageKey(slug));
    const value = raw ? JSON.parse(raw) : null;
    if (!value || typeof value.episodeId !== 'string' || dateValue(value.publishedAt) === null) return { available: true, value: null };
    return { available: true, value };
  } catch {
    return { available: false, value: null };
  }
}

function browserStorage() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

export function shouldShowNewEpisode(marker, { storage = browserStorage(), now = Date.now() } = {}) {
  const publishedAt = dateValue(marker?.publishedAt);
  if (!marker?.slug || !marker?.episodeId || publishedAt === null) return false;
  const seenState = readSeen(storage, marker.slug);
  if (!seenState.available) return false;
  const seen = seenState.value;
  if (!seen) {
    const age = Number(now) - publishedAt;
    return age >= 0 && age <= FIRST_VISIT_WINDOW_DAYS * 24 * 60 * 60 * 1000;
  }
  const seenAt = dateValue(seen.publishedAt);
  return publishedAt > seenAt || (publishedAt === seenAt && marker.episodeId !== seen.episodeId);
}

export function markAudioShowSeen(marker, { storage = browserStorage() } = {}) {
  if (!marker?.slug || !marker?.episodeId || dateValue(marker.publishedAt) === null) return false;
  if (!storage || typeof storage.setItem !== 'function') return false;
  try {
    storage?.setItem(storageKey(marker.slug), JSON.stringify({
      episodeId: marker.episodeId,
      publishedAt: marker.publishedAt,
    }));
    return true;
  } catch {
    return false;
  }
}

export function applyAudioNewnessDots(root = document, options = {}) {
  try {
    root.querySelectorAll('[data-audio-newness-card]').forEach(card => {
      const dot = card.querySelector('[data-audio-newness-dot]');
      if (dot) dot.hidden = !shouldShowNewEpisode(markerFromDataset(card.dataset), options);
    });
  } catch {
    // Newness is an optional local affordance; rendering must remain unaffected.
  }
}
