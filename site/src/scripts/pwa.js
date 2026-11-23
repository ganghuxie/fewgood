const DISMISSED_KEY = 'fewgood-pwa-install-dismissed';
const promptBar = document.querySelector('[data-pwa-install]');
const androidButton = document.querySelector('[data-pwa-install-action]');
const closeButton = document.querySelector('[data-pwa-install-close]');
const isStandalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const isNarrow = () => window.matchMedia('(max-width: 700px)').matches;
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const isInApp = /MicroMessenger|QQ\/|Weibo|; wv\)|\bGSA\/|Instagram|FBAN|FBAV|Line\//i.test(navigator.userAgent);

let deferredPrompt;
const dismissed = () => {
  try { return localStorage.getItem(DISMISSED_KEY) === '1'; } catch { return false; }
};
const hide = () => { if (promptBar) promptBar.hidden = true; };
const dismiss = () => {
  try { localStorage.setItem(DISMISSED_KEY, '1'); } catch {}
  hide();
};
const show = () => {
  if (promptBar && !isStandalone() && !dismissed() && isNarrow()) promptBar.hidden = false;
};

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const swUrl = `${import.meta.env.BASE_URL}sw.js`.replace(/\/\/+/g, '/');
    navigator.serviceWorker.register(swUrl).catch(() => {});
  }, { once: true });
}

if (closeButton) closeButton.addEventListener('click', dismiss);
if (androidButton) androidButton.addEventListener('click', async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  hide();
});

if (!isStandalone() && !dismissed()) {
  if (isInApp) {
    if (promptBar) promptBar.dataset.pwaMode = 'inapp';
    show();
  } else if (isIOS) {
    if (promptBar) promptBar.dataset.pwaMode = 'ios';
    show();
  } else {
    window.addEventListener('beforeinstallprompt', event => {
      event.preventDefault();
      deferredPrompt = event;
      show();
    });
  }
}
