"""Cluster the HN pool into data-driven topics and emit topic artifacts.

No LLM calls: topic membership, keywords, and aliases come from TF-IDF clustering
of video titles, channels, and quote text, followed by deterministic
channel/title curation rules. The display signal (used for the topic id and
Chinese name) is the cluster's most discriminative phrase/token; only the
signal -> Chinese-name translation is curated.
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

CLASSIC_TALKS_TOPIC_ID = 'classic-talks'
_NEWS_RECAP_TITLE_RE = re.compile(
    r'\bloses?\b[^|]{0,45}\$?\d+(?:\.\d+)?\s*[bmk]\b|'
    r'\bbuys?\b[^|]{0,60}\bfor\s+\$\d+(?:\.\d+)?\s*[bmk]\b|'
    r'\braises?\b[^|]{0,45}\$\d+(?:\.\d+)?\s*[bmk]\b|'
    r'\bin\s+\d{1,2}\s+hours?\b|'
    r'\b(?:market|stocks?|wall\s+street)\s+'
    r'(?:recap|roundup|wrap|today|close|rally|selloff|plunge)\b|'
    r'\b(?:daily|weekly)\s+(?:news\s+)?(?:recap|roundup)\b|'
    r'\bnews\s+(?:recap|roundup)\b|\btop\s+stories\b',
    re.IGNORECASE,
)


def is_news_recap_title(title):
    """Return True for finance/news recap headlines that are not classic talks."""
    return bool(title and _NEWS_RECAP_TITLE_RE.search(str(title)))


def retag_topic_lookup(lookup, metadata):
    """Drop 经典演讲 chips from news/market recap headlines.

    Metadata is a mapping of video id to a record containing at least ``title``.
    Real TED, commencement, and classic lecture titles are left untouched.
    """
    retagged = dict(lookup)
    changed = 0
    for video_id, topic_id in lookup.items():
        if topic_id != CLASSIC_TALKS_TOPIC_ID:
            continue
        record = metadata.get(video_id) or {}
        if is_news_recap_title(record.get('title')):
            retagged.pop(video_id, None)
            changed += 1
    return retagged, changed

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
    'mit': ('mit', '高校公开课'), 'opencourseware': ('mit', '高校公开课'),
    'cppcon': ('cpp', 'C++ 与系统编程'), 'cppcon chandler': ('cpp', 'C++ 与系统编程'),
    'movie': ('language-history', '编程语言史'), 'ii': ('language-history', '编程语言史'), 'erlang': ('language-history', '编程语言史'),
    'space': ('future-programming', '未来编程'), 'bret': ('future-programming', '未来编程'),
}

# Merge duplicate clusters that describe the same theme. The smaller Veritasium
# cluster is folded into science before rules move its non-science members away.
CLUSTER_MERGES = {'science-2': 'science'}

# Channels whose entire catalogue belongs to one topic even when an individual
# title happens to contain a generic term such as "neural network" or "LLM".
HARD_CHANNEL_TOPIC = {
    'UCYO_jab_esuFRV4b17AJtAw': 'math',     # 3Blue1Brown
    'UCHnyfMqiRRG1u-2MsSQLbXA': 'science',  # Veritasium
}

# Narrow title exceptions take precedence over the broader channel map. A None
# target drops the video from shipped topics; it remains in hn_pool and still
# receives a weaker primary topic in topic_lookup.json.
TITLE_TOPIC_RULES = [
    (re.compile(r'\bleap technology\b', re.I), None),
    (re.compile(r'building the perfect linux pc|linus torvalds on why desktop linux', re.I), 'tech-review'),
    (re.compile(r'linus torvalds on git|google wave developer preview', re.I), 'programming'),
    (re.compile(r'\bruby on rails\b|\brails demo\b', re.I), 'programming'),
    (re.compile(r'y ?combinator|startup school', re.I), 'startups'),
    (re.compile(r"i don't like notebooks", re.I), 'conferences'),
    (re.compile(r'quakecon', re.I), 'game-dev'),
    (re.compile(r'\bzelda\b|\bsm64\b|super mario 64', re.I), 'games'),
    (re.compile(r'backyard squirrel maze', re.I), 'maker'),
    (re.compile(r'steve jobs presents to the cupertino|cupertino city council', re.I), 'classic-talks'),
    (re.compile(r'worst nuclear accidents', re.I), 'science'),
    (re.compile(r'elevator hacking', re.I), 'maker'),
    (re.compile(r'insane battle to sabotage|apartment building.*housing crisis', re.I), 'commentary'),
    (re.compile(r'everything is a remix', re.I), 'documentary'),
    (re.compile(r'future computers will be radically different', re.I), 'science'),
    (re.compile(r'tesla battery day', re.I), 'tech-review'),
    (re.compile(r'\btitanic\b|\bshakespeare\b', re.I), 'documentary'),
    (re.compile(r'\bclimate\b|global warming|renewable energy|gas stoves?|greenhouse|'
                r'deforestation|heat pumps?|soil health|population and energy|'
                r'electric cars? .*environment|planet of the humans|'
                r'deserts? .*climate', re.I), 'climate'),
    (re.compile(r'(?:\bai\b|\ba\.i\.|\bagi\b|\bllms?\b|\bgpt(?:-\d+)?\b|\bchatgpt\b|'
                r'\bdeep learning\b|\bmachine learning\b|\bneural networks?\b|'
                r'\bstable diffusion\b|\bartificial (?:intelligence|consciousness)\b|'
                r'\bblack-hat llms?\b)', re.I), 'ai'),
]

# Broad channel -> topic mappings. Channel ids are stable in the local pool and
# let the builder reassign whole catalogues without hand-editing generated JSON.
CHANNEL_TOPIC = {
    # AI / ML
    'UCXUPKJO5MZQN11PqgIvyuvQ': 'ai',  # Andrej Karpathy
    'UCR85FcguqcxLQ7XEg1byAtQ': 'ai',  # Matroid
    'UCZHmQk67mSJgfCCTn7xBfew': 'ai',  # Yannic Kilcher
    'UC-UC-nE8B33UGnC-NRaSfug': 'ai',  # Sebastien Bubeck
    'UC5WjFrtBdufl6CZojX3D8dQ': 'ai',  # Tesla
    'UCXZCJLdBC09xxGZ6gcdrc6A': 'ai',  # OpenAI
    'UC5GCrYGsm7EHQzQZj65A-5w': 'ai',  # [un]prompted
    'UCFECM-p3CF81Tp_l2sJsiyg': 'ai',  # Center for Humane Technology
    'UCP7jMXSY2xbc3KCAE0MHQ-A': 'ai',  # Google DeepMind

    # Math and visual explanations
    'UC7M-Wz4zK8oikt6ATcoTwBA': 'math',  # Freya Holmér
    'UCdmAhiG8HQDlz8uyekw4ENw': 'math',  # Inigo Quilez
    'UC1_uAIS3r8Vu6JjXWvastJg': 'math',  # Mathologer
    'UCSju5G2aFaWMqn-_0YBtq5A': 'math',  # Stand-up Maths
    'UCoxcjq-8xIDTYp3uz647V5A': 'math',  # Numberphile
    'UCyp1gCHZJU_fGWFf2rtMkCg': 'math',  # Numberphile2
    'UCtJPeNYnAXhB1-_h8xbIX_Q': 'math',  # Nemean
    'UCZZ3MA6ChVTViq8ORmFfCPA': 'math',  # Bivector
    'UCCb9_Kn8F_Opb3UCGm-lILQ': 'math',  # Microsoft Research

    # Science
    'UCsXVk37bltHxD1rDPwtNM8Q': 'science',  # Kurzgesagt
    'UC6nSFpj9HTCZ5t-N3Rm3-HA': 'science',  # Vsauce
    'UCUHW94eEFW7hkUMVaZz4eDg': 'science',  # minutephysics
    'UCWvq4kcdNI1r1jZKFw9TiUA': 'science',  # ScienceClic
    'UC1yNl2E66ZzKApQdRuTQ4tw': 'science',  # Sabine Hossenfelder
    'UCtscFf8VayggrDYjOwDke_Q': 'science',  # Angela Collier
    'UCR1IuLEqb6UEA_zQ81kwXfg': 'science',  # Real Engineering
    'UC2bkHVIDjXS7sgrgjFtzOXQ': 'science',  # engineerguy
    'UCCWeRTgd79JL0ilH0ZywSJA': 'science',  # AlphaPhoenix
    'UCJ0-OtVpF0wOKEqT2Z1HEtA': 'science',  # ElectroBOOM
    'UC7_gcs09iThXybpVgjHZ_7g': 'science',  # PBS Space Time
    'UCNqNkZ7kKfqimqHkgbWMNYA': 'science',  # Launch Pad Astronomy
    'UC6107grRI4m0o2-emgoDnAA': 'science',  # SmarterEveryDay
    'UCMOqf8ab-42UUQIdVoKwjlQ': 'science',  # Practical Engineering
    'UClaMKdlrBAqj0i8k_b0QC_Q': 'science',  # Feynman lectures
    'UC5g-f-g4EVRkqL8Xs888BLA': 'science',  # Bioelectric computation
    'UC6uKrU_WqJ1R2HMTY3LIx5Q': 'science',  # Everyday Astronaut
    'UCtI0Hodo5o5dUb67FeUjDeA': 'science',  # SpaceX
    'UCmb8hO2ilV9vRa8cilis88A': 'science',  # Thunderf00t
    'UCR9sFzaG9Ia_kXJhfxtFMBA': 'science',  # melodysheep
    'UCTdLvmSFokrAtp1ZtP-HhSw': 'science',  # US Auto Industry
    'UCaHTNOx_kHc0mvKjhhltceQ': 'science',  # ConceptVBS
    'UCotwjyJnb-4KW7bmsOoLfkg': 'science',  # Art of the Problem
    'UCLYG3Tn_qNxfLdVV6Gr7PGg': 'science',  # chip manufacturing
    'UC-k1j7M2-hBfXeECd9YAQ_g': 'science',  # Starlink relays
    'UCH_zYYXkJpULueOVZTkY4Bw': 'science',  # Lawrence Krauss
    'UC2D2CMWXMOVWx7giW1n3LIg': 'science',  # Andrew Huberman
    'UCrgvg3HpIT-MuwvTDVRm9mA': 'science',  # Feynman CS lecture
    'UCXtSt_iCM8XMy0Z-B2w9LSg': 'science',  # Missing Memristor
    'UCBBd3JxQl455JkWBeulc-9w': 'science',  # Berkeley BIDS
    'UCP_lo1MFyx5IXDeD9s_6nUw': 'programming',  # Meta Developers
    'UCYeF244yNGuFefuFKqxIAXw': 'science',  # The Royal Institution
    'UCH5Rft7GYM8KZpxA-4Ohihg': 'science',  # insideHPC
    'UCdp4_l1vPmpN-gDbUwhaRUQ': 'science',  # Branch Education
    'UCLA_DiR1FfKNvjuUpBHmylQ': 'science',  # NASA

    # Programming, languages, and software
    'UCKS1lbJXYQxwqpFzHMiYinQ': 'programming',  # tenthconcept
    'UCseUQK4kC3x2x543nHtGpzw': 'programming',  # Brian Will
    'UCQ7dFBzZGlBvtU2hCecsBBg': 'programming',  # Next Day Video
    'UCgxzjK6GuOHVKR_08TT4hJQ': 'programming',  # PyCon 2015
    'UCrJhliKNQ8g0qoE_zvL8eVg': 'programming',  # PyCon 2017
    'UC51aOZF5nnderbuar5D5ifw': 'programming',  # SF Python
    'UCTHcgWOTU6gPje1g_U29tfQ': 'programming',  # YUI Library
    'UCO3LEtymiLrgvpb59cNsb8A': 'programming',  # Go
    'UC9IuUwwE2xdjQUT_LMLONoA': 'programming',  # Julia
    'UCoebwHSTvwalADTJhps0emA': 'programming',  # Wes Bos
    'UCaTznQhurW5AaiYPbhEA-KA': 'programming',  # Molly Rocket
    'UCRLwxeoe37rPV7E9bHBLcHA': 'programming',  # Etsy Engineering
    'UC3P6PrEBAVH1UaiPOzZ-u-w': 'programming',  # Russ Cox
    'UCzdaFtpPWb-Pn6oYXQTCnxA': 'programming',  # Brian Kernighan lecture
    'UCUR1pFG_3XoZn3JNKjulqZg': 'programming',  # thoughtbot
    'UC8uSLYDanXDnP9Yn8UrTNzQ': 'programming',  # Racket
    'UC9SzG8f9xlz8VquuO4fRZsg': 'programming',  # Go Sydney
    'UCbGQAz4nL_P2Em5p8KPDFIA': 'programming',  # Casey Muratori
    'UCkhm72fuzkS9fYGlGpEmj7A': 'programming',  # Matplotlib
    'UCrZv07X-hsHqXjM-cxgRBhg': 'programming',  # Allen Holub
    'UC7BL19P9OXPOJgu2DRzozDA': 'programming',  # Eskil Steenberg
    'UCRFAE1uHnrhXlSkoaAgKsIQ': 'programming',  # Dyalog APL
    'UCB31oh4SvSvz5LCM84Pov9w': 'programming',  # Monads

    # Clojure / functional programming
    'UCaLlzGqiPE2QRj6sSOawJRg': 'clojure',  # ClojureTV
    'UClJshc6QtMWRqIAwJy85sfA': 'clojure',  # Clojure/north

    # Systems
    'UCciKHCG06rnq31toLTfAiyw': 'systems',  # linux.conf.au
    'UC_KrvG48vsb4SYRGlu3rAHg': 'systems',  # Wayland talk
    'UC7jUrsr9985aKVJmpg-dtZg': 'systems',  # Gtk/Qt talk
    'UC4-GrpQBx6WCGwmwozP744Q': 'systems',  # USENIX
    'UCIxsmRWj3-795FMlrsikd3A': 'systems',  # Linux Plumbers
    'UCfX55Sx5hEFjoC3cNs6mCUQ': 'systems',  # The Linux Foundation
    'UCQjlOy1mNc9IockEk5BS5GQ': 'systems',  # Method / SQLite
    'UCro9rA8-YX-26UVNY8ewAKQ': 'systems',  # Speakeasy / eBPF

    # Conferences
    'UC_QIfHvN9auy2CoOdSfMWDw': 'conferences',  # Strange Loop
    'UCs_tLP3AiwYKwdUHpltJPuA': 'conferences',  # GOTO
    'UCTdw38Cw6jcm0atBPA39a0Q': 'conferences',  # NDC
    'UCzoVCacndDCfGDf41P-z0iA': 'conferences',  # JSConf
    'UCWnPjmqvljcafA0z2U1fwKQ': 'conferences',  # Confreaks
    'UC47eUBNO8KBH_V8AfowOWOw': 'conferences',  # Code Sync
    'UCorlLn2oZfgOJ-FUcF2eZ1A': 'conferences',  # ReactEurope
    'UCSRhwaM00ay0fasnsw6EXKA': 'conferences',  # dotconferences
    'UCvzMZyJZZ3XYQwbvOACVYrQ': 'conferences',  # DevTernity
    'UCaUtAK8xECTkETCYivJegeQ': 'conferences',  # RedMonk
    'UC3BGlwmI-Vk6PWyMt15dKGw': 'conferences',  # O'Reilly
    'UC6Om9kAkl32dWlDSNlDS9Iw': 'conferences',  # DEF CON
    'UCJ6q9Ie29ajGqKApbLqfBOg': 'conferences',  # Black Hat
    'UC2TXq_t06Hjdr2g_KdKpHQg': 'conferences',  # media.ccc.de
    'UCwBVURsT1hSnFT8vGO6vSqw': 'conferences',  # 28c3
    'UCd9I8ZkgoR1d7GeSj_wi_LQ': 'conferences',  # @Scale
    'UCoYjwcb3p7DDeE_B1KneGFw': 'conferences',  # Platform Security Summit
    'UC0BJVNTIEbG8CLG-xVVWJnA': 'conferences',  # HITB
    'UCqMG_BBwxrhLG80Y3yuEu-Q': 'conferences',  # XOXO
    'UCYmfe5bvRYu-H1rtfc4n7AA': 'conferences',  # securitylectures
    'UCkQX1tChV7Z7l1LFF4L9j_g': 'conferences',  # InfoQ
    'UC4PBNDLlS4d75MP0xxcukGA': 'conferences',  # Adrian Crenshaw
    'UCr5AKH-Ooht17f2xxRaX3ag': 'conferences',  # Paul Stringer's Mobile Tech
    'UCYI-TL0LoFRl1gFnnUFwdow': 'conferences',  # Better Software Conference
    'UC7Qu6WAXfoGUYc8NxPDZZBg': 'conferences',  # Code & Supply
    'UC_x5XG1OV2P6uZZ5FSM9Ttw': 'conferences',  # Google for Developers
    'UC9V4KS8ggGQe_Hfeg1OQrWw': 'conferences',  # SIGGRAPH
    'UCEPzS1rYsrkqzSLNp76nrcg': 'conferences',  # Christiaan008
    'UCoj4eQh_dZR37lL78ymC6XA': 'conferences',  # PapersWeLove
    'UCU-fOxx_kT5OARG0KiksiCA': 'conferences',  # You Gotta Love Frontend
    'UCVob1MNHX2wRBPZXRDIlPgQ': 'conferences',  # LibreSSL
    'UCc0j7uOItUDh7vEvPb-TeCg': 'conferences',  # Scala World
    'UCqT6vUgnUC8VWd2yiHQlHSg': 'conferences',  # DebConf
    'UChfe3zGOtlJoHVl0tRUrGJA': 'conferences',  # Blockchains talk

    # Game development and games
    'UC0JB7TSe49lg56u6qH8y_MQ': 'game-dev',  # GDC
    'UCgoMppmHUHU_3vxMD7oDG7g': 'game-dev',  # DevGAMM
    'UCtQvv0QrY7_W49gtIPSDWdg': 'game-dev',  # Media Molecule
    'UC-2Y8dQb0S6DtpxNgAKoJKA': 'game-dev',  # PlayStation
    'UCDXajZI-pUqVfPpjdXp9zCA': 'game-dev',  # grapefrukt
    'UCCuoqzrsHlwv1YyPKLuMDUQ': 'game-dev',  # Jonathan Blow
    'UCaYhcUwRBNscFNUKTjgPFiA': 'game-dev',  # Rust game development talk
    'UC3azLjQuz9s5qk76KEXaTvA': 'games',  # suckerpinch
    'UCMm211NGh4Ls5SAMZJF7E8A': 'games',  # pannenkoek2012
    'UCuvSqzfO_LV_QzHdmEj84SQ': 'games',  # Kaze Emanuar
    'UCAnzaHhB0ONtwDkYdc3MFCw': 'games',  # Linkus7
    'UCZB6V9fUov0Mx_us3MWWILg': 'games',  # People Make Games
    'UCGNm2vGRTPwbO0Q6u-X7MuA': 'games',  # Morphcat Games
    'UCE1jXbVAGJQEORz9nZqb5bQ': 'games',  # Ahoy
    'UC4EFgGdLCsUKXO4LzMfypMA': 'games',  # Power Pak
    'UC0fDG3byEcMtbOqPMymDNbw': 'games',  # noclip
    'UCCDU1fsmgvWljcW2aodfJsA': 'games',  # Ars Technica game stories
    'UC1d4faRf_bna2UZkiJuJ-Mw': 'game-dev',  # Gabe Newell
    'UCeLK5pd6P33uz_ffPFYGwZg': 'game-dev',  # QuakeCon talk
    'UCaquFi5JOPWPFNwy11oPx2w': 'game-dev',  # QuakeCon
    'UC766vkQw0Mz3VtXX5XvXxGQ': 'game-dev',  # Oculus live coding
    'UCIQ3KtupJCawXGMyTqpADXg': 'game-dev',  # free-to-play monetisation

    # Making / hardware
    'UCS0N5baNlQWJCUrhCEo8WlA': 'maker',  # Ben Eater
    'UCUQo7nzH1sXVpzL92VesANw': 'maker',  # DIY Perks
    'UC4dxXZQq-ofAadUWbqhoceQ': 'maker',  # DeviantOllam
    'UCY1kMZp36IQSyNx_9h4mpCg': 'maker',  # Mark Rober
    'UCO8DQrSp5yEP937qNqTooOw': 'maker',  # Strange Parts
    'UCV5vCi3jPJdURZwAOO_FNfQ': 'maker',  # The Thought Emporium
    'UCVSHXNNBitaPd5lYz48--yg': 'maker',  # Tech Ingredients
    'UCj1VqrHhDte54oLgPG4xpuQ': 'maker',  # Stuff Made Here
    'UCtM5z2gkrGRuWd0JQMx76qA': 'maker',  # bigclivedotcom
    'UChWv6Pn_zP0rI6lgGt3MyfA': 'maker',  # AvE
    'UCiDJtJKMICpb9B1qf7qjEOA': 'maker',  # Adam Savage's Tested
    'UCpFrWTaIDAnGzrA3P9OxfhQ': 'maker',  # webserver on public transport
    'UC0IY1BQiMehWMvezqWLyk4g': 'maker',  # Nixie Tube

    # Tech reviews / explainers
    'UCXuqSBlHAE6Xw-yeJA0Tunw': 'tech-review',  # Linus Tech Tips
    'UCy0tKL1T7wFoYcxCe0xjN6Q': 'tech-review',  # Technology Connections
    'UC9-y-6csu5WGm29I7JiwpnA': 'tech-review',  # Computerphile
    'UCBa659QWEk1AI4Tg--mrJ2A': 'tech-review',  # Tom Scott
    'UCl2mFZoRqjw_ELax4Yisf6w': 'tech-review',  # Louis Rossmann
    'UChIs72whgZI9w6d6FhwGGHA': 'tech-review',  # Gamers Nexus
    'UCGsaijjOJshS2_ZmMNZgS-g': 'tech-review',  # der8auer
    'UC18R5fEIi0uleFNt3v4KwaQ': 'tech-review',  # gentooman
    'UCshObcm-nLhbu8MY50EZ5Ng': 'tech-review',  # Benn Jordan
    'UCSpFnDQr88xCZ80N-X7t0nQ': 'tech-review',  # Corridor Crew
    'UCj--iMtToRO_cGG_fpmP5XQ': 'tech-review',  # Munro Live

    # Computing history
    'UCHDr4RtxwA1KqKGwxgdK4Vg': 'computing-history',  # Computer History Museum
    'UCnpDurxReTSpFs5-AhDo8Kg': 'computing-history',  # AT&T Tech Channel
    'UC3bosUr3WlKYm4sBaLs-Adw': 'computing-history',  # CuriousMarc
    'UCNzszbnvQeFzObW0ghk0Ckw': 'computing-history',  # Dave's Garage
    'UC8uT9cgJorJPWu7ITLGo9Ww': 'computing-history',  # The 8-Bit Guy
    'UCBGzCVpJFb-MPehbNoK173w': 'computing-history',  # VintageCG
    'UCO1ifHwXHkEyCLFk2b7Z8xA': 'computing-history',  # TheRasteri
    'UC4M8BkvloHHCM0_l1-WdNaw': 'computing-history',  # NeXT vs Sun
    'UCsGeHtRtIooDGzvLKxz9t3w': 'computing-history',  # Symbolics Lisp Machine
    'UC44lc40rLHVDMxfxNimVRSg': 'computing-history',  # UNIX history
    'UCq2d2c_u0Lat0SL9P4LEPlg': 'computing-history',  # TNMoC
    'UC49y2dyVZ6_V3dJxrFuzinA': 'computing-history',  # 8088 MPH
    'UCfsznjef2zGJnrCRQBXqo6Q': 'computing-history',  # Machine Thinking
    'UC3FlJFuAHHWehanLCETxCcw': 'computing-history',  # Mechanical computer
    'UCk9H1u4QMFNbBOj96A9DGHw': 'computing-history',  # Mother of All Demos
    'UCBYAfgpXFaO3yebqf49KAgQ': 'computing-history',  # Micro Men

    # Computer pioneers
    'UCSA0xzgKlopUZpIaw6XAsvA': 'pioneers',  # Jeff Gonis / Alan Kay
    'UCNOMqK6psg2Wvl68_9xDyDw': 'pioneers',  # powerfuloutlet / Alan Kay
    'UCOEy0zJHk8d3vwk47b2chZg': 'pioneers',  # Kenneth Friedman
    'UCr_DXJ7ZUAJO_d8CnHYTDMQ': 'pioneers',  # Ted Nelson
    'UCqv7gk4p_rB4nRz0j7B5yFA': 'pioneers',  # Ivan Sutherland
    'UCKrD_GYN3iDpG_uMmADPzJQ': 'pioneers',  # Erlang Solutions
    'UCKdBVD2wVUkuJQZhxGvVr0Q': 'pioneers',  # Vintage Computer Federation

    # University courses and lectures
    'UCEBb1b_L6zDS3xTUrIALZOw': 'mit',  # MIT OpenCourseWare
    'UCu2dehvPe9e_ui_1HN7INxw': 'mit',  # MIT Club of Northern California
    'UCMFsHceLUJNkXMiCMFNnvkA': 'mit',  # MIT Plasma Science and Fusion Center
    'UCjSXSHPOU4Dr94ENpf2YAiw': 'mit',  # MIT Video Productions
    'UC-EnprmCZ3OXyAoG7vjVNCA': 'mit',  # Stanford
    'UCf-COwmdNelXvbj-KaMCuLw': 'mit',  # Carnegie Mellon
    'UCcabW7890RKJzL968QWEykA': 'mit',  # CS50
    'UCSh-dNnqe1agUSzPM01LgBA': 'mit',  # Yale
    'UCVCldvV9TWPPGM0kRB91G7w': 'mit',  # UMBC
    'UCh6KFtW4a4Ozr81GI1cxaBQ': 'mit',  # UCTV
    'UCblU02pAw9C5jnDZSGNs_Hw': 'mit',  # UMBC lecture
    'UCYN8R_LpgxCkeVTO_YdVJoA': 'mit',  # UC Berkeley EECS

    # Talks
    'UCAuUUnT6oDeKwE6v1NGQxug': 'classic-talks',  # TED
    'UCsT0YIqwnpJCM-mx7-gSA4Q': 'classic-talks',  # TEDx
    'UCbmNph6atAoGfqLoCL_duAg': 'classic-talks',  # Talks at Google
    'UCtXKDgv1AVoG88PLl8nGXmw': 'classic-talks',  # Google TechTalks
    'UChTGNMh9Ti6cCi6gMCxhBTg': 'classic-talks',  # City of Cupertino
    'UC6d4S835I5zWy4GSu1ThJog': 'classic-talks',  # Steve Jobs keynote
    'UCML_dO_vGALxxQbmYdLPrhw': 'classic-talks',  # Steve Jobs presentation
    'UC9UHHS9id7KonzYR1fNqFyw': 'classic-talks',  # Video Arts
    'UC-ZA3QN2nDmqOSujn8zvNjw': 'classic-talks',  # CreativeMornings

    # Startups
    'UCpl3CA98zybDPLjRKYWcAlg': 'startups',  # Startup School
    'UCcefcZRL2oaA_uBNeo5UOWg': 'startups',  # Y Combinator
    'UCxIJaCMEptJjxmmQgGFsnCg': 'startups',  # YC Root Access
    'UCHoBKQDRkJcOY2BO47q5Ruw': 'startups',  # Rob Walling
    'UCI11W4ZZ4k-w0zYWw7sZfIw': 'startups',  # Founder School
    'UCCjyq_K1Xwfg8Lndy7lKMpA': 'startups',  # TechCrunch
    'UCIsbLox_y9dCIMLd8tdC6qg': 'startups',  # Vanity Fair / YC
    'UCGwuxdEeCf0TIA2RbPOj-8g': 'startups',  # Stanford GSB
    'UCESLZhusAkFfsNsApnjF_Cg': 'startups',  # All-In Podcast
    'UCASM0cgfkJxQ1ICmRilfHLw': 'startups',  # Patrick Boyle

    # Ideas
    'UCzQUP1qoWDoEbmsQxvdjxgQ': 'ideas',  # Joe Rogan
    'UCY7dD6waquGnKTZSumPMTlQ': 'ideas',  # Oxford Union
    'UC51_awyLXl2nxCduuzzmw4w': 'ideas',  # Milton Friedman
    'UCK8sQmJBp8GCxrOtXWBpyEA': 'ideas',  # Google talks
    'UCv_vLHiWVBh_FR9vbeuiY-A': 'ideas',  # Historia Civilis
    'UCR85PW_B_7_Aisx5vNS7Gjw': 'ideas',  # Eric Weinstein
    'UCqvaXJ1K3HheTPNjH-KpwXQ': 'ideas',  # Ray Dalio
    'UCIb2ti8V0Mhgvxgs80-Lo1w': 'ideas',  # Chomsky/Foucault
    'UCMFqCWI1HZRNDQIKERXEg3Q': 'ideas',  # Christopher Alexander
    'UCvhsiQGy_zcNCiSbeXEjhLg': 'ideas',  # RSA Animate
    'UCil2G-oUNzJ7Bzfv11kDjNQ': 'ideas',  # UChicago Social Sciences
    'UCxHTM1FYxeC4F7xDsBVltGg': 'ideas',  # Wim Hof
    'UCcEDTBdietc2JmgN6TL8wAg': 'ideas',  # Radical Discourse
    'UCJIfeSCssxSC_Dhc5s7woww': 'ideas',  # Lex Clips
    'UCSHZKyawb77ixDdsGog4iWA': 'ideas',  # Lex Fridman
    'UC8BtBl8PNgd3vWKtm2yJ7aA': 'math',  # Category Theory

    # Documentary
    'UC8xkuBKC4fXJHrnXtOwEW8Q': 'documentary',  # Adam Curtis
    'UCa1LiBedgAciIiHqBAWEo7Q': 'documentary',  # JustAdamCurtis
    'UCU_nlLzlVPFLJxB_iEwtwBw': 'documentary',  # Michael Moore
    'UCQ5imaHcujp1h98CGpLE9sA': 'documentary',  # WIRED Investigations
    'UC4FrvWBLhbOkpgOHj-jz6Ww': 'documentary',  # The Documentary Network
    'UC__2_0RJ8XnHt2angfw6S1Q': 'documentary',  # KOMO News
    'UCNye-wNBqNL5ZzHSJj3l8Bg': 'documentary',  # Al Jazeera
    'UCddiUEpeqJcYeBxX1IVBKvQ': 'documentary',  # The Verge
    'UCyF-6wI0EoKAe7nZqlIOrOA': 'documentary',  # X, The Moonshot Factory
    'UCeIJlnFJ9ewahK2ZmOYVOqQ': 'documentary',  # Project Code Rush
    'UCMOB6uDg7e-h8OuCw8dK2_Q': 'documentary',  # ALTER
    'UCR1D15p_vdP3HkrH8wgjQRw': 'documentary',  # Internet Historian
    'UC9PIn6-XuRKZ5HmYeu46AIw': 'documentary',  # Barely Sociable
    'UCbWcXB0PoqOsAvAdfzWMf0w': 'documentary',  # Fredrik Knudsen
    'UCddem5RlB3bQe99wyY49g0g': 'documentary',  # PeriscopeFilm
    'UCehSs_T0079U1hwNuw4LXBA': 'documentary',  # Dominion
    'UCnrKkTdBFs2UipU2-Ikjsbg': 'documentary',  # Nuclear explosion map
    'UCqwxJts-6yF33rupyF_DCsA': 'documentary',  # Life Where I'm From
    'UCXsH4hSV_kEdAOsupMMm4Qw': 'documentary',  # OpenLearn
    'UCVT1tPkR-fUVlO652EcO3ow': 'documentary',  # CBS Sunday Morning
    'UCHTqhvH0v4iXpxzoNuZbTyw': 'documentary',  # drum loop
    'UCvAovXWLq8Q6VITKAB_Rjww': 'documentary',  # guitar tone
    'UCZaT_X_mc0BI-djXOlfhqWQ': 'documentary',  # VICE News
    'UCOKHwx1VCdgnxwbjyb9Iu1g': 'documentary',  # Blender Guru
    'UCMbmqUMqzerMSM48pGYMYsg': 'documentary',  # Gapminder
    'UC30jm2WJ03mTCOxzU3mBC1A': 'documentary',  # KGB computer
    'UCvwZ5XRRdZRePAqJ7UZPUyQ': 'documentary',  # Collateral Murder
    'UCGIkFNbztHRaX0GB78SWaZA': 'documentary',  # Magenta Line
    'UCqGONXW1ORgz5Y4qK-0JdkQ': 'documentary',  # Hackers testifying
    'UCq6aw03lNILzV96UvEAASfQ': 'documentary',  # bill wurtz
    'UCCRa-wycVfgh1ctaKaD0BeQ': 'documentary',  # Eames Office
    'UCftwRNsjfRo08xYE31tkiyw': 'documentary',  # WIRED
    'UCvpQ-l09fCVxJd3urZbxzHg': 'documentary',  # British Museum
    'UCqVEHtQoXHmUCfJ-9smpTSg': 'documentary',  # Answer in Progress
    'UC9RM-iSvTu1uPJb8X5yp3EQ': 'documentary',  # Wendover Productions

    # Commentary
    'UC3XTzVzaHQEd30rQbuvCtTQ': 'commentary',  # Last Week Tonight
    'UC0intLFzLaudFG-xAvUEO-A': 'commentary',  # Not Just Bikes
    'UCyNtlmLB73-7gtlBz00XOQQ': 'commentary',  # Folding Ideas
    'UCmGSJVG3mCRXVOP4yZrU1Dw': 'commentary',  # Johnny Harris
    'UCLXo7UDZvByw2ixzpQCufnA': 'commentary',  # Vox
    'UCm1fqkJ-Tq64bQzM6VRMicQ': 'commentary',  # NYT Opinion
    'UC0uVZd8N7FfIZnPu0y7o95A': 'commentary',  # ReasonTV
    'UC7JrYS7mUdFSDyfpuZQDwBw': 'commentary',  # George Carlin
    'UCANb8zIwVZzMuot5fhLPDQA': 'commentary',  # George Carlin
    'UCt-TWZubGKT0mkQfFwnzloQ': 'commentary',  # George Carlin
    'UCGINcKuFbysZAslgL46KeOA': 'commentary',  # John Mearsheimer
    'UCwhB8cJTSLxyubnKSS-PLJg': 'commentary',  # MegaLag
    'UCFQMnBA3CS502aghlcr0_aw': 'commentary',  # Coffeezilla
    'UCjr2bPAyPV7t35MvcgT3W8Q': 'commentary',  # The Hated One
    'UCP5tjEmvPItGyLhmjdwP7Ww': 'commentary',  # RealLifeLore
    'UC0qMEMLBV_4yrRyJm_ugxVw': 'commentary',  # Jon Stewart
    'UCuvWIeAEnRF3O16O9uihnZw': 'commentary',  # Christopher Hitchens
    'UCQrJSZqagqHCls2Vkrubkzg': 'commentary',  # Rowan Atkinson
    'UCL_f53ZEJxp8TtlOkHwMV9Q': 'commentary',  # Jordan Peterson
    'UChvithwOECK5g_19TjldMKw': 'commentary',  # laowhy86
    'UCs523RmO5vIVulYpOoAGDyw': 'commentary',  # Blonde Politics
    'UCgPClNr5VSYC3syrDUIlzLw': 'commentary',  # Adult Swim
    'UCEE8w-v6Gg4j3ze3oX-urEw': 'commentary',  # Project Veritas
    'UCl_dlV_7ofr4qeP1drJQ-qg': 'commentary',  # Tantacrul
    'UC2C_jShtL725hvbm1arSV9w': 'commentary',  # CGP Grey
    'UCnkp4xDOwqqJD7sSM3xdUiQ': 'commentary',  # Adam Neely
    'UCJ6o36XL0CpYb6U5dNBiXHQ': 'commentary',  # The Bell Curve
    'UCi38HMIvRpGgMJ0Tlm1WYdw': 'commentary',  # Sassy Justice
    'UCfVotMGyD7sVMomr2AzsBtQ': 'commentary',  # ADL / Sacha Baron Cohen

    # Climate and environment
    'UCuVLG9pThvBABcYCm7pkNkA': 'climate',  # Climate Town
    'UCiBgK94oWs_x2wszFD-nlEQ': 'climate',  # Living Web Farms
}

# Broad title fallback for videos whose channel has not already been classified.
TITLE_FALLBACK_RULES = [
    (re.compile(r'\bsystems? programming\b|\boperating systems?\b|\bkernel\b|'
                r'\bfilesystem\b|distributed systems|\bdatabases?\b|\bsqlite\b|'
                r'\bsystemd\b|\bwayland\b|\blinux\b|\bunix\b|\bnetworking\b|'
                r'\bconcurrency\b|\bcompilers?\b', re.I), 'systems'),
    (re.compile(r'\bprogramming\b|\bsoftware\b|\bjavascript\b|\bpython\b|'
                r'\bruby\b|\brails\b|\bcompiler\b|\bclojure\b|\blisp\b|'
                r'\berlang\b|\bhaskell\b|\brust\b|\bgo programming\b|'
                r'\bemacs\b|\bvim\b|object-oriented|\bapi\b|\bopen source\b', re.I), 'programming'),
    (re.compile(r'\bmath(?:ematics|ematical)?\b|\bcalculus\b|\balgebra\b|'
                r'\bgeometry\b|\btopology\b|\btheorem\b|\briemann\b|\bfourier\b|'
                r'\bbayes\b|prime numbers|\bfractals?\b|\bsplines?\b|'
                r'\bb[eé]zier\b|p vs\. np|\bzeta\b', re.I), 'math'),
    (re.compile(r'\bgame boy\b|\bgame development\b|\bgameplay\b|\bvideo games?\b|'
                r'\bnes game\b|\bdoom\b|\bminecraft\b|\bstarcraft\b', re.I), 'games'),
    (re.compile(r'\bdocumentary\b|full film|feature film|\bfilm by\b|'
                r'\bthe movie\b', re.I), 'documentary'),
]


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


def _unique_videos(videos):
    seen = set()
    result = []
    for video in videos:
        video_id = video.get('id')
        if video_id and video_id not in seen:
            seen.add(video_id)
            result.append(video)
    return result


def _merge_cluster_ids(clusters, merges):
    by_id = {cluster['id']: cluster for cluster in clusters}
    for source_id, target_id in merges.items():
        source = by_id.pop(source_id, None)
        if source is None:
            continue
        target = by_id.get(target_id)
        if target is None:
            source['id'] = target_id
            by_id[target_id] = source
            continue
        target['videos'] = _unique_videos(target['videos'] + source['videos'])
    return list(by_id.values())


def _curation_target(video):
    channel_id = video.get('channel_id') or ''
    title = video.get('title') or ''
    if channel_id in HARD_CHANNEL_TOPIC:
        return True, HARD_CHANNEL_TOPIC[channel_id]
    for pattern, target in TITLE_TOPIC_RULES:
        if pattern.search(title):
            return True, target
    if channel_id in CHANNEL_TOPIC:
        return True, CHANNEL_TOPIC[channel_id]
    for pattern, target in TITLE_FALLBACK_RULES:
        if pattern.search(title):
            return True, target
    return False, None


def _curate_clusters(clusters):
    by_id = {cluster['id']: cluster for cluster in clusters}
    members = defaultdict(list)
    for cluster in clusters:
        for video in cluster['videos']:
            matched, target = _curation_target(video)
            if matched and target is None:
                continue
            destination = target if matched else cluster['id']
            if destination not in by_id:
                meta = SIGNAL_META.get(destination)
                if meta is None:
                    destination = cluster['id']
                else:
                    by_id[destination] = {
                        'id': destination,
                        'name_zh': meta[1],
                        'videos': [],
                    }
            members[destination].append(video)
    result = []
    for cluster in clusters:
        cluster_id = cluster['id']
        if members.get(cluster_id):
            result.append({**cluster, 'videos': _unique_videos(members[cluster_id])})
    for cluster_id, videos in members.items():
        if cluster_id not in {cluster['id'] for cluster in result}:
            result.append({**by_id[cluster_id], 'videos': _unique_videos(videos)})
    return result


def _merge_duplicate_names(clusters):
    by_name = {}
    result = []
    for cluster in sorted(clusters, key=lambda item: (-len(item['videos']), item['id'])):
        same_name = by_name.get(cluster['name_zh'])
        if same_name is None:
            by_name[cluster['name_zh']] = cluster
            result.append(cluster)
        else:
            same_name['videos'] = _unique_videos(same_name['videos'] + cluster['videos'])
    return result


def _cluster_centroid(videos):
    acc = {}
    for video in videos:
        _add_into(acc, _binary_vector(video))
    return _normalize(acc) if acc else {}


def _drop_or_merge_underfilled(clusters):
    """Merge a small cluster into its closest honest neighbour, or drop it."""
    clusters = [cluster for cluster in clusters if cluster['videos']]
    merged = []
    dropped = []
    while True:
        underfilled = sorted(
            (cluster for cluster in clusters if len(cluster['videos']) < MIN_CLUSTER),
            key=lambda cluster: (len(cluster['videos']), cluster['id']),
        )
        if not underfilled:
            break
        source = underfilled[0]
        source_centroid = _cluster_centroid(source['videos'])
        best = None
        for candidate in sorted((cluster for cluster in clusters if cluster is not source),
                                key=lambda cluster: cluster['id']):
            similarity = _cosine(source_centroid, _cluster_centroid(candidate['videos']))
            if best is None or similarity > best[0]:
                best = (similarity, candidate)
        if best is not None and best[0] >= 0.12:
            best[1]['videos'] = _unique_videos(best[1]['videos'] + source['videos'])
            clusters.remove(source)
            merged.append((source['id'], best[1]['id']))
        else:
            clusters.remove(source)
            dropped.append(source['id'])
    return clusters, merged, dropped


def _refresh_cluster_signals(clusters):
    all_cluster_lists = [cluster['videos'] for cluster in clusters]
    for cluster in clusters:
        keywords, bigrams, signal = _cluster_signals(cluster['videos'], all_cluster_lists)
        cluster['keywords'] = keywords
        cluster['bigrams'] = bigrams
        cluster['signal'] = signal
    return clusters


def _load_editorial(root='site/src/data'):
    videos = []
    for name in ('picks', 'trending', 'ai', 'podcast', 'music', 'editorial', 'videos'):
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
    if not clusters:
        return lookup
    centroids = _topic_centroids(pool, clusters)
    fallback_topic = sorted(centroids)[0]
    for video in pool:
        if video['id'] in lookup:
            continue
        doc = _binary_vector({**video, 'quotes': []})
        if not doc:
            lookup[video['id']] = fallback_topic
            continue
        nearest = max(sorted(centroids), key=lambda topic_id: _cosine(doc, centroids[topic_id]))
        lookup[video['id']] = nearest
    editorial = _load_editorial()
    pool_ids = {video['id'] for video in pool}
    unknown = [video for video in editorial if video.get('id') and video['id'] not in pool_ids]
    if unknown:
        for video in unknown:
            record = {**video, 'quotes': []}
            doc = _binary_vector(record)
            if not doc:
                continue
            nearest = max(sorted(centroids), key=lambda topic_id: _cosine(doc, centroids[topic_id]))
            if _cosine(doc, centroids[nearest]) >= 0.1:
                lookup[video['id']] = nearest
    metadata = {video['id']: video for video in pool if video.get('id')}
    metadata.update({video['id']: video for video in editorial if video.get('id')})
    lookup, _changed = retag_topic_lookup(lookup, metadata)
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
    clusters = _merge_cluster_ids(clusters, CLUSTER_MERGES)
    clusters = _curate_clusters(clusters)
    clusters = _merge_duplicate_names(clusters)
    shipped, merged_topics, dropped_topics = _drop_or_merge_underfilled(clusters)
    shipped = _refresh_cluster_signals(shipped)
    names = [cluster['name_zh'] for cluster in shipped]
    if len(names) != len(set(names)):
        raise ValueError(f'duplicate topic display names: {names}')
    editorial = _load_editorial()
    lookup = _primary_topic_lookup(pool, shipped)
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
    if merged_topics:
        print('Merged underfilled topics:', ', '.join(f'{source}->{target}' for source, target in merged_topics))
    if dropped_topics:
        print('Dropped underfilled topics:', ', '.join(dropped_topics))
    return payload


if __name__ == '__main__':
    payload = build_topics()
    for topic in payload['topics']:
        print(f"{topic['id']:22} {topic['name_zh']:12} n={len(topic['video_ids'])} "
              f"added24h={topic['added_last_24h']} kw={topic['keywords']}")
