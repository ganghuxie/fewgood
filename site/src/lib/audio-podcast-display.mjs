import { parseFragment, serialize } from 'parse5';

const textOf = node => node.nodeName === '#text' ? node.value : (node.childNodes || []).map(textOf).join('');
const visible = node => textOf(node).replace(/\s+/g, ' ').trim();
const normalized = text => text.replace(/^[\s\p{Extended_Pictographic}\uFE0F🎧【「\[]+/u, '').replace(/[\s】」\]:：]+$/u, '');
const labels = /^(?:相关播客|相关节目|推荐播客|节目推荐|相关推荐|我们还有这些播客)$/;
const episodeTitle = text => /^(?:E\s*)?\d+\s*[-.、：: ]\s*\S/i.test(text);
const links = node => (node.tagName === 'a' ? [node] : []).concat((node.childNodes || []).flatMap(links));
const episodeLink = node => links(node).some(a => a.attrs?.some(({name,value}) => name === 'href' && /\/(?:episode|sound|track)\//i.test(value)));
const timestamp = text => /\b\d{1,2}:\d{2}\b/.test(text);
function heading(node) {
  // A wrapper containing multiple blocks is never itself an appendix heading.
  if ((node.childNodes || []).some(n => ['p', 'div', 'ul', 'ol', 'section', 'h1', 'h2', 'h3', 'h4'].includes(n.tagName))) return false;
  const text = visible(node).replace(/^[-•]\s+/, '');
  if (timestamp(text)) return false;
  if (labels.test(normalized(text))) return true;
  // Only these explicit new-block prefixes may contain the first appendix item.
  return /^(?:相关播客|我们还有这些播客)\s*[:：]\s*\S/.test(text);
}
function appendixItem(node) {
  const text = visible(node);
  if (!text) return true;
  if (timestamp(text) || /^h[1-6]$/.test(node.tagName || '')) return false;
  if (['ul', 'ol'].includes(node.tagName)) {
    const items = (node.childNodes || []).filter(n => n.tagName === 'li');
    return items.length > 0 && items.every(n => episodeTitle(visible(n)) || (episodeLink(n) && links(n).map(visible).join(' ').trim() === visible(n)));
  }
  // Linked episode rows must consist of the link, not prose mentioning a link.
  return episodeTitle(text) || (episodeLink(node) && links(node).map(visible).join(' ').trim() === text);
}
function filterChildren(parent) {
  const kept = [];
  let dropping = false;
  for (const node of parent.childNodes || []) {
    if (heading(node)) { dropping = true; continue; }
    if (dropping && appendixItem(node)) continue;
    dropping = false; // Any unrecognized content is a safe boundary, kept in full.
    if (['div', 'section', 'article', 'blockquote'].includes(node.tagName)) filterChildren(node);
    kept.push(node);
  }
  parent.childNodes = kept;
}

// Display transform only: ingestion and stored RSS descriptions remain untouched.
// parse5 tolerates the real feeds' stray closing anchors and preserves block structure.
export function displayNotes(html = '', plain = '') {
  const source = html || String(plain).split(/\n+/).map(line => `<p>${line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>`).join('');
  const tree = parseFragment(source);
  filterChildren(tree);
  return serialize(tree);
}
export function episodeExcerpt(episode, limit = 150) {
  const tree = parseFragment(displayNotes(episode.description_html, episode.description_text));
  // Separate blocks before collapsing whitespace so adjacent paragraphs don't merge.
  const text = (tree.childNodes || []).map(visible).join(' ').replace(/\s+/g, ' ').trim();
  return text.length > limit ? `${text.slice(0, limit).trim()}…` : text;
}
