import { renderSVG } from 'uqr';
import { shareIntents, shareUrlFor } from '../lib/share.mjs';
import { showPrompt } from './prompts.js';

const ICONS = {
  wechat: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9.2 4C5.2 4 2 6.7 2 10c0 1.9 1.1 3.6 2.9 4.7l-.7 2.1 2.4-1.2c.8.2 1.7.4 2.6.4.2 0 .5 0 .7-.1-.1-.4-.2-.8-.2-1.2 0-3.2 3.1-5.7 6.9-5.7h.2C16.2 6 13 4 9.2 4zm-2.5 3.1a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm5 0a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/><path fill="currentColor" d="M22 14.8c0-2.7-2.7-4.9-5.9-4.9s-5.9 2.2-5.9 4.9 2.7 4.9 5.9 4.9c.7 0 1.4-.1 2.1-.3l2 1-.6-1.8c1.5-.9 2.4-2.3 2.4-3.8zm-7.8-1.2a.8.8 0 1 1 0-1.6.8.8 0 0 1 0 1.6zm3.8 0a.8.8 0 1 1 0-1.6.8.8 0 0 1 0 1.6z"/></svg>',
  x: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M17.7 3h3.1l-6.8 7.8L22 21h-6.3l-4.9-6.4L5.2 21H2l7.3-8.4L2 3h6.4l4.4 5.8L17.7 3zm-1.1 16.1h1.7L7.4 4.8H5.6l11 14.3z"/></svg>',
  facebook: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M14 8.5V6.8c0-.7.5-.9.9-.9h2.2V3h-3c-3.2 0-3.9 2.4-3.9 3.9v1.6H7.5v3h2.7V21H14v-9.5h2.8l.4-3H14z"/></svg>',
  whatsapp: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M20.5 3.5A11.4 11.4 0 0 0 3.9 17.3L2.5 22l4.9-1.3A11.5 11.5 0 0 0 12 22h.1c6.3 0 11.4-5.1 11.4-11.4 0-3-1.2-5.9-3-7.1zm-8.4 16.9c-1.5 0-3-.4-4.3-1.2l-.3-.2-2.9.8.8-2.8-.2-.3a9.3 9.3 0 1 1 6.9 3.7z"/><path fill="currentColor" d="M16.7 14.3l-1.2-.6c-.2-.1-.3-.1-.4.1l-.5.7c-.1.2-.2.2-.4.1-.4-.2-1.5-.6-2.8-1.8-1-.9-1.2-1.5-1.3-1.7-.1-.2 0-.3.1-.4l.3-.4c.1-.1.1-.2.2-.4.1-.1 0-.3 0-.4l-.6-1.4c-.2-.4-.3-.4-.4-.4h-.4c-.2 0-.4.1-.6.3-.2.2-.8.8-.8 1.9s.8 2.2.9 2.4c.1.2 1.6 2.5 3.9 3.5 2.3 1 2.3.7 2.7.6.4 0 1.3-.5 1.5-1.1.2-.5.2-1 .1-1.1-.1-.1-.2-.1-.4-.2z"/></svg>',
  telegram: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M21.7 4.3 2.9 11.5c-1 .4-1 1.4 0 1.7l4.8 1.5 1.8 5.6c.2.6.4.7 1 .3l2.7-2 5.5 4.1c.7.4 1.2.2 1.4-.6l2.5-11.8c.3-1.2-.4-1.7-1.4-1.3zM8.4 13.9l9.8-6.2c.4-.2.7.1.4.4l-8 7.3-.3 3-1.9-4.5z"/></svg>',
  weibo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9.7 19.8c-4.3 0-7.7-2-7.7-4.7 0-1.4.9-3 2.5-4.5 2.2-2 4.8-2.9 5.8-2 .4.4.4 1 .1 1.8-.1.4.1.5.4.3 1.7-.7 3.1-.8 3.6.1.3.5.2 1.2-.1 2 .1.1.3.2.4.3 1.5.6 1.5 2.1.6 3.4-1.3 1.9-4 3.3-5.6 3.3z"/><path fill="#fff" d="M9.1 12.2c-2.3-.2-4.2 1.1-4.5 2.8-.3 1.8 1.2 3.4 3.6 3.6 2.4.2 4.6-1.2 4.9-3 .3-1.8-1.4-3.2-4-3.4zm-.7 4.9c-.9.1-1.7-.4-1.8-1.1-.1-.7.6-1.3 1.5-1.4.9-.1 1.7.4 1.8 1.1.1.7-.6 1.3-1.5 1.4z"/><path fill="currentColor" d="M21.8 9.1a1 1 0 0 0-1 .9c-.1.8-.7 1.4-1.5 1.5a1 1 0 1 0 .2 2c1.8-.2 3.2-1.7 3.3-3.5a1 1 0 0 0-1-.9zm-1.1-3.9a1 1 0 0 0-.1 2c1.6.2 2.8 1.5 2.9 3.1a1 1 0 0 0 2-.1c-.2-2.6-2.2-4.7-4.8-5z"/></svg>',
  email: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm9 8L4 7v10h16V7l-8 6z"/></svg>',
  system: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18 16a3 3 0 0 0-2.4 1.2l-6.2-3.1a3 3 0 0 0 0-2.2l6.2-3.1A3 3 0 1 0 15 6c0 .3 0 .5.1.8L8.9 9.9A3 3 0 1 0 9 14.1l6.1 3.1c-.1.3-.1.5-.1.8a3 3 0 1 0 3-2z"/></svg>',
};

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

