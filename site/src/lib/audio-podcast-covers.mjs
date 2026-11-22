export const CARD_COVER_WIDTHS = [320, 640, 960];
export const CARD_COVER_SIZES = '(min-width: 1280px) 25vw, (min-width: 600px) 50vw, 92vw';
export const SMALL_COVER_WIDTH = 320;

const XYZ_CDN_HOST = 'image.xyzcdn.net';
const XIMALAYA_SOURCE_HOST = 'fdfs.xmcdn.com';
const XIMALAYA_IMAGE_HOST = 'imagev2.xmcdn.com';
const XIMALAYA_PATH = /^\/(?:storages|group\d+)\//;
const XIMALAYA_MOBILE_LARGE = '!op_type=5&upload_type=album&device_type=ios&name=mobile_large&magick=png';

function parsedHttpsUrl(value) {
  if (typeof value !== 'string') return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'https:' ? parsed : null;
  } catch {
    return null;
  }
}

function isXyzCdn(parsed) {
  return parsed?.hostname === XYZ_CDN_HOST && !parsed.username && !parsed.password && !parsed.port;
}

function isXimalayaSource(parsed) {
  return parsed?.hostname === XIMALAYA_SOURCE_HOST
    && !parsed.username
    && !parsed.password
    && !parsed.port
    && XIMALAYA_PATH.test(parsed.pathname)
    && !parsed.pathname.includes('!')
    && !parsed.search;
}

export function coverDisplayUrl(url, { width } = {}) {
  const parsed = parsedHttpsUrl(url);
  if (!parsed || !Number.isInteger(width) || width <= 0) return url;

  if (isXyzCdn(parsed)) {
    if (/imageView2|imageMogr2/i.test(parsed.search)) return url;
    parsed.search = parsed.search
      ? `${parsed.search}&imageView2/2/w/${width}`
      : `?imageView2/2/w/${width}`;
    return parsed.toString();
  }

  // The named 290px rendition is suitable only for the 64px/96px slots.
  if (width <= SMALL_COVER_WIDTH && isXimalayaSource(parsed)) {
    return `https://${XIMALAYA_IMAGE_HOST}${parsed.pathname}${XIMALAYA_MOBILE_LARGE}`;
  }

  return url;
}

export function coverSrcset(url, widths) {
  const parsed = parsedHttpsUrl(url);
  if (!isXyzCdn(parsed) || /imageView2|imageMogr2/i.test(parsed.search)) return undefined;
  const candidates = (widths || []).filter(width => Number.isInteger(width) && width > 0);
  return candidates.length
    ? candidates.map(width => `${coverDisplayUrl(url, { width })} ${width}w`).join(', ')
    : undefined;
}
