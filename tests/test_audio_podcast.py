import html
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from ytrec import audio_podcast as ap


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def rss_item(
    title,
    *,
    guid=None,
    description=None,
    content=None,
    pub_date=None,
    audio_url=None,
    duration=None,
    author=None,
    link=None,
):
    parts = [f"<title>{html.escape(title)}</title>"]
    if guid is not None:
        parts.append(f'<guid isPermaLink="false">{html.escape(guid)}</guid>')
    if description is not None:
        parts.append(f"<description><![CDATA[{description}]]></description>")
    if content is not None:
        parts.append(f"<content:encoded><![CDATA[{content}]]></content:encoded>")
    if pub_date is not None:
        parts.append(f"<pubDate>{html.escape(pub_date)}</pubDate>")
    if audio_url is None:
        audio_url = f"https://cdn.example.test/{html.escape(guid or title)}.mp3"
    parts.append(
        f'<enclosure url="{html.escape(audio_url)}" type="audio/mpeg" length="1234" />'
    )
    if duration is not None:
        parts.append(f"<itunes:duration>{html.escape(str(duration))}</itunes:duration>")
    if author:
        parts.append(f"<itunes:author>{html.escape(author)}</itunes:author>")
    if link:
        parts.append(f"<link>{html.escape(link)}</link>")
    return "<item>" + "".join(parts) + "</item>"


def rss_doc(items, *, title="测试播客", author="测试发布者", copyright_text="Copyright 测试"):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{html.escape(title)}</title>
    <link>https://publisher.example.test/show</link>
    <description><![CDATA[<p>节目简介</p>]]></description>
    <itunes:author>{html.escape(author)}</itunes:author>
    <copyright>{html.escape(copyright_text)}</copyright>
    <language>zh-CN</language>
    {''.join(items)}
  </channel>
