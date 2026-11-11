export const SITE_NAME = 'fewgood.';
export const TAGLINE = 'a few good videos · 无广告 · 只看好视频';
export const DIALOG_BRAND = SITE_NAME;
export const MODE_LABELS = { explore: '探索世界', myspace: '我的空间' };
export const SECTION_LABELS = { picks: '精选', trending: '趋势', ai: 'AI前沿', podcast: '播客', music: '音乐', community: '社区推荐' };
export const COMMUNITY_SUBSOURCES = { people: '最多推荐', newest: '最新入选' };
export const MYSPACE_SOURCES = [
  { id: 'picks', label: SECTION_LABELS.picks, section: 'picks' },
  { id: 'trending', label: SECTION_LABELS.trending, section: 'trending' },
  { id: 'ai', label: SECTION_LABELS.ai, section: 'ai' },
  { id: 'podcast', label: SECTION_LABELS.podcast, section: 'podcast' },
  { id: 'music', label: SECTION_LABELS.music, section: 'music' },
  { id: 'community:people', label: `${SECTION_LABELS.community} · ${COMMUNITY_SUBSOURCES.people}`, section: 'community', sort: 'people' },
  { id: 'community:newest', label: `${SECTION_LABELS.community} · ${COMMUNITY_SUBSOURCES.newest}`, section: 'community', sort: 'newest' },
];
