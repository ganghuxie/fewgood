import { humanizeRecommendSpan } from './format.mjs';

const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const duration = seconds => `${Math.floor((Number(seconds) || 0) / 60)}:${String((Number(seconds) || 0) % 60).padStart(2, '0')}`;
const compact = value => new Intl.NumberFormat('zh-CN', { notation: 'compact', maximumFractionDigits: 1 }).format(value || 0);
const ago = value => {
  const days = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86400000));
  return days < 1 ? '今天' : days < 30 ? `${days}天前` : days < 365 ? `${Math.floor(days / 30)}个月前` : `${Math.floor(days / 365)}年前`;
};

function avatar(video) {
  const name = video.channel || '频道';
  const letter = [...name.trim()][0] || '频';
  let hash = 0; for (const char of name) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  const color = ['#d14b4b', '#b06b2f', '#8a6d1d', '#4f8a3d', '#357a8a', '#5367a6', '#7a5795'][hash % 7];
  return `<span class="channel-avatar channel-avatar-letter" style="background-color:${color}" aria-hidden="true">${esc(letter)}</span>`;
}

export function cardMeta(video) {
  const recommenders = Number(video.recommenders);
  if (Number.isFinite(recommenders) && recommenders > 0) {
    return [`${recommenders} 人推荐`, humanizeRecommendSpan(video.months)].filter(Boolean).join(' · ');
  }
  const parts = [];
  if (video.view_count !== null && video.view_count !== undefined && video.view_count !== '' && Number.isFinite(Number(video.view_count))) {
    parts.push(`${compact(video.view_count)} 次观看`);
  }
  if (video.published_at && Number.isFinite(Date.parse(video.published_at))) parts.push(ago(video.published_at));
  return parts.join(' · ');
}

export function card(video, href = '') {
  const meta = cardMeta(video);
  return `<a class="video-card" href="${esc(href)}"><div class="thumbnail"><img loading="lazy" src="https://i.ytimg.com/vi/${encodeURIComponent(video.id)}/maxresdefault.jpg" onerror="this.onerror=null;this.src='https://i.ytimg.com/vi/${encodeURIComponent(video.id)}/mqdefault.jpg'" alt=""><span class="duration">${duration(video.duration_seconds)}</span></div><div class="video-info">${avatar(video)}<div><h2 class="video-title">${esc(video.title)}</h2><p class="video-meta">${esc(video.channel)}</p>${meta ? `<p class="video-meta">${esc(meta)}</p>` : ''}</div></div></a>`;
}
