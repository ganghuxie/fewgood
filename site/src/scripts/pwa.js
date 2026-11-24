const DISMISSED_KEY = 'fewgood-pwa-install-dismissed';
const promptBar = document.querySelector('[data-pwa-install]');
const androidButton = document.querySelector('[data-pwa-install-action]');
const closeButton = document.querySelector('[data-pwa-install-close]');
const isStandalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const isNarrow = () => window.matchMedia('(max-width: 700px)').matches;
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
// Keep standalone mobile browsers such as MQQBrowser and HuaweiBrowser out of this list.
const isInApp = /MicroMessenger|QQ\/|Weibo|; wv\)|\bGSA\/|Instagram|FBAN|FBAV|Line\//i.test(navigator.userAgent);
const SPLASH_KEY = 'fewgood-splash-shown';
const splash = document.querySelector('[data-pwa-splash]');
const isSplashPreview = new URLSearchParams(window.location.search).get('preview_splash') === '1';
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const splashWasShown = () => { try { return sessionStorage.getItem(SPLASH_KEY) === '1'; } catch { return false; } };
const markSplashShown = () => { try { sessionStorage.setItem(SPLASH_KEY, '1'); } catch {} };
const hideSplash = immediate => {
  if (!splash || splash.hidden) return;
  markSplashShown();
  if (immediate || reducedMotion) { splash.hidden = true; return; }
  splash.classList.add('is-leaving');
  setTimeout(() => { splash.hidden = true; }, 340);
};
const showSplash = () => {
  if (!splash || (!isStandalone() && !isSplashPreview) || (!isSplashPreview && splashWasShown())) return;
  splash.hidden = false;
  splash.addEventListener('click', () => hideSplash(true), { once: true });
  if (!isSplashPreview && !reducedMotion) setTimeout(() => hideSplash(false), 1100);
  else if (!isSplashPreview) hideSplash(true);
};
showSplash();

let deferredPrompt;
let manualTimer;
const dismissed = () => {
  try { return localStorage.getItem(DISMISSED_KEY) === '1'; } catch { return false; }
};
const hide = () => { if (promptBar) promptBar.hidden = true; };
const dismiss = () => {
  clearTimeout(manualTimer);
  try { localStorage.setItem(DISMISSED_KEY, '1'); } catch {}
  hide();
};
const show = () => {
  if (promptBar && !isStandalone() && !dismissed()) promptBar.hidden = false;
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
  const choice = await deferredPrompt.userChoice;
  deferredPrompt = null;
  if (choice?.outcome !== 'accepted') dismiss();
  hide();
});

if (!isStandalone() && !dismissed()) {
  if (isInApp) {
    if (promptBar) promptBar.dataset.pwaMode = 'inapp';
    show();
  } else if (isIOS) {
    if (promptBar) promptBar.dataset.pwaMode = 'ios';
    show();
  } else if (/Android/i.test(navigator.userAgent)) {
    window.addEventListener('beforeinstallprompt', event => {
      event.preventDefault();
      deferredPrompt = event;
      clearTimeout(manualTimer);
      if (promptBar) delete promptBar.dataset.pwaMode;
      show();
    });
    window.addEventListener('appinstalled', () => {
      clearTimeout(manualTimer);
      deferredPrompt = null;
      hide();
    });
    manualTimer = setTimeout(() => {
      if (!deferredPrompt && !isStandalone() && !dismissed() && isNarrow()) {
        if (promptBar) promptBar.dataset.pwaMode = 'manual';
        show();
      }
    }, 2500);
  } else {
    window.addEventListener('beforeinstallprompt', event => {
      event.preventDefault();
      deferredPrompt = event;
      show();
    });
  }
}
