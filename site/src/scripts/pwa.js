const DISMISSED_KEY = 'fewgood-pwa-install-dismissed';
const promptBar = document.querySelector('[data-pwa-install]');
const androidButton = document.querySelector('[data-pwa-install-action]');
const closeButton = document.querySelector('[data-pwa-install-close]');
const isStandalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
// Keep standalone mobile browsers such as MQQBrowser and HuaweiBrowser out of this list.
const isInApp = /MicroMessenger|QQ\/|Weibo|; wv\)|\bGSA\/|Instagram|FBAN|FBAV|Line\//i.test(navigator.userAgent);
const SPLASH_KEY = 'fewgood-splash-shown';
const splash = document.querySelector('[data-pwa-splash]');
const isSplashPreview = new URLSearchParams(window.location.search).get('preview_splash') === '1';
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const splashWasShown = () => { try { return sessionStorage.getItem(SPLASH_KEY) === '1'; } catch { return false; } };
const markSplashShown = () => { try { sessionStorage.setItem(SPLASH_KEY, '1'); } catch {} };
const clearSplashFirstPaint = () => document.documentElement.removeAttribute('data-pwa-splash-first');
const hideSplash = immediate => {
  if (!splash || splash.hidden) return;
  if (!isSplashPreview) markSplashShown();
  clearSplashFirstPaint();
  if (immediate || reducedMotion) { splash.hidden = true; return; }
  splash.classList.add('is-leaving');
  setTimeout(() => { splash.hidden = true; splash.classList.remove('is-leaving'); }, 340);
};
const showSplash = () => {
  if (!splash || (!isStandalone() && !isSplashPreview) || (!isSplashPreview && splashWasShown())) { clearSplashFirstPaint(); return; }
  splash.hidden = false;
  splash.removeAttribute('aria-hidden');
  if (!isSplashPreview) markSplashShown();
  splash.addEventListener('click', () => hideSplash(true), { once: true });
  if (reducedMotion) hideSplash(true);
  else setTimeout(() => hideSplash(false), 1100);
};
showSplash();

let deferredPrompt;
const dismissed = () => {
  try { return localStorage.getItem(DISMISSED_KEY) === '1'; } catch { return false; }
};
const hide = () => { if (promptBar) promptBar.hidden = true; };
const dismiss = () => {
  try { localStorage.setItem(DISMISSED_KEY, '1'); } catch {}
  hide();
};
const manualMode = () => isInApp ? 'inapp' : isIOS ? 'ios' : 'manual';
const show = mode => {
  if (!promptBar || isStandalone() || dismissed()) return;
  if (mode) promptBar.dataset.pwaMode = mode;
  else delete promptBar.dataset.pwaMode;
  promptBar.hidden = false;
};

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const swUrl = `${import.meta.env.BASE_URL}sw.js`.replace(/\/\/+/g, '/');
    navigator.serviceWorker.register(swUrl).catch(() => {});
  }, { once: true });
}

if (closeButton) closeButton.addEventListener('click', dismiss);
if (androidButton) androidButton.addEventListener('click', async () => {
  if (!deferredPrompt) { show(manualMode()); return; }
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  dismiss();
});

if (!isStandalone() && !dismissed()) {
  show(manualMode());
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    deferredPrompt = event;
    show();
  });
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    hide();
  });
}