</rss>'''.encode("utf-8")


def show_config(slug, *, rss_url=None, name=None, host_kind="xiaoyuzhou"):
    return {
        "name": name or slug,
        "display_name": name or slug,
        "slug": slug,
        "publisher": f"{slug} publisher",
        "host_kind": host_kind,
        "rss_url": rss_url or f"https://feeds.example.test/{slug}.xml",
        "source_page": f"https://publisher.example.test/{slug}",
        "optional_spotify": None,
        "apple": None,
        "status": "enabled",
    }


def write_config(tmp_path, shows, planned=None):
    path = tmp_path / "audio_podcasts.yaml"
    path.write_text(yaml.safe_dump({
        "shows": shows,
        "planned_shows": planned or [],
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_config_contains_exact_enabled_shows_and_empty_planned_shows():
    config = ap.load_config(ROOT / "config/audio_podcasts.yaml")
    expected = [
        (
            "岩中花述", "岩中花述", "yan-zhong-hua-shu", "GIADA", "xiaoyuzhou",
            "https://feed.xyzfm.space/hwen8wf69c6g",
            "https://www.xiaoyuzhoufm.com/podcast/625635587bfca4e73e990703",
            "https://open.spotify.com/show/6JukZBKKuvslkEUmfmlZTh",
            "https://podcasts.apple.com/cn/podcast/岩中花述/id1582119137",
        ),
        (
            "知行小酒馆", "知行小酒馆", "zhi-xing-xiao-jiu-guan", "有知有行", "xiaoyuzhou",
            "https://feed.xyzfm.space/j8yp8gxkmgqr",
            "https://www.xiaoyuzhoufm.com/podcast/6013f9f58e2f7ee375cf4216",
            "https://open.spotify.com/show/2XeU495v6CZvBuRcVEbfQI",
            "https://podcasts.apple.com/cn/podcast/知行小酒馆/id1559695855",
        ),
        (
            "无人知晓", "无人知晓", "wu-ren-zhi-xiao", "孟岩", "xiaoyuzhou",
            "https://feed.xyzfm.space/ypn9dydpbxpc",
            "https://www.xiaoyuzhoufm.com/podcast/611719d3cb0b82e1df0ad29e",
            "https://open.spotify.com/show/4TY2xLrxqaOEffz4B8eXpi",
            "https://podcasts.apple.com/cn/podcast/无人知晓/id1581271335",
        ),
        (
            "面基", "面基", "mian-ji", "面基", "xiaoyuzhou",
            "https://feed.xyzfm.space/6hpdgggtxpxb",
            "https://www.xiaoyuzhoufm.com/podcast/6388760f22567e8ea6ad070f",
            "https://open.spotify.com/show/65XM7rQOU05IRxFX0jVjsH",
            "https://podcasts.apple.com/cn/podcast/面基/id1686741064",
        ),
        (
            "谭立人", "谭立人", "tan-li-ren", "谭立人", "xiaoyuzhou",
            "https://feed.xyzfm.space/nh9mphjxn8u7",
            "https://www.xiaoyuzhoufm.com/podcast/65a2d0f07242f9fc1c1df60a",
            "https://open.spotify.com/show/61RHBnuUh4CVLqvWFsaLOk",
            "https://podcasts.apple.com/cn/podcast/谭立人/id1771401634",
        ),
        (
            "自我进化论", "自我进化论", "zi-wo-jin-hua-lun", "颜晓静Athena", "xiaoyuzhou",
            "https://feed.xyzfm.space/artr8kfmlmxh",
            "https://www.xiaoyuzhoufm.com/podcast/5e5de5cb418a84a0467beb90",
            "https://open.spotify.com/show/4esvXRFo24ukSH01RwDCy9",
            "https://podcasts.apple.com/cn/podcast/自我进化论/id1498170617",
        ),
        (
            "忽左忽右", "忽左忽右", "hu-zuo-hu-you", "JustPod", "xiaoyuzhou",
            "https://feed.xyzfm.space/cv4bkgpuglwp",
            "https://www.xiaoyuzhoufm.com/podcast/5e4ee557418a84a0466737b7",
            "https://open.spotify.com/show/1Fm6RmlyY9YsqoOLMBQpxJ",
            "https://podcasts.apple.com/cn/podcast/忽左忽右/id1493503146",
        ),
        (
            "独树不成林", "独树不成林", "du-shu-bu-cheng-lin", "鬼鬼祟祟的树", "xiaoyuzhou",
            "https://feed.xyzfm.space/y9qnpfdrctnx",
            "https://www.xiaoyuzhoufm.com/podcast/64acd33c7a3d479103fbd32d",
            "https://open.spotify.com/show/054BlO7x8pvcblbzxq8BxU",
            "https://podcasts.apple.com/cn/podcast/独树不成林/id1711052890",
        ),
        (
            "正经叭叭", "正经叭叭", "zheng-jing-ba-ba", "惊讶喜剧", "xiaoyuzhou",
            "https://feed.xyzfm.space/t7hdrqbuxmqr",
            "https://www.xiaoyuzhoufm.com/podcast/60e43cecc4e7c8188c2f92a4",
            "https://open.spotify.com/show/39TlHlfNXzhYe59G7ETdv8",
            "https://podcasts.apple.com/cn/podcast/正经叭叭/id1575323064",
        ),
        (
            "张小珺商业访谈录", "张小珺Jùn｜商业访谈录", "zhang-xiao-jun", "张小珺", "xiaoyuzhou",
            "https://feed.xyzfm.space/dk4yh3pkpjp3",
            "https://www.xiaoyuzhoufm.com/podcast/626b46ea9cbbf0451cf5a962",
            "https://open.spotify.com/show/2g0V13H8ZqZao5uqpJJkZs",
            "https://podcasts.apple.com/cn/podcast/张小珺Jùn｜商业访谈录/id1634356920",
        ),
        (
            "故事FM", "故事FM", "story-fm", "寇爱哲", "storyfm",
            "https://feeds.storyfm.cn/storyfm.xml",
            "https://storyfm.cn/",
            "https://open.spotify.com/show/3ROMNljvYu6nHCTpklrOS6",
            "https://podcasts.apple.com/cn/podcast/故事FM/id1256399960",
        ),
        (
            "纵横四海", "纵横四海", "zong-heng-si-hai", "携隐Melody", "ximalaya",
            "https://www.ximalaya.com/album/67531569.xml",
            "https://www.ximalaya.com/album/67531569",
            None,
            "https://podcasts.apple.com/cn/podcast/纵横四海/id1671490972",
        ),
        (
            "文化有限", "文化有限", "wen-hua-you-xian", "文化有限", "wavpub",
            "https://s1.proxy.wavpub.com/weknownothing.xml",
            "https://www.ximalaya.com/album/29887212",
            None,
            "https://podcasts.apple.com/cn/podcast/文化有限/id1482731836",
        ),
        (
            "声动早咖啡", "声动早咖啡", "sheng-dong-zao-ka-fei", "声动活泼", "ximalaya",
            "https://www.ximalaya.com/album/51076156.xml",
            "https://www.ximalaya.com/album/51076156",
            None,
            "https://podcasts.apple.com/cn/podcast/声动早咖啡/id1573189055",
        ),
        (
            "谐星聊天会", "谐星聊天会", "xie-xing-liao-tian-hui", "单立人喜剧", "danlirencomedy",
            "https://feeds.danlirencomedy.com/xxlth.xml",
            "https://www.danlirencomedy.cn/",
            None,
            "https://podcasts.apple.com/cn/podcast/谐星聊天会/id1488080680",
        ),
    ]
    assert len(config["shows"]) == 40
    assert config["catalog"]["categories"] == ["认知", "商业", "心理", "人文", "搞笑", "生活"]
    assert {show["category"] for show in config["shows"]} == set(config["catalog"]["categories"])
    assert {show["name"] for show in config["shows"]}.isdisjoint({"张小珺商业访谈录", "悬而未决"})
    assert next(show for show in config["shows"] if show["name"] == "声动早咖啡")["daily_update"] is True
    xuan = next(show for show in config["shows"] if show["slug"] == "xuan-er-wei-jue")
    assert xuan["name"] == "玄而未决"
    assert xuan["category"] == "心理"
    assert xuan["apple_collection_id"] == "1639994222"
    assert xuan["source_status"] == "identity_verified_feed_unavailable"
    assert xuan["source_page"] == "https://www.xiaoyuzhoufm.com/podcast/62d8ea30977d5e2e1bfc534a"
    assert config["catalog"]["missing_shows"] == []
    assert config["planned_shows"] == []
    assert all(show["apple_collection_id"].isdigit() for show in config["shows"])


def test_real_config_has_no_planned_shows_and_no_network_never_fetches(tmp_path, monkeypatch):
    config = ap.load_config(ROOT / "config/audio_podcasts.yaml")
    assert config["planned_shows"] == []

    def unexpected_network(*args, **kwargs):
        raise AssertionError("--no-network must not fetch")

    monkeypatch.setattr(ap, "fetch_rss", unexpected_network)
    export = ap.ingest(
        config_path=ROOT / "config/audio_podcasts.yaml",
        output_path=tmp_path / "audio_podcast.json",
        cache_dir=tmp_path / "cache",
        now=NOW,
        no_network=True,
    )
    assert len(export["shows"]) == 40
    assert export["show_count"] == 40
    assert all(show["status"] == "enabled" for show in export["shows"])
    assert export["planned_shows"] == []


def test_full_real_config_visits_every_show_and_imports_steve_rss_fixture(tmp_path, monkeypatch):
    """A first import must not silently retain the old 15-show snapshot."""
    config = ap.load_config(ROOT / "config/audio_podcasts.yaml")
    steve = next(show for show in config["shows"] if show["slug"] == "steve-shuo")
    seen = []

    def fixture_fetch(url, **kwargs):
        seen.append(url)
        if url == steve["rss_url"]:
            return rss_doc([
                rss_item("Steve fixture episode", guid="steve-fixture-1", pub_date="2026-11-20T00:00:00Z"),
            ], title="史蒂夫说")
        raise OSError("fixture has no publisher response")

    monkeypatch.setattr(ap, "fetch_rss", fixture_fetch)
    export = ap.ingest(
        config_path=ROOT / "config/audio_podcasts.yaml",
        output_path=tmp_path / "audio_podcast.json",
        cache_dir=tmp_path / "cache",
        now=NOW,
    )

    assert len(export["shows"]) == 40
    assert set(seen) == {show["rss_url"] for show in config["shows"]}
    imported = next(show for show in export["shows"] if show["slug"] == "steve-shuo")
    assert imported["fetch_status"] == "fresh"
    assert imported["episode_count"] == 1
    assert imported["episodes"][0]["episode_id"] == "steve-fixture-1"


def test_html_response_is_not_a_successful_rss_import(tmp_path, monkeypatch):
    config = ap.load_config(ROOT / "config/audio_podcasts.yaml")
    monkeypatch.setattr(ap, "fetch_rss", lambda *_args, **_kwargs: b"<!doctype html><title>challenge</title>")
    export = ap.ingest(
        config_path=ROOT / "config/audio_podcasts.yaml",
        output_path=tmp_path / "audio_podcast.json",
        cache_dir=tmp_path / "cache",
        now=NOW,
        only_show="xuan-er-wei-jue",
    )
    record = export["shows"][0]
    assert record["fetch_status"] == "unavailable"
    assert record["episode_count"] == 0
    assert "FeedParseError" in record["fetch_error"]


def test_fetch_rss_is_bounded_polite_and_never_requests_audio(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        headers = {"Content-Type": "application/rss+xml; charset=utf-8"}

        def iter_content(self, chunk_size):
            assert chunk_size == 65536
            yield b"<rss><channel><title>x</title></channel></rss>"

        def close(self):
            pass

    class Session:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response()

    payload = ap.fetch_rss("https://feeds.example.test/show.xml", session=Session())

    assert payload.startswith(b"<rss>")
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://feeds.example.test/show.xml"
    assert kwargs["timeout"] == 45
    assert kwargs["allow_redirects"] is True
    assert "fewgood-audio" in kwargs["headers"]["User-Agent"]


def test_fetch_rss_rejects_oversize_payload():
    class Response:
        status_code = 200
        headers = {"Content-Type": "application/xml"}

        def iter_content(self, chunk_size):
            yield b"x" * 20

        def close(self):
            pass

    class Session:
        def get(self, url, **kwargs):
            return Response()

    with pytest.raises(ap.RSSFetchError, match="size limit"):
        ap.fetch_rss("https://feeds.example.test/show.xml", session=Session(), max_bytes=10)


def test_fetch_rss_rejects_html_response_before_parsing():
    class Response:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def iter_content(self, _chunk_size):
            yield b"<!doctype html><title>challenge</title>"

        def close(self):
            pass

    class Session:
        def get(self, _url, **_kwargs):
            return Response()

    with pytest.raises(ap.RSSFetchError, match="non-XML"):
        ap.fetch_rss("https://feeds.example.test/show.xml", session=Session())


def test_vistopia_official_http_enclosures_upgrade_to_https_and_keep_every_item():
    items = [
        rss_item(
            f"Vistopia {index}",
            guid=f"vistopia-{index}",
            pub_date=f"2026-11-{10 + index:02d}T00:00:00Z",
            audio_url=f"http://cdn5.vistopia.com.cn/{index}.mp3",
        )
        for index in range(1, 4)
    ]
    result = ap.parse_feed(rss_doc(items), {"host_kind": "vistopia"})
    assert result["stats"]["item_count"] == len(items)
    assert result["stats"]["episode_count"] == len(items)
    assert result["stats"]["invalid_media_count"] == 0
    assert [episode["audio_url"] for episode in result["episodes"]] == [
        "https://cdn5.vistopia.com.cn/3.mp3",
        "https://cdn5.vistopia.com.cn/2.mp3",
        "https://cdn5.vistopia.com.cn/1.mp3",
    ]


def test_http_enclosure_from_non_allowlisted_host_is_still_rejected():
    result = ap.parse_feed(rss_doc([
        rss_item("Untrusted", guid="untrusted", audio_url="http://cdn.example.test/untrusted.mp3"),
    ]))
    assert result["stats"]["item_count"] == 1
    assert result["stats"]["episode_count"] == 0
    assert result["stats"]["invalid_media_count"] == 1


def test_only_show_merges_into_existing_export_without_dropping_other_shows(tmp_path, monkeypatch):
    config_path = write_config(tmp_path, [show_config("vistopia", host_kind="vistopia"), show_config("other")])
    feeds = {
        "https://feeds.example.test/vistopia.xml": rss_doc([
            rss_item("Vistopia", guid="vistopia-one", audio_url="http://cdn5.vistopia.com.cn/vistopia-one.mp3"),
        ]),
        "https://feeds.example.test/other.xml": rss_doc([
            rss_item("Other", guid="other-one"),
        ]),
    }
    monkeypatch.setattr(ap, "fetch_rss", lambda url, **_kwargs: feeds[url])
    output = tmp_path / "audio_podcast.json"
    cache = tmp_path / "cache"
    first = ap.ingest(config_path=config_path, output_path=output, cache_dir=cache, now=NOW)
    assert {show["slug"] for show in first["shows"]} == {"vistopia", "other"}

    monkeypatch.setattr(ap, "fetch_rss", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no network")))
    merged = ap.ingest(
        config_path=config_path,
        output_path=output,
        cache_dir=cache,
        now=NOW,
        no_network=True,
        only_show="vistopia",
    )
    by_slug = {show["slug"]: show for show in merged["shows"]}
    assert set(by_slug) == {"vistopia", "other"}
    assert by_slug["vistopia"]["fetch_status"] == "cache_only"
    assert by_slug["vistopia"]["episodes"][0]["audio_url"] == "https://cdn5.vistopia.com.cn/vistopia-one.mp3"
    assert by_slug["other"]["episodes"][0]["episode_id"] == "other-one"


def test_parser_strips_malicious_html_and_sanitizes_title():
    description = (
        '<p onclick="evil()">Hello '
        '<a href="https://example.com/a">safe</a> '
        '<a href="javascript:alert(1)">js</a> '
        '<a href="data:text/html;base64,PHNjcmlwdD4=">data</a>'
        '<img src="https://tracker.example/x" onerror="alert(1)">'
        '<script>alert(1)</script><iframe src="https://evil.example">fallback</iframe>'
        '<strong>bold</strong></p>'
    )
    result = ap.parse_feed(rss_doc([rss_item(
        '<img src=x onerror=alert(1)>Safe <script>bad()</script>Title',
        guid="malicious-html",
        description=description,
        pub_date="2026-11-14T12:00:00Z",
    )]))
    episode = result["episodes"][0]
    assert episode["title"] == "Safe Title"
    assert '<a href="https://example.com/a">safe</a>' in episode["description_html"]
    assert "<strong>bold</strong>" in episode["description_html"]
    lowered = episode["description_html"].lower()
    for banned in ("<script", "<iframe", "onerror", "onclick", "javascript:", "data:", "fallback"):
        assert banned not in lowered


def test_parser_sanitizes_actual_child_tags_inside_rss_elements():
    xml = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Nested</title>
  <item>
    <title>Nested<script>bad()</script>Title</title>
    <guid>nested-child-tags</guid>
    <description><p>Hello<script>bad()</script><strong>bold</strong></p></description>
    <enclosure url="https://cdn.example.test/nested.mp3" type="audio/mpeg" />
  </item>
</channel></rss>'''
    episode = ap.parse_feed(xml)["episodes"][0]
    assert episode["title"] == "NestedTitle"
    assert episode["description_html"] == "<p>Hello<strong>bold</strong></p>"
    assert "bad()" not in episode["title"]
    assert "bad()" not in episode["description_html"]


