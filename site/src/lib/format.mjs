export function humanizeRecommendSpan(months) {
  const n = Number(months);
  if (!Number.isFinite(n) || n <= 0) return '';
  if (n >= 12) return `${Math.floor(n / 12)} 年前`;
  return `${Math.round(n)} 个月`;
}

export function thumbUrl(id, kind = 'maxresdefault') {
  return id ? `https://i.ytimg.com/vi/${id}/${kind}.jpg` : '';
}

export function thumbFallbackAttr(id) {
  return `this.onerror=null;this.src='${thumbUrl(id, 'mqdefault')}'`;
}
