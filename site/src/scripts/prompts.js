const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

export function dismissPrompt(node) {
  if (!node) return;
  node.classList.add('soft-prompt-leaving');
  setTimeout(() => node.remove(), 180);
}

export function showPrompt(message, options = {}) {
  document.querySelector('[data-soft-prompt]')?.remove();
  const toast = document.createElement('div');
  toast.className = 'soft-prompt';
  toast.setAttribute('data-soft-prompt', '');
  toast.setAttribute('role', 'status');
  toast.innerHTML = `<span>${esc(message)}</span>${options.actions ? `<span class="soft-prompt-actions">${options.actions.map(action => `<button type="button" data-action="${esc(action.id)}">${esc(action.label)}</button>`).join('')}</span>` : ''}<button class="soft-prompt-close" type="button" aria-label="关闭" data-soft-prompt-close>×</button>`;
  document.body.append(toast);
  toast.querySelector('[data-soft-prompt-close]')?.addEventListener('click', () => dismissPrompt(toast));
  if (options.actions) {
    toast.querySelectorAll('[data-action]').forEach(button => {
      button.addEventListener('click', () => {
        const action = options.actions.find(item => item.id === button.dataset.action);
        if (action) action.onClick();
      });
    });
  }
  if (options.ttl !== 0) setTimeout(() => { if (toast.isConnected) dismissPrompt(toast); }, options.ttl ?? 12000);
  return toast;
}
