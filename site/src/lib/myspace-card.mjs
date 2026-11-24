import { CARD_THUMB_SIZES, relativePublishedTime, thumbFallbackAttr, thumbFor, thumbSrcset } from './format.mjs';

const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const duration = seconds => `${Math.floor((Number(seconds) || 0) / 60)}:${String((Number(seconds) || 0) % 60).padStart(2, '0')}`;

function avatar(video) {
  const name = video.channel || '频道';
  const letter = [...name.trim()][0] || '频';
  let hash = 0; for (const char of name) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  const color = ['#d14b4b', '#b06b2f', '#8a6d1d', '#4f8a3d', '#357a8a', '#5367a6', '#7a5795'][hash % 7];
  return `<span class="channel-avatar channel-avatar-letter" style="background-color:${color}" aria-hidden="true">${esc(letter)}</span>`;
}

export function card(video, href = '', zh = null) {
  const zhTitle = zh?.title_zh || video.title_zh || '';
  const title = zhTitle || video.title;
  const classic = video.community_classic ? `<span class="community-classic-badge">${Number(video.recommenders) > 0 ? `HN ${Number(video.recommenders)} 人推荐` : '社区精选'}</span>` : '';
  const published = relativePublishedTime(video.published_at);
  return `<article class="video-card"><a class="card-link" href="${esc(href)}"><div class="thumbnail"><img loading="lazy" src="${esc(thumbFor(video))}" srcset="${esc(thumbSrcset(video))}" sizes="${CARD_THUMB_SIZES}" ${thumbFallbackAttr(video.id)} alt="">${classic}<span class="duration">${duration(video.duration_seconds)}</span><button class="watch-later-action" type="button" data-watch-later data-id="${esc(video.id)}" data-title="${esc(title)}" data-channel="${esc(video.channel)}" data-duration="${Number(video.duration_seconds) || 0}" data-published-at="${esc(video.published_at || '')}" data-tooltip="稍后再看" aria-label="稍后再看" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></svg></button></div><div class="video-info">${avatar(video)}<div class="video-copy"><h2 class="video-title">${esc(title)}</h2><p class="video-meta"><span class="video-meta-channel">${esc(video.channel)}</span>${published ? `<span class="video-meta-separator">·</span><span class="video-meta-time">${published}</span>` : ''}</p></div></div></a></article>`;
}
