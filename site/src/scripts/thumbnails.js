import { thumbCandidates } from '../lib/format.mjs';

const PLACEHOLDER_MAX_WIDTH = 120;
const attempts = new WeakMap();

const absolute = value => {
  try { return new URL(value, location.href).href; } catch { return ''; }
};

const isThumb = node => node instanceof HTMLImageElement && node.matches('img[data-thumb-id]');

const tryNext = image => {
  const id = image.dataset.thumbId;
  if (!id) return false;
  const tried = attempts.get(image) || new Set();
  attempts.set(image, tried);
  tried.add(absolute(image.currentSrc || image.src));
  for (const candidate of thumbCandidates(id)) {
    const url = absolute(candidate);
    if (!url || tried.has(url)) continue;
    tried.add(url);
    delete image.dataset.thumbUnavailable;
    image.src = candidate;
    return true;
  }
  image.dataset.thumbUnavailable = '1';
  return false;
};

const verify = image => {
  if (!isThumb(image) || !image.complete) return;
  if (image.naturalWidth > PLACEHOLDER_MAX_WIDTH) {
    image.dataset.thumbLoaded = '1';
    delete image.dataset.thumbUnavailable;
    return;
  }
  tryNext(image);
};

const scan = root => {
  if (!root?.querySelectorAll) return;
  if (isThumb(root)) verify(root);
  root.querySelectorAll('img[data-thumb-id]').forEach(verify);
};

document.addEventListener('load', event => verify(event.target), true);
document.addEventListener('error', event => {
  if (isThumb(event.target)) tryNext(event.target);
}, true);

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => scan(document), { once: true });
} else {
  scan(document);
}

new MutationObserver(records => {
  for (const record of records) for (const node of record.addedNodes) {
    if (node.nodeType === Node.ELEMENT_NODE) scan(node);
  }
}).observe(document.documentElement, { childList: true, subtree: true });
