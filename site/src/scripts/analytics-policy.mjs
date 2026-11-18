import { isAudioDebugEnabled } from '../lib/audio-debug-query.mjs';

export function shouldInitPostHog({ key, dnt, localHost, search }) {
  return Boolean(key && !dnt && !localHost && !isAudioDebugEnabled(search));
}