def test_missing_and_truncated_descriptions_are_flagged():
    result = ap.parse_feed(rss_doc([
        rss_item("Missing", guid="missing", description=None),
        rss_item(
            "Marker truncation", guid="marker",
            description="<p>这是一段简介。</p><p>去小宇宙查看完整单集简介</p>",
        ),
        rss_item("Cut note", guid="cut", description="<p>" + ("很长的正文" * 30) + "...</p>"),
        rss_item("Script only", guid="script-only", description="<script>alert(1)</script>"),
    ]))
    episodes = {episode["guid"]: episode for episode in result["episodes"]}
    assert episodes["missing"]["description_missing"] is True
    assert episodes["missing"]["description_truncated"] is False
    assert episodes["marker"]["description_missing"] is False
    assert episodes["marker"]["description_truncated"] is True
    assert episodes["cut"]["description_truncated"] is True
    assert episodes["script-only"]["description_missing"] is True


def test_duplicate_guids_and_fallback_keys_collapse_and_http_media_is_rejected():
    result = ap.parse_feed(rss_doc([
        rss_item("GUID first", guid="duplicate-guid", description="first", pub_date="2026-11-14T12:00:00Z"),
        rss_item("GUID second", guid="duplicate-guid", description="second", pub_date="2026-11-14T12:00:00Z"),
        rss_item("Fallback same", description="one", pub_date="2026-11-13T12:00:00Z",
                 audio_url="https://cdn.example.test/fallback.mp3"),
        rss_item("Fallback same", description="two", pub_date="2026-11-13T12:00:00Z",
                 audio_url="https://cdn.example.test/fallback.mp3"),
        rss_item("Different fallback", description="three", pub_date="2026-11-12T12:00:00Z",
                 audio_url="https://cdn.example.test/fallback.mp3"),
        rss_item("HTTP rejected", guid="http", audio_url="http://cdn.example.test/http.mp3"),
    ]))

    assert result["stats"]["duplicate_count"] == 2
    assert result["stats"]["invalid_media_count"] == 1
    assert len(result["episodes"]) == 3
    assert {episode["title"] for episode in result["episodes"]} == {
        "GUID first", "Fallback same", "Different fallback",
    }
    assert all(episode["audio_url"].startswith("https://") for episode in result["episodes"])


