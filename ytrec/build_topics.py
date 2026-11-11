"""Cluster the HN pool into data-driven topics and emit topic artifacts.

No LLM calls: topic membership, keywords, and aliases come from TF-IDF clustering
of video titles, channels, and quote text. The display signal (used for the
topic id and Chinese name) is the cluster's most discriminative phrase/token;
only the signal -> Chinese-name translation is curated.
"""
import json
import math
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core import iso_now, published_at_dt

STOPWORDS = set('''a an and are as at be but by can could did do does for from had has have he her hers
him his how i if in into is it its just like may me more most much my no not of on or our ours out
over per she should so some such than that the their them then there these they this those to too
under up us very was we were what when where which while who will with would you your yours one two
three new good great people time make made use used get got see know think say said way first last
many s t re ve ll don isn aren doesn didn wasn weren couldn shouldn www http https com youtube
watch video videos channel youtu be about things need works want actually here why bad wrong hard
really years hours ever part using best world other something even every'''.split())

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-+#./][a-z0-9]+)*")
URL_RE = re.compile(r"https?://\S+|www\.\S+|\byoutu\.be\S*")
MIN_CLUSTER = 8
MIN_KEYWORDS = 5

# Curated display mapping keyed by the dominant English signal a cluster surfaces.
SIGNAL_META = {
    '3blue1brown': ('math', '数学与可视化'), 'grey': ('math', '数学与可视化'), 'cgp': ('math', '数学与可视化'),
    'cgp grey': ('math', '数学与可视化'),
    'go': ('tech-life', '科技与生活'), 'quite': ('tech-life', '科技与生活'),
    'javascript': ('programming', '编程思想'), 'programming': ('programming', '编程思想'),
    'light': ('maker', '动手与黑客'), 'artificial': ('maker', '动手与黑客'),
    'american': ('game-dev', '游戏开发'), 'festival': ('game-dev', '游戏开发'), 'gdc': ('game-dev', '游戏开发'),
    'veritasium': ('science', '科技科普'), 'fraud': ('science', '科技科普'),
    'lecture': ('classic-talks', '经典演讲'), 'stanford': ('classic-talks', '经典演讲'), 'commencement': ('classic-talks', '经典演讲'),
    'modern': ('computing-history', '计算机历史'), 'engineer': ('computing-history', '计算机历史'),
    'change': ('climate', '气候与环境'), 'climate': ('climate', '气候与环境'),
    'click': ('tech-videos', '科技深度解析'),
    'suckerpinch': ('games', '游戏与逆向工程'), 'games': ('games', '游戏与逆向工程'),
    'tom': ('tech-review', '科技评论'), 'scott': ('tech-review', '科技评论'), 'computerphile': ('tech-review', '科技评论'),
    'tom scott': ('tech-review', '科技评论'),
    'week tonight': ('commentary', '深度评论'), 'tonight john': ('commentary', '深度评论'), 'oliver hbo': ('commentary', '深度评论'), 'john': ('commentary', '深度评论'),
    'combinator': ('startups', '创业与硅谷'), 'startup': ('startups', '创业与硅谷'), 'startup school': ('startups', '创业与硅谷'),
    'rich hickey': ('clojure', '函数式编程'), 'rich': ('clojure', '函数式编程'), 'clojure': ('clojure', '函数式编程'),
    'building': ('ai', '人工智能'), 'karpathy': ('ai', '人工智能'), 'gpt': ('ai', '人工智能'), 'ai': ('ai', '人工智能'),
    'alan': ('pioneers', '计算机先驱访谈'), 'kay': ('pioneers', '计算机先驱访谈'), 'alan kay': ('pioneers', '计算机先驱访谈'),
    'gear': ('documentary', '纪录片'), 'full documentary': ('documentary', '纪录片'), 'documentary': ('documentary', '纪录片'),
    'work': ('ideas', '人物与思想'), 'being': ('ideas', '人物与思想'),
    'introduction': ('conferences', '技术会议'), 'conferences': ('conferences', '技术会议'), 'goto': ('conferences', '技术会议'),
    'linux.conf.au': ('systems', '系统与软件设计'), 'science': ('systems', '系统与软件设计'),
    'mit': ('mit', 'MIT 公开课'), 'opencourseware': ('mit', 'MIT 公开课'),
    'cppcon': ('cpp', 'C++ 与系统编程'), 'cppcon chandler': ('cpp', 'C++ 与系统编程'),
    'movie': ('language-history', '编程语言史'), 'ii': ('language-history', '编程语言史'), 'erlang': ('language-history', '编程语言史'),
    'space': ('future-programming', '未来编程'), 'bret': ('future-programming', '未来编程'),
}


