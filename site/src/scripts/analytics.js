import posthog from 'posthog-js';

const key = import.meta.env.PUBLIC_POSTHOG_KEY?.trim();
const host = import.meta.env.PUBLIC_POSTHOG_HOST?.trim() || 'https://us.i.posthog.com';
const dnt = [navigator.doNotTrack, window.doNotTrack, navigator.msDoNotTrack]
  .some(value => ['1', 'yes'].includes(String(value ?? '').toLowerCase()));
let inited = false;

if (key && !dnt) {
  posthog.init(key, {
    api_host: host,
    autocapture: true,
    capture_pageview: 'history_change',
    disable_session_recording: true,
    respect_dnt: true,
  });
  inited = true;
}

export function track(event, props) {
  if (inited) posthog.capture(event, props);
}

export function identify(id) {
  if (inited && id) posthog.identify(id);
}

export function reset() {
  if (inited) posthog.reset();
}

document.addEventListener('click', event => {
  const link = event.target.closest('a');
  if (!link) return;
  const videoCard = link.closest('.video-card');
  if (videoCard) {
    const match = link.href.match(/\/v\/([^/?#]+)/);
    const videoId = match?.[1] || (link.hostname === 'www.youtube.com' || link.hostname === 'youtube.com' ? new URL(link.href).searchParams.get('v') : null);
    if (videoId) {
      const grid = videoCard.closest('[data-feed-grid], [data-channel-grid], [data-results], [data-list]');
      const cards = grid ? [...grid.querySelectorAll('.video-card')] : [];
      const feed = grid?.dataset.section || (grid?.id === 'following-feed' ? 'following' : grid?.dataset.kind || 'search');
      track('video_click', { video_id: videoId, feed, position: Math.max(0, cards.indexOf(videoCard)) });
    }
  }
  if (link.hostname === 'www.youtube.com' || link.hostname === 'youtube.com') {
    const videoId = new URL(link.href).searchParams.get('v');
    if (videoId) track('open_youtube', { video_id: videoId });
  }
});