@pytest.mark.parametrize(("host_kind", "title", "audio_url"), [
    (
        "ximalaya",
        "纵横四海",
        "https://jt.ximalaya.com//aod.cos.tx.xmcdn.com/group1/M00/00/zong-heng-si-hai.m4a"
        "?channel=rss&album_id=67531569&jt=https://aod.cos.tx.xmcdn.com/storages/zong-heng-si-hai.m4a",
    ),
    (
        "wavpub",
        "文化有限",
        "https://tk.wavpub.com/weknownothing/2026/11/audio.mp3?timestamp=1763200000&sign=abc123",
    ),
    (
        "danlirencomedy",
        "谐星聊天会",
        "https://feeds.danlirencomedy.com/audio/xxlth/episode-123.mp3",
    ),
])
def test_representative_host_feeds_preserve_official_enclosure_urls(host_kind, title, audio_url):
    result = ap.parse_feed(
        rss_doc([
            rss_item(
                title,
                guid=f"{host_kind}-representative",
                description="<p>发布者提供的原始单集简介。</p>",
                pub_date="2026-11-15T04:00:00Z",
                audio_url=audio_url,
                duration="48:12",
            ),
        ], title=f"{title} RSS"),
        {"host_kind": host_kind},
    )
    episode = result["episodes"][0]
    assert result["feed"]["title"] == f"{title} RSS"
    assert episode["title"] == title
    assert episode["audio_url"] == audio_url
    assert episode["duration_seconds"] == 2892
    assert episode["duration_display"] == "48:12"