def tokenize(text):
    text = URL_RE.sub(' ', text or '')
    out = []
    for token in TOKEN_RE.findall(text.lower()):
        token = token.strip('.-_#+')
        if len(token) < 2 or token in STOPWORDS or token.isdigit():
            continue
        out.append(token)
    return out


def document_tokens(video):
    title = video.get('title') or ''
    channel = video.get('channel') or ''
    quotes = ' '.join(q.get('text') or '' for q in video.get('quotes') or [])
    return tokenize(title) * 2 + tokenize(channel) * 2 + tokenize(quotes)


def _tfidf(docs):
    df = Counter()
    for doc in docs:
        df.update(set(doc))
    total = len(docs)
    vectors = []
    for doc in docs:
        counts = Counter(doc)
        vec = {}
        for term, count in counts.items():
            if df[term] < 2 or df[term] > total * 0.75:
                continue
            vec[term] = (1.0 + math.log(count)) * math.log(total / df[term])
        norm = math.sqrt(sum(value * value for value in vec.values())) or 1.0
        vectors.append({term: value / norm for term, value in vec.items()})
    return vectors


def _cosine(a, b):
    smaller, larger = (a, b) if len(a) <= len(b) else (b, a)
    return sum(value * larger.get(term, 0.0) for term, value in smaller.items())


def _normalize(vec):
    norm = math.sqrt(sum(value * value for value in vec.values())) or 1.0
    return {term: value / norm for term, value in vec.items()}


def _add_into(acc, vec):
    for term, value in vec.items():
        acc[term] = acc.get(term, 0.0) + value
    return acc


def kmeans(vectors, k, iters=40, seed=7):
    rng = random.Random(seed)
    centroids = [vectors[rng.randrange(len(vectors))]]
    for _ in range(k - 1):
        distances = [min(1.0 - _cosine(doc, centroid) for centroid in centroids) for doc in vectors]
        total = sum(distances)
        if total <= 0:
            pick = rng.randrange(len(vectors))
        else:
            target = rng.random() * total
            acc = 0.0
            pick = len(vectors) - 1
            for index, distance in enumerate(distances):
                acc += distance
                if acc >= target:
                    pick = index
                    break
        centroids.append(vectors[pick])
    assignments = [0] * len(vectors)
    for _ in range(iters):
        changed = False
        for index, doc in enumerate(vectors):
            best = max(range(k), key=lambda candidate: _cosine(doc, centroids[candidate]))
            if best != assignments[index]:
                assignments[index] = best
                changed = True
        sums = [{} for _ in range(k)]
        for index, doc in enumerate(vectors):
            _add_into(sums[assignments[index]], doc)
        for candidate in range(k):
            centroids[candidate] = _normalize(sums[candidate]) if sums[candidate] else centroids[candidate]
        if not changed:
            break
    return assignments, centroids


def _bigrams(tokens):
    return ['%s %s' % (a, b) for a, b in zip(tokens, tokens[1:])]


