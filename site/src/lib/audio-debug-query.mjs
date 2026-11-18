export function isAudioDebugEnabled(search) {
  return new URLSearchParams(search).get('audio_debug') === '1';
}