@pytest.mark.parametrize("host_kind", ["ximalaya", "wavpub", "danlirencomedy"])
def test_host_feeds_reject_malformed_xml(host_kind):
    with pytest.raises(ap.FeedParseError, match="malformed XML"):
        ap.parse_feed(b"<rss><channel><title>broken</title>", {"host_kind": host_kind})


def test_host_feeds_flag_truncated_and_missing_metadata():
    result = ap.parse_feed(rss_doc([
        rss_item(
            "纵横四海",
            guid="ximalaya-truncated",
            description="<p>节目简介。</p><p>去小宇宙查看完整单集简介</p>",
        ),
        rss_item("文化有限", guid="wavpub-missing", description=None),
        rss_item(
            "谐星聊天会",
            guid="danliren-missing-date",
            description="<p>" + ("发布者简介" * 30) + "...</p>",
        ),
    ]))
    by_guid = {episode["guid"]: episode for episode in result["episodes"]}
    assert by_guid["ximalaya-truncated"]["description_truncated"] is True
    assert by_guid["wavpub-missing"]["description_missing"] is True
    assert by_guid["danliren-missing-date"]["description_truncated"] is True
    assert by_guid["danliren-missing-date"]["published_at"] is None


@pytest.mark.parametrize("host_kind", ["ximalaya", "wavpub", "danlirencomedy"])
def test_host_feeds_reject_non_https_enclosures(host_kind):
    result = ap.parse_feed(rss_doc([
        rss_item(
            f"{host_kind} HTTP",
            guid=f"{host_kind}-http",
            audio_url=f"http://cdn.example.test/{host_kind}.mp3",
        ),
    ]))
    assert result["episodes"] == []
    assert result["stats"]["invalid_media_count"] == 1


def test_wavpub_dedup_keeps_same_titles_with_distinct_guids_and_dates():
    result = ap.parse_feed(rss_doc([
        rss_item(
            "文化有限",
            guid="wen-hua-2026-11-14",
            description="第一期",
            pub_date="2026-11-14T12:00:00Z",
            audio_url="https://tk.wavpub.com/weknownothing/first.mp3",
        ),
        rss_item(
            "文化有限",
            guid="wen-hua-2026-11-07",
            description="第二期",
            pub_date="2026-11-07T12:00:00Z",
            audio_url="https://tk.wavpub.com/weknownothing/second.mp3",
        ),
        rss_item(
            "文化有限",
            guid="wen-hua-2026-11-14",
            description="重复的第一期",
            pub_date="2026-11-14T12:00:00Z",
            audio_url="https://tk.wavpub.com/weknownothing/first.mp3",
        ),
    ]))
    assert result["stats"]["duplicate_count"] == 1
    assert [episode["guid"] for episode in result["episodes"]] == [
        "wen-hua-2026-11-14", "wen-hua-2026-11-07",
    ]
    assert {episode["title"] for episode in result["episodes"]} == {"文化有限"}


def test_host_cache_fallback_does_not_wipe_another_hosts_cache(tmp_path, monkeypatch):
    ximalaya_url = "https://www.ximalaya.com/album/67531569.xml"
    wavpub_url = "https://s1.proxy.wavpub.com/weknownothing.xml"
    danliren_url = "https://feeds.danlirencomedy.com/xxlth.xml"
    shows = [
        show_config("zong-heng-si-hai", host_kind="ximalaya", rss_url=ximalaya_url),
        show_config("wen-hua-you-xian", host_kind="wavpub", rss_url=wavpub_url),
        show_config("xie-xing-liao-tian-hui", host_kind="danlirencomedy", rss_url=danliren_url),
    ]
    config_path = write_config(tmp_path, shows)
    feeds = {
        ximalaya_url: rss_doc([rss_item("纵横四海", guid="xhs-old", pub_date="2026-11-14T12:00:00Z")]),
        wavpub_url: rss_doc([rss_item("文化有限", guid="wh-old", pub_date="2026-11-14T12:00:00Z")]),
        danliren_url: rss_doc([rss_item("谐星聊天会", guid="xxlth-old", pub_date="2026-11-14T12:00:00Z")]),
    }
    failing = {"ximalaya": False}

    def fake_fetch(url, **kwargs):
        if url == ximalaya_url and failing["ximalaya"]:
            raise ap.RSSFetchError("tracker redirect timed out")
        return feeds[url]

    monkeypatch.setattr(ap, "fetch_rss", fake_fetch)
    output = tmp_path / "out" / "audio_podcast.json"
    cache = tmp_path / "cache"
    ap.ingest(config_path=config_path, output_path=output, cache_dir=cache, now=NOW)
    ximalaya_cache_before = (cache / "zong-heng-si-hai.xml").read_bytes()
    wavpub_cache_before = (cache / "wen-hua-you-xian.xml").read_bytes()

    failing["ximalaya"] = True
    feeds[wavpub_url] = rss_doc([rss_item("文化有限", guid="wh-new", pub_date="2026-11-15T05:00:00Z")])
    feeds[danliren_url] = rss_doc([rss_item("谐星聊天会", guid="xxlth-new", pub_date="2026-11-15T06:00:00Z")])
    export = ap.ingest(config_path=config_path, output_path=output, cache_dir=cache, now=NOW)

    by_slug = {show["slug"]: show for show in export["shows"]}
    assert by_slug["zong-heng-si-hai"]["fetch_status"] == "cache_fallback"
    assert by_slug["zong-heng-si-hai"]["episodes"][0]["episode_id"] == "xhs-old"
    assert by_slug["wen-hua-you-xian"]["fetch_status"] == "fresh"
    assert by_slug["wen-hua-you-xian"]["episodes"][0]["episode_id"] == "wh-new"
    assert by_slug["xie-xing-liao-tian-hui"]["fetch_status"] == "fresh"
    assert by_slug["xie-xing-liao-tian-hui"]["episodes"][0]["episode_id"] == "xxlth-new"
    assert (cache / "zong-heng-si-hai.xml").read_bytes() == ximalaya_cache_before
    assert (cache / "wen-hua-you-xian.xml").read_bytes() != wavpub_cache_before
    assert ap.load_cached_result(cache, "wen-hua-you-xian")["episodes"][0]["episode_id"] == "wh-new"