def _cluster_signals(member_videos, all_cluster_lists):
    unigram = Counter()
    bigram = Counter()
    for video in member_videos:
        unigram.update(set(document_tokens(video)))
        bigram.update(set(_bigrams(tokenize(video.get('title') or ''))))
        bigram.update(set(_bigrams(tokenize(video.get('channel') or ''))))
    cluster_df_uni = Counter()
    cluster_df_bi = Counter()
    for cluster_videos in all_cluster_lists:
        uni = set()
        bi = set()
        for video in cluster_videos:
            uni.update(set(document_tokens(video)))
            bi.update(set(_bigrams(tokenize(video.get('title') or ''))))
            bi.update(set(_bigrams(tokenize(video.get('channel') or ''))))
        cluster_df_uni.update(uni)
        cluster_df_bi.update(bi)
    total_clusters = max(1, len(all_cluster_lists))
    scored_uni = []
    for term, count in unigram.items():
        idf = math.log((total_clusters + 1.0) / (cluster_df_uni.get(term, 0) + 1.0)) + 1.0
        scored_uni.append((count * idf, term))
    scored_uni.sort(reverse=True)
    scored_bi = []
    for phrase, count in bigram.items():
        idf = math.log((total_clusters + 1.0) / (cluster_df_bi.get(phrase, 0) + 1.0)) + 1.0
        scored_bi.append((count * idf, phrase))
    scored_bi.sort(reverse=True)
    # Display signal: most discriminative phrase/token seen in >=2 member videos.
    combined = []
    for count, term in scored_uni:
        if count >= 2:
            combined.append((count, term))
    for count, phrase in scored_bi:
        if count >= 2:
            combined.append((count * 1.2, phrase))
    combined.sort(reverse=True)
    if combined:
        signal = next((term for _score, term in combined if term in SIGNAL_META), combined[0][1])
    else:
        signal = scored_uni[0][1] if scored_uni else 'topic'
    return ([term for _score, term in scored_uni],
            [phrase for _score, phrase in scored_bi], signal)


def _slug(term):
    return re.sub(r'[^a-z0-9]+', '-', term.lower()).strip('-') or 'topic'


def cluster_pool(videos):
    vectors = _tfidf([document_tokens(video) for video in videos])
    best = None
    for k in range(20, 26):
        assignments, centroids = kmeans(vectors, k)
        clusters = defaultdict(list)
        for index, cluster_id in enumerate(assignments):
            clusters[cluster_id].append(index)
        sizes = [len(members) for members in clusters.values()]
        honest = sum(1 for size in sizes if size >= MIN_CLUSTER)
        score = (honest, -max(sizes) if sizes else 0, k)
        if best is None or score > best[0]:
            best = (score, assignments, clusters)
    _score, assignments, clusters = best
    all_cluster_lists = [[videos[index] for index in members] for members in clusters.values()]
    result = []
    used_ids = set()
    for members in clusters.values():
        member_videos = [videos[index] for index in members]
        keywords, bigrams, signal = _cluster_signals(member_videos, all_cluster_lists)
        result.append({'videos': member_videos, 'keywords': keywords, 'bigrams': bigrams, 'signal': signal})
    result.sort(key=lambda cluster: -len(cluster['videos']))
    for cluster in result:
        meta = SIGNAL_META.get(cluster['signal'])
        base = meta[0] if meta else _slug(cluster['signal'])
        candidate = base
        suffix = 2
        while candidate in used_ids:
            candidate = f'{base}-{suffix}'
            suffix += 1
        cluster['id'] = candidate
        cluster['name_zh'] = meta[1] if meta else cluster['signal']
        used_ids.add(candidate)
    return result, len(result)


def _load_editorial(root='site/src/data'):
    videos = []
    for name in ('picks', 'trending', 'ai', 'podcast', 'music', 'videos'):
        path = Path(root) / f'{name}.json'
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        videos.extend(payload.get('videos', []))
    return videos


def _binary_vector(video):
    counts = Counter(document_tokens(video))
    vec = {term: 1.0 for term in counts}
    return _normalize(vec)


def _topic_centroids(pool, clusters):
    centroids = {}
    for cluster in clusters:
        acc = {}
        for video in cluster['videos']:
            _add_into(acc, _binary_vector(video))
        centroids[cluster['id']] = _normalize(acc) if acc else {}
    return centroids


