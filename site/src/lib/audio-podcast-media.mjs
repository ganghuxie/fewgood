const XIMALAYA_JUMPER_HOST = 'jt.ximalaya.com';
const VERIFIED_MEDIA_HOSTS = new Set(['aod.cos.tx.xmcdn.com']);

export function playbackAudioUrl(value) {
  if (typeof value !== 'string' || !value) return '';
  let source;
  try {
    source = new URL(value);
  } catch {
    return '';
  }
  if (source.protocol !== 'https:') return '';
  if (source.hostname !== XIMALAYA_JUMPER_HOST) return source.href;

  const embedded = source.searchParams.get('jt');
  if (!embedded) return source.href;
  try {
    const target = new URL(embedded);
    if (
      target.protocol === 'https:' &&
      VERIFIED_MEDIA_HOSTS.has(target.hostname) &&
      !target.username && !target.password &&
      !target.port &&
      /\.m4a$/i.test(target.pathname)
    ) return target.href;
  } catch {
    // Retain the official enclosure when its embedded target is malformed.
  }
  return source.href;
}
