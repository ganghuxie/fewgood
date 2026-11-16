export const PLAYER_LOADING_TEXT = '加载中…';
export const PLAYER_PLAY_TEXT = '播放官方音频';
export const PLAYER_RETRY_TEXT = '重试播放官方音频';

export function initAudioPodcastPlayers(roots) {
  const playerRoots = Array.from(roots || []);
  const audios = playerRoots
    .map(root => root.querySelector('[data-audio]'))
    .filter(Boolean);
  const controllers = [];
  let currentAudio = null;

  playerRoots.forEach(root => {
    const audio = root.querySelector('[data-audio]');
    const button = root.querySelector('[data-audio-play]');
    const errorBox = root.querySelector('[data-audio-error]');
    const sourceLink = root.querySelector('[data-audio-source]');
    const audioUrl = root.dataset?.audioUrl;
    if (!audio || !button || !errorBox || !audioUrl) return;

    let pending = false;
    let failed = false;
    let attemptId = 0;

    const cancelPending = () => {
      if (currentAudio === audio) currentAudio = null;
      if (!audio.paused) audio.pause();
      if (!pending) return;
      attemptId += 1;
      pending = false;
      button.disabled = false;
      button.removeAttribute?.('aria-busy');
      button.hidden = false;
      button.textContent = PLAYER_PLAY_TEXT;
      audio.hidden = true;
      if (audio.hasAttribute('src')) {
        audio.removeEventListener('error', showError);
        audio.removeAttribute('src');
        if (typeof audio.load === 'function') audio.load();
        audio.addEventListener('error', showError);
      }
    };

    const pauseOthers = () => {
      controllers.forEach(other => {
        if (other.audio === audio) return;
        other.cancelPending();
      });
      if (currentAudio && currentAudio !== audio) {
        if (!currentAudio.paused) currentAudio.pause();
        currentAudio = null;
      }
    };

    const clearError = () => {
      errorBox.hidden = true;
      if (errorBox.dataset) delete errorBox.dataset.visible;
    };

    const setLoading = () => {
      failed = false;
      pending = true;
      button.hidden = false;
      button.disabled = true;
      button.setAttribute?.('aria-busy', 'true');
      button.textContent = PLAYER_LOADING_TEXT;
      audio.hidden = false;
    };

    const setPlaying = () => {
      pending = false;
      button.disabled = false;
      button.removeAttribute?.('aria-busy');
      button.textContent = PLAYER_PLAY_TEXT;
      button.hidden = true;
      audio.hidden = false;
      currentAudio = audio;
    };

    const showError = () => {
      if (!audio.hasAttribute('src')) return;
      failed = true;
      pending = false;
      if (currentAudio === audio) currentAudio = null;
      audio.pause();
      audio.hidden = true;
      audio.removeEventListener('error', showError);
      audio.removeAttribute('src');
      if (typeof audio.load === 'function') audio.load();
      audio.addEventListener('error', showError);
      button.hidden = false;
      button.disabled = false;
      button.removeAttribute?.('aria-busy');
      button.textContent = PLAYER_RETRY_TEXT;
      errorBox.hidden = false;
      if (errorBox.dataset) errorBox.dataset.visible = '1';
      if (sourceLink) sourceLink.hidden = false;
    };

    button.addEventListener('click', async () => {
      if (pending) return;
      const currentAttempt = ++attemptId;
      clearError();
      pauseOthers();
      setLoading();
      if (!audio.hasAttribute('src')) audio.setAttribute('src', audioUrl);
      try {
        await audio.play();
        if (failed || currentAttempt !== attemptId) {
          if (currentAttempt !== attemptId && !audio.paused) audio.pause();
          return;
        }
        setPlaying();
      } catch {
        if (currentAttempt !== attemptId) return;
        showError();
      }
    });

    audio.addEventListener('play', () => {
      pauseOthers();
      if (!pending) currentAudio = audio;
    });
    audio.addEventListener('error', showError);

    controllers.push({
      audio,
      button,
      errorBox,
      sourceLink,
      cancelPending,
      get pending() {
        return pending;
      },
    });
  });

  return controllers;
}
