export const SHARE_ORIGIN = 'https://fewgood.io';

const encode = value => encodeURIComponent(String(value ?? ''));

export function shareUrlFor(id) {
  return `${SHARE_ORIGIN}/v/${encode(String(id ?? '').trim())}/`;
}

export function shareIntents({ id, title }) {
  const url = shareUrlFor(id);
  const text = String(title || 'fewgood. 上的一条长视频');
  return [
    { key: 'x', label: 'X', href: `https://twitter.com/intent/tweet?url=${encode(url)}&text=${encode(text)}` },
    { key: 'facebook', label: 'Facebook', href: `https://www.facebook.com/sharer/sharer.php?u=${encode(url)}` },
    { key: 'whatsapp', label: 'WhatsApp', href: `https://api.whatsapp.com/send?text=${encode(`${text} ${url}`)}` },
    { key: 'telegram', label: 'Telegram', href: `https://t.me/share/url?url=${encode(url)}&text=${encode(text)}` },
    { key: 'weibo', label: '微博', href: `https://service.weibo.com/share/share.php?url=${encode(url)}&title=${encode(text)}` },
    { key: 'email', label: '邮件', href: `mailto:?subject=${encode(text)}&body=${encode(`${text}\n${url}`)}` },
  ];
}
