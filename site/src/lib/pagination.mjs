export const PAGE_SIZE = 50;
export function pageUrl(sort, page, base = '') {
  const path = sort === 'newest' ? '/newest/' : '/';
  const relativePath = page === 1 ? path : `${path}page/${page}/`;
  if (!base || base === '/') return relativePath;
  return `${base.replace(/\/$/, '')}${relativePath}`;
}
export function pageNumbers(page, pages) {
  const numbers = Array.from({ length: pages }, (_, i) => i + 1)
    .filter(n => n === 1 || n === pages || Math.abs(n - page) <= 2);
  return numbers.flatMap((n, i) => i && n - numbers[i - 1] > 1 ? [null, n] : [n]);
}
export function paginate(videos, sort) {
  const sorted = [...videos].sort((a, b) =>
    (sort === 'newest'
      ? b.selected_at - a.selected_at || b.last - a.last
      : b.recommenders - a.recommenders || b.months - a.months)
    || a.id.localeCompare(b.id));
  const pages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  return Array.from({ length: pages }, (_, i) => ({
    videos: sorted.slice(i * PAGE_SIZE, (i + 1) * PAGE_SIZE),
    total: sorted.length, page: i + 1, pages, sort,
  }));
}
