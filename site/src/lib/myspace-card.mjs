import { CARD_THUMB_SIZES, thumbFallbackAttr, thumbFor, thumbSrcset } from './format.mjs';

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
  const why = video.why_good && !/来自.*频道|近期长视频|播放第/.test(String(video.why_good)) ? `<p class="why-good">${esc(video.why_good)}</p>` : '';
  const classic = video.community_classic ? '<span class="community-classic-badge">社区经典</span>' : '';
  return `<article class="video-card"><a class="card-link" href="${esc(href)}"><div class="thumbnail"><img loading="lazy" src="${esc(thumbFor(video))}" srcset="${esc(thumbSrcset(video))}" sizes="${CARD_THUMB_SIZES}" ${thumbFallbackAttr(video.id)} alt="">${classic}<span class="duration">${duration(video.duration_seconds)}</span></div><div class="video-info">${avatar(video)}<div class="video-copy"><h2 class="video-title">${esc(title)}</h2>${why}<p class="video-meta">${esc(video.channel)} · ${duration(video.duration_seconds)}</p></div></div></a><button class="watch-later-action" type="button" data-watch-later data-id="${esc(video.id)}" data-title="${esc(title)}" data-channel="${esc(video.channel)}" data-duration="${Number(video.duration_seconds) || 0}" aria-pressed="false">◷ 稍后再看</button></article>`;
}
