import { has, toggleVideo, KEYS } from './library.js';

const paint = button => {
  const active = has(KEYS.watchLater, button.dataset.id);
  button.classList.toggle('is-added', active);
  button.textContent = active ? '✓ 已添加' : '◷ 稍后观看';
  button.setAttribute('aria-pressed', String(active));
};

const enhance = () => document.querySelectorAll('.sr-video-card, .library-list .video-card, .channel .video-card').forEach(card => {
  if (card.querySelector('[data-watch-later]')) return;
  const id = card.querySelector('img')?.dataset.thumbId || card.href.split('/').filter(Boolean).pop();
  const title = card.querySelector('.sr-video-title, .video-title')?.textContent || '';
  const channel = card.querySelector('.sr-video-meta, .video-meta')?.textContent || '';
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'watch-later-action'; button.dataset.watchLater = '';
  button.dataset.id = id; button.dataset.title = title; button.dataset.channel = channel; button.dataset.duration = '0';
  button.addEventListener('click', event => {
    event.preventDefault(); event.stopPropagation();
    toggleVideo(KEYS.watchLater, { id, title, channel, duration: 0 }); paint(button);
  });
  card.querySelector('.thumbnail, .sr-thumbnail')?.append(button); paint(button);
});

if (document.querySelector('.search-page')) {
  const style = document.createElement('style');
  style.textContent = '.sr-video-card,.library-list .video-card,.channel .video-card{position:relative}.sr-thumbnail,.thumbnail{position:relative}.watch-later-action{position:absolute;right:8px;top:8px;z-index:4;border:0;border-radius:14px;background:#0f0f0fcc;color:#fff;padding:6px 10px;font:500 12px inherit;cursor:pointer;opacity:0;pointer-events:none}.sr-video-card:hover .watch-later-action,.sr-video-card:focus-within .watch-later-action,.library-list .video-card:hover .watch-later-action,.library-list .video-card:focus-within .watch-later-action,.channel .video-card:hover .watch-later-action,.channel .video-card:focus-within .watch-later-action,.watch-later-action:focus-visible{opacity:1;pointer-events:auto}.watch-later-action.is-added{background:#49C987;color:#0f0f0f}@media(hover:none){.watch-later-action{opacity:1;pointer-events:auto}}';
  document.head.append(style);
  new MutationObserver(enhance).observe(document.querySelector('[data-results]'), { childList: true });
  enhance();
  document.addEventListener('youtuber:library-change', enhance);
}
