import { isAudioDebugEnabled } from './audio-debug-query.mjs';

const MEDIA_EVENTS = ['loadstart', 'loadedmetadata', 'canplay', 'play', 'playing', 'waiting', 'stalled', 'abort'];
const MEDIA_TYPES = ['audio/mp4', 'audio/mp4; codecs="mp4a.40.2"', 'audio/aac', 'audio/x-m4a', 'audio/mpeg'];
const MAX_EVENTS = 20;
const clip = value => typeof value === 'string' ? value.slice(0, 200) : '';

function parseSource(value) {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

function errorText(value, source) {
  if (typeof value !== 'string') return '';
  // Media errors can include the enclosure URL. Strip URLs and any standalone
  // path, credentials, or query values from the configured source.
  let safe = value.replace(/(?:[a-z][a-z\d+.-]*:)?\/\/[^\s<>"']+/gi, '[地址已省略]');
  if (source) {
    const parts = [source.pathname, source.search, source.hash, source.username,
      source.password, ...source.searchParams.values()];
    for (const part of parts) {
      if (part && part !== '/') safe = safe.replaceAll(part, '[已省略]');
    }
  }
  return clip(safe);
}

// The report lives in this page. Layout's existing Cloudflare Web Analytics
// tag may still send its ordinary page-level beacon in debug mode.
export function initAudioPodcastDebug(roots, {
  search = window.location.search,
  document: doc = document,
  browser = navigator,
  now = () => performance.now(),
} = {}) {
  if (!isAudioDebugEnabled(search)) return undefined;
  const diagnostics = new Map();

  for (const root of roots) {
    const audio = root.querySelector('[data-audio]');
    if (!audio || !root.dataset.audioUrl) continue;

    const section = doc.createElement('section');
    const heading = doc.createElement('h2');
    heading.textContent = '诊断模式';
    const note = doc.createElement('p');
    note.textContent = '这是诊断模式，不是修复完成。记录仅保存在本机，不会自动上传。复制结果后请自愿提供给我们。';
    const copy = doc.createElement('button');
    copy.type = 'button';
    copy.textContent = '复制诊断结果';
    const status = doc.createElement('p');
    status.setAttribute('role', 'status');
    const output = doc.createElement('pre');
    output.style.whiteSpace = 'pre-wrap';
    output.style.overflowWrap = 'anywhere';
    section.append(heading, note, copy, status, output);
    root.after(section);

    const source = parseSource(root.dataset.audioUrl);
    const report = {
      sourceHostname: clip(source?.hostname),
      userAgent: clip(browser.userAgent),
      platform: clip(browser.platform),
      online: browser.onLine,
      canPlayType: Object.fromEntries(MEDIA_TYPES.map(type => [type, clip(audio.canPlayType(type))])),
      events: [],
    };
    let startedAt;
    let attempt = 0;
    const render = () => {
      output.textContent = JSON.stringify(report, null, 2);
    };
    const record = (type, fields) => {
      report.online = browser.onLine;
      report.events.push({
        type,
        attempt,
        ms: Math.round(now() - startedAt),
        networkState: audio.networkState,
        readyState: audio.readyState,
        ...fields,
      });
      if (report.events.length > MAX_EVENTS) report.events.shift();
      render();
    };

    for (const type of MEDIA_EVENTS) {
      audio.addEventListener(type, () => {
        if (startedAt !== undefined && audio.hasAttribute('src')) record(type);
      });
    }
    diagnostics.set(audio, {
      start() {
        startedAt = now();
        attempt += 1;
        record('click');
      },
      fail({ type, playRejection }) {
        if (startedAt === undefined) return;
        const mediaError = audio.error;
        record(type, {
          mediaError: mediaError ? {
            code: mediaError.code,
            message: errorText(mediaError.message, source),
          } : null,
          ...(type === 'play-rejection' && {
            playRejection: {
              name: errorText(playRejection?.name, source),
              message: errorText(playRejection?.message ?? playRejection, source),
            },
          }),
        });
        startedAt = undefined;
      },
    });

    copy.addEventListener('click', async () => {
      try {
        await browser.clipboard.writeText(output.textContent);
        status.textContent = '已复制诊断结果。';
      } catch {
        status.textContent = '无法自动复制，请选中下方文字并手动复制。';
      }
    });
    render();
  }

  return {
    onPlayAttempt: audio => diagnostics.get(audio)?.start(),
    onBeforeShowError: failure => diagnostics.get(failure.audio)?.fail(failure),
  };
}