def test_timezone_offsets_and_date_only_midnight_are_preserved():
    result = ap.parse_feed(rss_doc([
        rss_item("ISO date", guid="iso-date", pub_date="2025-11-14"),
        rss_item("GMT midnight", guid="gmt-midnight", pub_date="Fri, 14 Nov 2025 00:00:00 GMT"),
        rss_item("Shanghai noon", guid="shanghai-noon", pub_date="Fri, 14 Nov 2025 12:00:00 +0800"),
        rss_item("GMT noon", guid="gmt-noon", pub_date="Fri, 14 Nov 2025 12:00:00 GMT"),
    ]))
    by_guid = {episode["guid"]: episode for episode in result["episodes"]}

    for guid in ("iso-date", "gmt-midnight"):
        assert by_guid[guid]["published_date_only"] is True
        assert by_guid[guid]["published_at_asia_shanghai"] == "2025-11-14"
        assert by_guid[guid]["published_display"] == "2025-11-14"
    assert by_guid["gmt-midnight"]["pub_date_raw"] == "Fri, 14 Nov 2025 00:00:00 GMT"

    shanghai = by_guid["shanghai-noon"]
    assert shanghai["published_date_only"] is False
    assert shanghai["published_at_utc"] == "2025-11-14T04:00:00+00:00"
    assert shanghai["published_at_asia_shanghai"] == "2025-11-14T12:00:00+08:00"
    assert shanghai["published_display"] == "2025-11-14 12:00"

    gmt = by_guid["gmt-noon"]
    assert gmt["published_at_asia_shanghai"] == "2025-11-14T20:00:00+08:00"
    assert gmt["published_display"] == "2025-11-14 20:00"


@pytest.mark.parametrize(("raw", "seconds", "display"), [
    ("1:02:03", 3723, "1:02:03"),
    ("02:03", 123, "2:03"),
    ("42", 42, "0:42"),
    ("bad", None, None),
])
def test_duration_parsing_and_display(raw, seconds, display):
    assert ap.parse_duration(raw) == seconds
    assert ap.format_duration(seconds) == display


def test_recent_selection_caps_per_show_and_does_not_backfill(tmp_path, monkeypatch):
    shows = [
        show_config("fresh"),
        show_config("second"),
        show_config("stale"),
        show_config("quiet"),
    ]
    config_path = write_config(tmp_path, shows)

    def at(days):
        return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")

    feeds = {
        "https://feeds.example.test/fresh.xml": rss_doc([
            rss_item("fresh-1", guid="fresh-1", pub_date=at(1)),
            rss_item("fresh-2", guid="fresh-2", pub_date=at(2)),
            rss_item("fresh-3", guid="fresh-3", pub_date=at(3)),
        ]),
        "https://feeds.example.test/second.xml": rss_doc([
            rss_item("second-1", guid="second-1", pub_date=at(4)),
        ]),
        "https://feeds.example.test/stale.xml": rss_doc([
            rss_item("stale-1", guid="stale-1", pub_date=at(40)),
            rss_item("stale-2", guid="stale-2", pub_date=at(45)),
        ]),
        "https://feeds.example.test/quiet.xml": rss_doc([]),
    }
    monkeypatch.setattr(ap, "fetch_rss", lambda url, **kwargs: feeds[url])

    export = ap.ingest(
        config_path=config_path,
        output_path=tmp_path / "out" / "audio_podcast.json",
        cache_dir=tmp_path / "cache",
        now=NOW,
    )
    selection = export["recent_selection"]
    assert selection["candidate_count"] == 4
    assert selection["selected_count"] == 3
    assert [item["episode"]["episode_id"] for item in selection["items"]] == [
        "fresh-1", "fresh-2", "second-1",
    ]
    assert all(item["reason"] == "近30天内更新 · 该节目最多收录2条" for item in selection["items"])
    assert "不会用更旧单集回填" in selection["selection_rules"]
    for banned in ("编辑精选", "听过", "高分", "评分", "全集"):
        assert banned not in json.dumps(export, ensure_ascii=False)

    by_slug = {show["slug"]: show for show in export["shows"]}
    assert by_slug["stale"]["episode_count"] == 2
    assert by_slug["stale"]["episode_count_label"] == "本站已收录单集"
    assert by_slug["quiet"]["episode_count"] == 0
    assert "stale-1" not in [item["episode"]["episode_id"] for item in selection["items"]]

    first_bytes = (tmp_path / "out" / "audio_podcast.json").read_bytes()
    ap.ingest(
        config_path=config_path,
        output_path=tmp_path / "out" / "audio_podcast.json",
        cache_dir=tmp_path / "cache",
        now=NOW,
    )
    assert (tmp_path / "out" / "audio_podcast.json").read_bytes() == first_bytes


