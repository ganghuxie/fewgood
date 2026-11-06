export const PAGE_SIZE = 20;

// Detail pages are shared by video ID. `from` keeps a static detail page aware
// of which feed supplied the click, so related videos stay in that feed.
export function videoUrl(section, id, base = '') {
  const path = `/v/${id}/?from=${section}`;
  return !base || base === '/' ? path : `${base.replace(/\/$/, '')}${path}`;
}

export function pageUrl(section, page, base = '', sort = 'people') {
  let path;
  if (section === 'ai') path = '/ai/';
  else if (section === 'community') path = sort === 'newest' ? '/community/newest/' : '/community/';
  else path = '/';
  const relative = page === 1 ? path : `${path}page/${page}/`;
  return !base || base === '/' ? relative : `${base.replace(/\/$/, '')}${relative}`;
}

export function pageNumbers(page, pages) {
  const numbers = Array.from({ length: pages }, (_, i) => i + 1)
    .filter(n => n === 1 || n === pages || Math.abs(n - page) <= 2);
  return numbers.flatMap((n, i) => i && n - numbers[i - 1] > 1 ? [null, n] : [n]);
}

export function paginate(videos, section, sort = 'people') {
  const sorted = [...videos].sort((a, b) => {
    if (section === 'community') return (sort === 'newest'
      ? b.selected_at - a.selected_at || b.last - a.last
      : b.recommenders - a.recommenders || b.months - a.months) || a.id.localeCompare(b.id);
    return b.view_count - a.view_count || a.id.localeCompare(b.id);
  });
  const pages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  return Array.from({ length: pages }, (_, i) => ({
    videos: sorted.slice(i * PAGE_SIZE, (i + 1) * PAGE_SIZE), total: sorted.length,
    page: i + 1, pages, section, sort,
  }));
}
