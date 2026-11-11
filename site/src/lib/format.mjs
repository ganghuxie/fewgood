export function humanizeRecommendSpan(spanDays) {
  const days = Number(spanDays);
  if (!Number.isFinite(days) || days <= 0) return '';
  if (days >= 365) return `跨 ${Math.max(1, Math.round(days / 365.25))} 年`;
  return `跨 ${Math.max(1, Math.round(days / 30.4375))} 个月`;
}

const SAFE_YT_THUMB_KINDS = new Set(['default', 'mqdefault', 'hqdefault', 'medium', 'high']);
const YT_THUMB_PATH = /\/vi\/[^/]+\/([^/?#]+)\.(?:jpe?g|webp)(?:[?#].*)?$/i;

export function thumbUrl(id, kind = 'hqdefault') {
  return id ? `https://i.ytimg.com/vi/${id}/${kind}.jpg` : '';
}

export function thumbCandidates(id) {
  return id ? [thumbUrl(id, 'hqdefault'), thumbUrl(id, 'mqdefault')] : [];
}

export function thumbFor(video, kind = 'hqdefault') {
  const id = typeof video === 'string' ? video : video?.id;
  const stored = typeof video === 'object' ? (video.thumb || video.thumbnail || '') : '';
  if (stored) {
    const match = String(stored).match(YT_THUMB_PATH);
    if (!match || SAFE_YT_THUMB_KINDS.has(match[1]) || video.thumb_verified === true) return stored;
  }
  return thumbUrl(id, kind);
}

export function thumbFallbackAttr(id) {
  const safeId = String(id ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  return safeId ? `data-thumb-id="${safeId}"` : '';
}