def test_recent_selection_excludes_daily_update_shows():
    daily = {
        "slug": "daily", "display_name": "Daily", "publisher": "Publisher", "host_kind": "ximalaya",
        "daily_update": True,
        "episodes": [{"episode_id": "daily-1", "audio_url": "https://cdn.example.test/daily.mp3", "published_at_utc": "2026-11-15T11:00:00+00:00"}],
    }
    weekly = {
        "slug": "weekly", "display_name": "Weekly", "publisher": "Publisher", "host_kind": "rss",
        "episodes": [{"episode_id": "weekly-1", "audio_url": "https://cdn.example.test/weekly.mp3", "published_at_utc": "2026-11-15T10:00:00+00:00"}],
    }
    selection = ap.select_recent([daily, weekly], NOW)
    assert [item["show_slug"] for item in selection["items"]] == ["weekly"]


def test_transient_failure_uses_cache_without_wiping_other_shows(tmp_path, monkeypatch):
    shows = [show_config("one"), show_config("two")]
    config_path = write_config(tmp_path, shows)
    failing = {"one": False}
    state = {
        "one": rss_doc([rss_item("one-old", guid="one-old", pub_date="2026-11-14T12:00:00Z")]),
        "two": rss_doc([rss_item("two-old", guid="two-old", pub_date="2026-11-14T12:00:00Z")]),
    }

    def fake_fetch(url, **kwargs):
        slug = "one" if "/one." in url else "two"
        if slug == "one" and failing["one"]:
            raise ap.RSSFetchError("temporary upstream failure")
        return state[slug]

    monkeypatch.setattr(ap, "fetch_rss", fake_fetch)
    output = tmp_path / "out" / "audio_podcast.json"
    cache = tmp_path / "cache"
    ap.ingest(config_path=config_path, output_path=output, cache_dir=cache, now=NOW)
    cached_raw = (cache / "one.xml").read_bytes()

    failing["one"] = True
    state["one"] = rss_doc([rss_item("one-new", guid="one-new", pub_date="2026-11-15T05:00:00Z")])
    state["two"] = rss_doc([rss_item("two-new", guid="two-new", pub_date="2026-11-15T06:00:00Z")])
    export = ap.ingest(config_path=config_path, output_path=output, cache_dir=cache, now=NOW)

    by_slug = {show["slug"]: show for show in export["shows"]}
    assert by_slug["one"]["fetch_status"] == "cache_fallback"
    assert by_slug["one"]["cache_used"] is True
    assert by_slug["one"]["episodes"][0]["episode_id"] == "one-old"
    assert "temporary upstream failure" in by_slug["one"]["fetch_error"]
    assert by_slug["two"]["fetch_status"] == "fresh"
    assert by_slug["two"]["episodes"][0]["episode_id"] == "two-new"
    assert (cache / "one.xml").read_bytes() == cached_raw

    def unexpected_network(*args, **kwargs):
        raise AssertionError("network must not be used in --no-network mode")

    monkeypatch.setattr(ap, "fetch_rss", unexpected_network)
    cache_only = ap.ingest(
        config_path=config_path,
        output_path=tmp_path / "out" / "cache-only.json",
        cache_dir=cache,
        now=NOW,
        no_network=True,
    )
    assert {show["fetch_status"] for show in cache_only["shows"]} == {"cache_only"}


def test_ingest_does_not_touch_existing_youtube_feeds_or_nav_labels(tmp_path, monkeypatch):
    protected = [
        "site/src/data/podcast.json",
        "site/src/data/music.json",
        "site/src/data/trending.json",
        "site/src/data/ai.json",
        "site/src/data/channels.json",
        "site/src/components/Header.astro",
        "site/src/components/Sidebar.astro",
    ]
    existing = [ROOT / path for path in protected if (ROOT / path).exists()]
    before = {path: path.read_bytes() for path in existing}
    config_path = write_config(tmp_path, [show_config("safe", name="安全节目")])
    monkeypatch.setattr(
        ap, "fetch_rss",
        lambda url, **kwargs: rss_doc([rss_item("Safe", guid="safe", pub_date="2026-11-14T12:00:00Z")]),
    )

    ap.ingest(
        config_path=config_path,
        output_path=tmp_path / "audio_podcast.json",
        cache_dir=tmp_path / "cache",
        now=NOW,
    )

    assert existing
    assert all(path.read_bytes() == payload for path, payload in before.items())


