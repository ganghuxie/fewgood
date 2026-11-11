export const TOPIC_SUBSCRIBED_LABEL = '✓ 已订阅，在我的空间';

export const topicSubscribeLabel = topicName => `+ 订阅「${topicName}」栏目`;
export const topicSubscribeTitle = topicName => `订阅后，「${topicName}」会作为一栏出现在我的空间`;

export function paintTopicChip(button, active, topicName) {
  const name = topicName || button?.dataset?.topicName || '';
  if (!button) return;
  button.classList.toggle('is-subscribed', Boolean(active));
  button.textContent = active ? TOPIC_SUBSCRIBED_LABEL : topicSubscribeLabel(name);
  button.title = topicSubscribeTitle(name);
  button.setAttribute('aria-label', topicSubscribeTitle(name));
}
