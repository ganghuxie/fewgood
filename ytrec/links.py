import html
import re
from urllib.parse import urlparse, parse_qs, unquote

ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
URL = re.compile(r'(?<![A-Za-z0-9_.-])(?:https?://|//)?(?:[\w-]+\.)*(?:youtube\.com|youtu\.be|youtube-nocookie\.com)(?::\d+)?[^\s<>"\']*', re.I)

def video_id(url, depth=0):
    if depth > 3:
        return None
    url = html.unescape(url).strip().rstrip('.,);]')
    parsed = urlparse(url if '://' in url else 'https://' + url.lstrip('/'))
    host = (parsed.hostname or '').lower()
    query = parse_qs(parsed.query)
    path = parsed.path.strip('/').split('/')
    value = None
    if host in {'youtu.be', 'www.youtu.be'}:
        value = path[0].split('&', 1)[0]
    elif host in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'}:
        if path[0] == 'attribution_link':
            target = query.get('u', [''])[0]
            if target.startswith('/'):
                target = 'https://youtube.com' + target
            return video_id(target, depth + 1)
        if path[0] == 'watch':
            value = query.get('v', [None])[0]
        elif len(path) == 2 and path[0] in {'embed', 'shorts', 'live', 'v'}:
            value = path[1]
    return value if value and ID.fullmatch(value) else None

def extract_ids(text):
    text = html.unescape(html.unescape(text or ''))
    return {v for match in URL.finditer(text) if (v := video_id(match.group()))}

def plain(text):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ', text or '')).split())
