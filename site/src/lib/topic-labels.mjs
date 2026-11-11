export const TOPIC_SUBSCRIBED_LABEL = '✓ 已订阅';
export const TOPIC_DEFAULT_LABEL = '+订阅栏目';

export const topicSubscribeLabel = () => TOPIC_DEFAULT_LABEL;
export const topicSubscribeTitle = topicName => `订阅「${topicName}」栏目，它会作为一栏出现在我的空间`;

export function paintTopicChip(button, active, topicName) {
  const name = topicName || button?.dataset?.topicName || '';
  if (!button) return;
  button.classList.toggle('is-subscribed', Boolean(active));
  button.textContent = active ? TOPIC_SUBSCRIBED_LABEL : topicSubscribeLabel(name);
  button.title = topicSubscribeTitle(name);
  button.setAttribute('aria-label', topicSubscribeTitle(name));
  button.setAttribute('aria-pressed', String(Boolean(active)));
}
