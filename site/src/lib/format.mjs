export function humanizeRecommendSpan(spanDays) {
  const days = Number(spanDays);
  if (!Number.isFinite(days) || days <= 0) return '';
  if (days >= 365) return `跨 ${Math.max(1, Math.round(days / 365.25))} 年`;
  return `跨 ${Math.max(1, Math.round(days / 30.4375))} 个月`;
}

export function thumbUrl(id, kind = 'maxresdefault') {
  return id ? `https://i.ytimg.com/vi/${id}/${kind}.jpg` : '';
}

export function thumbFallbackAttr(id) {
  return `this.onerror=null;this.src='${thumbUrl(id, 'mqdefault')}'`;
}
