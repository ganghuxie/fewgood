export function humanizeRecommendSpan(spanDays) {
  const days = Number(spanDays);
  if (!Number.isFinite(days) || days <= 0) return '';
  if (days >= 365) return `跨 ${Math.max(1, Math.round(days / 365.25))} 年`;
  return `跨 ${Math.max(1, Math.round(days / 30.4375))} 个月`;
}

export function relativePublishedTime(value, now = Date.now()) {
  const published = Date.parse(value || '');
  if (!Number.isFinite(published) || !Number.isFinite(now) || published > now) return '';
  const day = stamp => {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(stamp));
    const get = type => Number(parts.find(part => part.type === type)?.value);
    return Date.UTC(get('year'), get('month') - 1, get('day'));
  };
  const days = Math.floor((day(now) - day(published)) / 86400000);
  if (days < 0) return '';
  if (days === 0) return '今天';
  if (days === 1) return '昨天';
  if (days < 30) return `${days}天前`;
  if (days < 365) return `${Math.floor(days / 30)}个月前`;
  return `${Math.floor(days / 365)}年前`;
}

export function shouldShowWhy(video) {
  const why = String(video?.why_good || '').trim();
  if (!why || /来自.*频道|近期长视频|播放第/.test(why)) return false;
  if (Number(video?.recommenders) > 0 && /(HN|用户|人推荐|推荐|跨\s*\d+\s*年|跨\s*\d+\s*个月)/i.test(why)) return false;
  return true;
}

const SAFE_YT_THUMB_KINDS = new Set(['default', 'mqdefault', 'hqdefault', 'medium', 'high']);
const YT_THUMB_PATH = /\/vi\/[^/]+\/([^/?#]+)\.(?:jpe?g|webp)(?:[?#].*)?$/i;
export const CARD_THUMB_SIZES = '(min-width: 1600px) 20vw, (min-width: 1300px) 25vw, (min-width: 900px) 33vw, (min-width: 600px) 50vw, 100vw';

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
    if (!match || SAFE_YT_THUMB_KINDS.has(match[1])) return stored;
  }
  return thumbUrl(id, kind);
}

export function heroThumbFor(video) {
  const id = typeof video === 'string' ? video : video?.id;
  const stored = typeof video === 'object' ? (video.thumb || video.thumbnail || '') : '';
  const match = String(stored).match(YT_THUMB_PATH);
  if (video?.thumb_verified === true) {
    if (match && ['maxresdefault', 'hq720'].includes(match[1])) return stored;
    return thumbUrl(id, 'maxresdefault');
  }
  return thumbFor(video);
}

export function thumbSrcset(video) {
  const id = typeof video === 'string' ? video : video?.id;
  return id ? [
    `${thumbUrl(id, 'mqdefault')} 320w`,
    `${thumbUrl(id, 'hqdefault')} 480w`,
    `${thumbUrl(id, 'sddefault')} 640w`,
  ].join(', ') : '';
}

export function thumbFallbackAttr(id) {
  const safeId = String(id ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  return safeId ? `data-thumb-id="${safeId}"` : '';
}
