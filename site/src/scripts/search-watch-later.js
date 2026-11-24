import { KEYS, has, toggleVideo } from './library.js';

export const watchLaterIcon = checked => checked
  ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>'
  : '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></svg>';
const snapshot = button => ({ id: button.dataset.id, title: button.dataset.title, channel: button.dataset.channel, duration: Number(button.dataset.duration) || 0, published_at: button.dataset.publishedAt || '' });
const buttonsIn = root => [...(root instanceof Element && root.matches('[data-watch-later]') ? [root] : []), ...(root.querySelectorAll?.('[data-watch-later]') || [])];
const paint = button => {
  const added = has(KEYS.watchLater, button.dataset.id);
  button.innerHTML = `${watchLaterIcon(added)}<span class="watch-later-label">${added ? '已添加' : '稍后观看'}</span>`;
  button.dataset.added = String(added);
  button.setAttribute('aria-label', added ? '已添加到稍后观看' : '添加到稍后观看');
  button.setAttribute('aria-pressed', String(added));
};
document.addEventListener('click', event => {
  const button = event.target.closest('[data-watch-later]');
  if (!button) return;
  event.preventDefault(); event.stopPropagation();
  if (has(KEYS.watchLater, button.dataset.id)) return;
  toggleVideo(KEYS.watchLater, snapshot(button));
  // The check is persistent; matching cards repaint through the library event.
  paint(button);
});
const style = document.createElement('style');
style.textContent = `.thumbnail .watch-later-action,.sr-thumbnail .watch-later-action{position:absolute!important;right:8px!important;top:8px!important;z-index:4;border:0!important;border-radius:7px!important;height:28px!important;width:28px!important;max-width:calc(100% - 16px)!important;padding:0 7px!important;display:flex!important;align-items:center!important;justify-content:flex-start!important;gap:6px!important;overflow:hidden!important;background:rgb(15 15 15 / .82)!important;color:#fff!important;cursor:pointer;white-space:nowrap!important;transition:width .16s ease!important}.thumbnail .watch-later-action svg,.sr-thumbnail .watch-later-action svg{width:14px!important;height:14px!important;min-width:14px!important;fill:none!important;stroke:currentColor!important;stroke-width:2!important;stroke-linecap:round!important;stroke-linejoin:round!important}.watch-later-label{display:block;font-size:12px;line-height:1;font-weight:500;opacity:0;transition:opacity .1s ease}.thumbnail .watch-later-action:hover,.thumbnail .watch-later-action:focus-visible,.sr-thumbnail .watch-later-action:hover,.sr-thumbnail .watch-later-action:focus-visible{width:92px!important}.thumbnail .watch-later-action:hover .watch-later-label,.thumbnail .watch-later-action:focus-visible .watch-later-label,.sr-thumbnail .watch-later-action:hover .watch-later-label,.sr-thumbnail .watch-later-action:focus-visible .watch-later-label{opacity:1}@media(hover:hover) and (min-width:376px){.thumbnail .watch-later-action,.sr-thumbnail .watch-later-action{opacity:0;pointer-events:none}.video-card:hover .thumbnail .watch-later-action,.thumbnail:hover .watch-later-action,.sr-video-card:hover .sr-thumbnail .watch-later-action,.sr-thumbnail:hover .watch-later-action,.thumbnail .watch-later-action:focus,.sr-thumbnail .watch-later-action:focus{opacity:1;pointer-events:auto}}@media(max-width:375px),(hover:none){.thumbnail .watch-later-action,.sr-thumbnail .watch-later-action{opacity:1;pointer-events:auto}}`;
document.head.append(style);
const enhance = (root = document) => buttonsIn(root).forEach(paint);
document.addEventListener('youtuber:library-change', () => enhance());
new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => { if (node instanceof Element) enhance(node); }))).observe(document.documentElement, { childList: true, subtree: true });
enhance();