def test_public_cli_registers_audio_ingest_command():
    result = subprocess.run(
        [sys.executable, "-m", "ytrec", "--help"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert "ingest-audio-podcasts" in result.stdout
    assert "--no-network" in result.stdout


def test_committed_snapshot_fallback_without_local_cache(tmp_path, monkeypatch):
    config = write_config(tmp_path, [show_config('one'), show_config('two')])
    output = tmp_path / 'audio.json'
    def initial_fetch(url, **kwargs):
        slug = 'one' if '/one.' in url else 'two'
        return rss_doc([rss_item(slug, guid=slug, pub_date='2026-11-14T12:00:00Z')]).replace(b'<channel>', b'<channel><itunes:image href="https://publisher.test/cover.jpg"/>')
    monkeypatch.setattr(ap, 'fetch_rss', initial_fetch)
    first = ap.ingest(config_path=config, output_path=output, cache_dir=tmp_path / 'old-cache', now=NOW)
    def mixed_fetch(url, **kwargs):
        if '/one.' in url:
            raise ap.RSSFetchError('temporary failure')
        return rss_doc([rss_item('two-new', guid='two-new', pub_date='2026-11-15T06:00:00Z')])
    monkeypatch.setattr(ap, 'fetch_rss', mixed_fetch)
    second = ap.ingest(config_path=config, output_path=output, cache_dir=tmp_path / 'empty-cache', now=NOW)
    assert second['shows'][0]['fetch_status'] == 'snapshot_fallback'
    assert second['shows'][0]['episodes'] == first['shows'][0]['episodes']
    assert second['shows'][0]['feed']['cover_url'] == first['shows'][0]['feed']['cover_url'] == 'https://publisher.test/cover.jpg'
    assert json.loads(output.read_text())['shows'][0]['feed']['cover_url'] == 'https://publisher.test/cover.jpg'
    assert second['shows'][1]['fetch_status'] == 'fresh'
    assert second['shows'][1]['episodes'][0]['episode_id'] == 'two-new'
    assert '\n  ' not in output.read_text()


def test_publisher_cover_https_only_and_episode_fallback():
    from ytrec.audio_podcast import parse_feed
    xml = '''<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>
    <itunes:image href="https://publisher.test/show.jpg"/>
    <item><guid>a</guid><enclosure url="https://publisher.test/a.mp3"/><itunes:image href="https://publisher.test/episode.jpg"/></item>
    <item><guid>b</guid><enclosure url="https://publisher.test/b.mp3"/><itunes:image href="http://publisher.test/insecure.jpg"/></item>
    </channel></rss>'''
    result = parse_feed(xml.encode())
    assert result['feed']['cover_url'] == 'https://publisher.test/show.jpg'
    covers = {e['guid']: e['cover_url'] for e in result['episodes']}
    assert covers == {'a': 'https://publisher.test/episode.jpg', 'b': 'https://publisher.test/show.jpg'}
    for unsafe in ['http://publisher.test/show.jpg', 'javascript:alert(1)', '//publisher.test/show.jpg', 'data:image/png;base64,xx']:
        result = parse_feed(xml.replace('https://publisher.test/show.jpg', unsafe).encode())
        assert result['feed']['cover_url'] is None
    result = parse_feed(b'<rss><channel><image><url>https://publisher.test/real.jpg</url></image></channel></rss>')
    assert result['feed']['cover_url'] == 'https://publisher.test/real.jpg'
    assert parse_feed(b'<rss><channel/></rss>')['feed']['cover_url'] is None


def test_no_network_reparses_old_cached_xml_for_covers(tmp_path):
    import json
    from ytrec.audio_podcast import _process_show
    show = {'slug': 'cached', 'name': 'cached', 'display_name': 'cached', 'publisher': 'publisher',
            'host_kind': 'storyfm', 'rss_url': 'https://publisher.test/rss', 'source_page': 'https://publisher.test/'}
    (tmp_path / 'cached.json').write_text(json.dumps({'cache_version': 1, 'show_slug': 'cached', 'result': {'feed': {}, 'episodes': []}}))
    (tmp_path / 'cached.xml').write_bytes(b'<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel><itunes:image href="https://publisher.test/cover.jpg"/></channel></rss>')
    class NoNetwork:
        def get(self, *args, **kwargs):
            raise AssertionError('offline cache reparsing must not fetch')
    record = _process_show(show, cache_dir=tmp_path, no_network=True, dry_run=True,
                           session=NoNetwork(), sleep_fn=lambda _: None, fetched_at='2026-11-16T00:00:00Z')
    assert record['feed']['cover_url'] == 'https://publisher.test/cover.jpg'
    assert record['fetch_status'] == 'cache_only'


@pytest.mark.parametrize('cover_tag', [
    '<itunes:image href="https://publisher.test/show.jpg"/>',
    '<image><url>https://publisher.test/show.jpg</url></image>',
])
def test_live_ingest_exports_official_covers_without_prior_cache(tmp_path, cover_tag):
    config = write_config(tmp_path, [show_config('live')])
    output = tmp_path / 'audio.json'
    cache = tmp_path / 'cache'
    item = rss_item('Live', guid='live', pub_date='2026-11-14T12:00:00Z')
    item = item.replace('</item>', '<itunes:image href="https://publisher.test/episode.jpg"/></item>')
    payload = rss_doc([item, rss_item('Inherited', guid='inherited', pub_date='2026-11-13T12:00:00Z')])
    payload = payload.replace(b'<channel>', ('<channel>' + cover_tag).encode())
    calls = []

    class Response:
        status_code = 200
        headers = {'Content-Type': 'application/rss+xml'}

        def iter_content(self, chunk_size):
            yield payload

        def close(self):
            pass

    class Session:
        def get(self, url, **kwargs):
            assert url == 'https://feeds.example.test/live.xml'
            calls.append(url)
            return Response()

    assert not cache.exists() and not output.exists()
    ap.ingest(config_path=config, output_path=output, cache_dir=cache,
              session=Session(), sleep_fn=lambda _: None, now=NOW)
    show = json.loads(output.read_text())['shows'][0]
    assert calls == ['https://feeds.example.test/live.xml']
    assert show['fetch_status'] == 'fresh'
    assert show['feed']['cover_url'] == 'https://publisher.test/show.jpg'
    assert {e['guid']: e['cover_url'] for e in show['episodes']} == {
        'live': 'https://publisher.test/episode.jpg',
        'inherited': 'https://publisher.test/show.jpg',
    }