let root = null;
let modal = null;
let icons = null;
let linkField = null;
let copyButton = null;
let scrollButton = null;
let mainPanel = null;
let wechatPanel = null;
let qrHost = null;
let closeButton = null;
let currentId = '';
let currentUrl = '';
let currentTitle = '';
let lastFocus = null;
let copyTimer = null;

function canonicalIdFromLocation() {
  const match = location.pathname.match(/\/v\/([^/]+)\//);
  return match ? decodeURIComponent(match[1]) : '';
}

function iconMarkup(key, label) {
  return `<span class="share-icon-disc share-icon-${key}" aria-hidden="true">${ICONS[key] || ''}</span><span class="share-icon-label">${label}</span>`;
}

function iconButton(key, label, extraClass = '') {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `share-icon-item share-icon-button ${extraClass}`.trim();
  button.setAttribute('aria-label', label);
  button.innerHTML = iconMarkup(key, label);
  return button;
}

function iconLink(key, label, href) {
  const anchor = document.createElement('a');
  anchor.className = 'share-icon-item';
  anchor.href = href;
  anchor.target = '_blank';
  anchor.rel = 'noopener noreferrer';
  anchor.setAttribute('aria-label', label);
  anchor.innerHTML = iconMarkup(key, label);
  return anchor;
}

function updateScrollButton() {
  if (!icons || !scrollButton) return;
  scrollButton.hidden = icons.scrollWidth <= icons.clientWidth + 2;
  scrollButton.classList.toggle('is-at-end', icons.scrollLeft + icons.clientWidth >= icons.scrollWidth - 2);
}

function showMainPanel() {
  mainPanel.hidden = false;
  wechatPanel.hidden = true;
  qrHost.innerHTML = '';
}

function showWechatPanel() {
  mainPanel.hidden = true;
  wechatPanel.hidden = false;
  qrHost.innerHTML = renderSVG(currentUrl, { border: 2, ecc: 'M' });
  wechatPanel.querySelector('[data-share-wechat-back]')?.focus();
}

function closeModal() {
  if (!root || root.hidden) return;
  root.hidden = true;
  document.body.classList.remove('share-modal-open');
  showMainPanel();
  if (lastFocus && lastFocus.isConnected) lastFocus.focus();
  lastFocus = null;
}

async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const field = document.createElement('textarea');
  field.value = value;
  field.setAttribute('readonly', '');
  field.style.position = 'fixed';
  field.style.opacity = '0';
  document.body.append(field);
  field.select();
  const copied = document.execCommand('copy');
  field.remove();
  if (!copied) throw new Error('copy');
}

async function copyCurrentUrl() {
  try {
    await copyText(currentUrl);
    copyButton.textContent = '已复制';
    copyButton.classList.add('is-copied');
    showPrompt('已复制', { ttl: 2200 });
    clearTimeout(copyTimer);
    copyTimer = setTimeout(() => {
      copyButton.textContent = '复制';
      copyButton.classList.remove('is-copied');
    }, 2200);
  } catch {
    showPrompt('复制失败，请从链接框复制。', { ttl: 5000 });
  }
}