def _primary_topic_lookup(pool, clusters):
    """Map every pool video to its cluster and every editorial video to the nearest topic."""
    lookup = {}
    for cluster in clusters:
        for video in cluster['videos']:
            lookup[video['id']] = cluster['id']
    editorial = _load_editorial()
    pool_ids = {video['id'] for video in pool}
    unknown = [video for video in editorial if video.get('id') and video['id'] not in pool_ids]
    if unknown and clusters:
        centroids = _topic_centroids(pool, clusters)
        for video in unknown:
            record = {**video, 'quotes': []}
            doc = _binary_vector(record)
            if not doc:
                continue
            nearest = max(centroids, key=lambda topic_id: _cosine(doc, centroids[topic_id]))
            if _cosine(doc, centroids[nearest]) >= 0.1:
                lookup[video['id']] = nearest
    return lookup


def _added_last_24h(topic_id, editorial, pool, lookup, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)
    count = 0
    for video in pool:
        if lookup.get(video['id']) == topic_id:
            published = published_at_dt(video)
            if published and published >= cutoff:
                count += 1
    for video in editorial:
        if lookup.get(video['id']) == topic_id:
            published = published_at_dt(video)
            if published and published >= cutoff:
                count += 1
    return count


def build_topics(pool_path='site/src/data/hn_pool.json', output_dir='site/src/data',
                 yaml_path='config/topics.yaml'):
    pool = json.loads(Path(pool_path).read_text())['videos']
    clusters, total = cluster_pool(pool)
    shipped = [cluster for cluster in clusters if len(cluster['videos']) >= MIN_CLUSTER]
    editorial = _load_editorial()
    lookup = _primary_topic_lookup(pool, clusters)
    topics = []
    for cluster in shipped:
        keywords = cluster['keywords'][:8]
        if len(keywords) < MIN_KEYWORDS:
            keywords = cluster['keywords'][:MIN_KEYWORDS]
        aliases = [cluster['signal']]
        for candidate in cluster['bigrams'][:4]:
            if candidate != cluster['signal'] and candidate not in aliases:
                aliases.append(candidate)
        aliases = aliases[:6]
        video_ids = [video['id'] for video in cluster['videos']]
        channel_ids = list(dict.fromkeys(video.get('channel_id') for video in cluster['videos'] if video.get('channel_id')))
        topics.append({
            'id': cluster['id'],
            'name_zh': cluster['name_zh'],
            'aliases_en': aliases,
            'keywords': keywords,
            'source_channel_ids': channel_ids,
            'video_ids': video_ids,
            'added_last_24h': _added_last_24h(cluster['id'], editorial, pool, lookup),
        })
    topics.sort(key=lambda topic: topic['id'])
    generated_at = iso_now()
    payload = {'generated_at': generated_at, 'count': len(topics), 'topics': topics}
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'topics.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    (out_dir / 'topic_lookup.json').write_text(json.dumps(lookup, ensure_ascii=False, indent=2) + '\n')
    yaml_lines = ['# Auto-generated from data clustering; do not hand-edit.', f'generated_at: {generated_at}', 'topics:']
    for topic in topics:
        yaml_lines.append(f'- id: {topic["id"]}')
        yaml_lines.append(f'  name_zh: "{topic["name_zh"]}"')
        yaml_lines.append(f'  aliases_en: {json.dumps(topic["aliases_en"], ensure_ascii=False)}')
        yaml_lines.append(f'  keywords: {json.dumps(topic["keywords"], ensure_ascii=False)}')
        yaml_lines.append(f'  source_channel_ids: {json.dumps(topic["source_channel_ids"], ensure_ascii=False)}')
        yaml_lines.append(f'  video_ids: {json.dumps(topic["video_ids"], ensure_ascii=False)}')
        yaml_lines.append(f'  added_last_24h: {topic["added_last_24h"]}')
    Path(yaml_path).write_text('\n'.join(yaml_lines) + '\n')
    print(f'Shipped {len(topics)} topics (clustered {total} total).')
    return payload


if __name__ == '__main__':
    payload = build_topics()
    for topic in payload['topics']:
        print(f"{topic['id']:22} {topic['name_zh']:12} n={len(topic['video_ids'])} "
              f"added24h={topic['added_last_24h']} kw={topic['keywords']}")
