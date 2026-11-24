import { KEYS, has, toggleVideo } from './library.js';

export const watchLaterIcon = checked => checked
  ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>'
  : '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></svg>';
const snapshot = button => ({ id: button.dataset.id, title: button.dataset.title, channel: button.dataset.channel, duration: Number(button.dataset.duration) || 0, published_at: button.dataset.publishedAt || '' });
const confirmation = new WeakMap();
const paint = button => { if (confirmation.has(button)) return; const added = has(KEYS.watchLater, button.dataset.id); button.innerHTML = watchLaterIcon(added); button.dataset.tooltip = '稍后再看'; button.setAttribute('aria-label', '稍后再看'); button.setAttribute('aria-pressed', String(added)); };
const buttonsIn = root => [
  ...(root instanceof Element && root.matches('[data-watch-later]') ? [root] : []),
  ...root.querySelectorAll('[data-watch-later]'),
];
document.addEventListener('click', event => {
  const button = event.target.closest('[data-watch-later]');
  if (!button) return;
  event.preventDefault(); event.stopPropagation();
  if (has(KEYS.watchLater, button.dataset.id)) return;
  toggleVideo(KEYS.watchLater, snapshot(button));
  button.innerHTML = watchLaterIcon(true); button.dataset.tooltip = '已加入稍后再看'; confirmation.set(button, true);
  setTimeout(() => { confirmation.delete(button); paint(button); }, 1500);
});
const style = document.createElement('style');
style.textContent = `.thumbnail,.sr-thumbnail{overflow:visible}.thumbnail img,.sr-thumbnail img{border-radius:12px}.thumbnail .watch-later-action,.sr-thumbnail .watch-later-action{position:absolute!important;right:8px!important;top:8px!important;z-index:4;border:0!important;border-radius:50%!important;width:26px!important;height:26px!important;padding:0!important;display:grid!important;place-items:center!important;background:rgba(0,0,0,.5)!important;color:#fff!important;cursor:pointer}.thumbnail .watch-later-action svg,.sr-thumbnail .watch-later-action svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.thumbnail .watch-later-action:hover,.thumbnail .watch-later-action:focus-visible,.sr-thumbnail .watch-later-action:hover,.sr-thumbnail .watch-later-action:focus-visible{background:rgba(0,0,0,.75)!important}.thumbnail .watch-later-action::after,.sr-thumbnail .watch-later-action::after{content:attr(data-tooltip);position:absolute;top:0;left:calc(100% + 6px);z-index:40;padding:4px 8px;border-radius:4px;background:rgba(0,0,0,.85);color:#fff;font-size:12px;line-height:1;white-space:nowrap;opacity:0;visibility:hidden;pointer-events:none;transition:opacity .12s ease,visibility 0s linear .12s;transition-delay:0s}.thumbnail .watch-later-action:hover::after,.thumbnail .watch-later-action:focus-visible::after,.sr-thumbnail .watch-later-action:hover::after,.sr-thumbnail .watch-later-action:focus-visible::after{opacity:1;visibility:visible;transition-delay:150ms}.thumbnail .watch-later-action[data-tooltip-side="left"]::after,.sr-thumbnail .watch-later-action[data-tooltip-side="left"]::after{left:auto;right:calc(100% + 6px)}@media(hover:hover) and (min-width:376px){.thumbnail .watch-later-action,.sr-thumbnail .watch-later-action{opacity:0;pointer-events:none}.video-card:hover .thumbnail .watch-later-action,.thumbnail:hover .watch-later-action,.sr-video-card:hover .sr-thumbnail .watch-later-action,.sr-thumbnail:hover .watch-later-action,.thumbnail .watch-later-action:focus,.sr-thumbnail .watch-later-action:focus{opacity:1;pointer-events:auto}}@media(max-width:375px){.thumbnail .watch-later-action,.sr-thumbnail .watch-later-action{opacity:1;pointer-events:auto}}@media(hover:none){.thumbnail .watch-later-action,.sr-thumbnail .watch-later-action{opacity:1;pointer-events:auto}.thumbnail .watch-later-action::after,.sr-thumbnail .watch-later-action::after{display:none}}`;
document.head.append(style);
const placeTooltips = () => document.querySelectorAll('[data-watch-later]').forEach(button => { const rect = button.getBoundingClientRect(); button.dataset.tooltipSide = rect.right + 130 > window.innerWidth ? 'left' : 'right'; });
const enhance = (root = document) => { buttonsIn(root).forEach(paint); placeTooltips(); };
document.addEventListener('youtuber:library-change', () => enhance());
const watchAddedButtons = new MutationObserver(records => {
  let added = false;
  records.forEach(record => record.addedNodes.forEach(node => {
    if (!(node instanceof Element)) return;
    const buttons = buttonsIn(node);
    if (!buttons.length) return;
    buttons.forEach(paint);
    added = true;
  }));
  if (added) requestAnimationFrame(placeTooltips);
});
watchAddedButtons.observe(document.body, { childList: true, subtree: true });
addEventListener('resize', placeTooltips, { passive: true }); requestAnimationFrame(placeTooltips);
enhance();