function renderIcons() {
  icons.innerHTML = '';
  const wechat = iconButton('wechat', '微信', 'share-icon-wechat');
  wechat.addEventListener('click', showWechatPanel);
  icons.append(wechat);

  shareIntents({ id: currentId, title: currentTitle }).forEach(intent => {
    icons.append(iconLink(intent.key, intent.label, intent.href));
  });

  if (typeof navigator.share === 'function') {
    const system = iconButton('system', '系统分享', 'share-icon-system');
    system.addEventListener('click', () => {
      navigator.share({ title: currentTitle, url: currentUrl }).then(() => closeModal()).catch(error => {
        if (error?.name !== 'AbortError') showPrompt('系统分享暂不可用', { ttl: 4000 });
      });
    });
    icons.append(system);
  }

  requestAnimationFrame(updateScrollButton);
}

function trapFocus(event) {
  if (event.key !== 'Tab' || !root || root.hidden) return;
  const nodes = [...modal.querySelectorAll(FOCUSABLE)].filter(node => !node.hidden && node.offsetParent !== null);
  if (!nodes.length) return;
  const first = nodes[0];
  const last = nodes[nodes.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function ensureModal() {
  if (root) return root;
  root = document.createElement('div');
  root.className = 'share-modal-root';
  root.setAttribute('data-share-modal-root', '');
  root.hidden = true;
  root.innerHTML = `<div class="share-modal-backdrop" data-share-backdrop></div><div class="share-modal" role="dialog" aria-modal="true" aria-labelledby="share-modal-title" tabindex="-1"><div class="share-modal-head"><h2 id="share-modal-title">分享</h2><button class="share-modal-close" type="button" data-share-close aria-label="关闭">×</button></div><div class="share-modal-body" data-share-main><div class="share-icons-wrap"><div class="share-icons" data-share-icons></div><button class="share-scroll" type="button" data-share-scroll aria-label="查看更多分享方式" hidden>›</button></div><div class="share-link-row"><input class="share-link" type="text" readonly aria-label="分享链接" data-share-link><button class="share-copy" type="button" data-share-copy>复制</button></div></div><div class="share-wechat" data-share-wechat hidden><button class="share-wechat-back" type="button" data-share-wechat-back>‹ 返回</button><div class="share-qr" data-share-qr aria-label="微信分享二维码"></div><p>微信扫码分享</p></div></div>`;
  document.body.append(root);

  modal = root.querySelector('.share-modal');
  icons = root.querySelector('[data-share-icons]');
  linkField = root.querySelector('[data-share-link]');
  copyButton = root.querySelector('[data-share-copy]');
  scrollButton = root.querySelector('[data-share-scroll]');
  mainPanel = root.querySelector('[data-share-main]');
  wechatPanel = root.querySelector('[data-share-wechat]');
  qrHost = root.querySelector('[data-share-qr]');
  closeButton = root.querySelector('[data-share-close]');

  closeButton.addEventListener('click', closeModal);
  root.querySelector('[data-share-backdrop]').addEventListener('click', closeModal);
  copyButton.addEventListener('click', copyCurrentUrl);
  linkField.addEventListener('focus', () => linkField.select());
  linkField.addEventListener('click', () => linkField.select());
  root.querySelector('[data-share-wechat-back]').addEventListener('click', showMainPanel);
  scrollButton.addEventListener('click', () => icons.scrollBy({ left: Math.max(200, icons.clientWidth * 0.8), behavior: 'smooth' }));
  icons.addEventListener('scroll', updateScrollButton, { passive: true });
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(updateScrollButton).observe(icons);

  document.addEventListener('keydown', event => {
    if (!root || root.hidden) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeModal();
      return;
    }
    trapFocus(event);
  });

  return root;
}

function openModal(trigger) {
  ensureModal();
  lastFocus = trigger || document.activeElement;
  currentId = trigger?.dataset?.shareId || canonicalIdFromLocation();
  currentUrl = shareUrlFor(currentId);
  currentTitle = trigger?.dataset?.shareTitle || document.title.replace(/\s*·\s*fewgood\.?\s*$/i, '') || document.title;
  linkField.value = currentUrl;
  copyButton.textContent = '复制';
  copyButton.classList.remove('is-copied');
  renderIcons();
  showMainPanel();
  root.hidden = false;
  document.body.classList.add('share-modal-open');
  requestAnimationFrame(() => {
    updateScrollButton();
    linkField.value = currentUrl;
    closeButton.focus();
  });
}

export function initShareModal(scope = document) {
  scope.querySelectorAll('[data-share]').forEach(trigger => {
    if (trigger.dataset.shareReady === '1') return;
    trigger.dataset.shareReady = '1';
    trigger.addEventListener('click', event => {
      event.preventDefault();
      openModal(trigger);
    });
  });
}
