import json
from datetime import datetime, timezone

import pytest
import yaml

from ytrec import audio_podcast as ap


NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
PODCAST_ID = "62d8ea30977d5e2e1bfc534a"


def _show(slug="fallback", **overrides):
    show = {
        "name": slug,
        "display_name": slug,
        "slug": slug,
        "publisher": "publisher",
        "host_kind": "xiaoyuzhou",
        "rss_url": f"https://feed.example.test/{slug}.xml",
        "source_page": f"https://www.xiaoyuzhoufm.com/podcast/{PODCAST_ID}",
        "xiaoyuzhou_page_fallback": True,
        "xiaoyuzhou_podcast_id": PODCAST_ID,
        "source_status": "rss_unavailable_limited_public_page",
        "status": "enabled",
    }
    show.update(overrides)
    return show


def _config(path, shows):
    path.write_text(yaml.safe_dump({"shows": shows, "planned_shows": []}, allow_unicode=True), encoding="utf-8")
    return path


def _page(entries, *, image=None):
    payload = {"props": {"pageProps": {"podcast": {
        "title": "官方节目", "description": "<p>节目介绍</p>", "episodeCount": 999,
        "image": image if image is not None else {"picUrl": "https://image.xyzcdn.net/podcast/cover.jpg"},
        "episodes": entries,
    }}}}
    return (
        '<html><script type="application/ld+json">{"requiresSubscription":"no"}</script>'
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload, ensure_ascii=False)
        + "</script></html>"
    ).encode("utf-8")


def _entry(eid="free-1", **overrides):
    entry = {
        "eid": eid,
        "title": "免费单集",
        "pubDate": "2026-11-20T08:00:00.000Z",
        "duration": 125,
        "payType": "FREE",
        "isPrivateMedia": False,
        "shownotes": "<p>保留 <em>内容</em><script>drop()</script></p>",
        "enclosure": {"url": f"https://media.xyzcdn.net/{PODCAST_ID}/{eid}.m4a", "type": "audio/mp4"},
    }
    entry.update(overrides)
    return entry


def _rss(guid):
    return f"""<rss><channel><title>RSS</title><item><title>{guid}</title><guid>{guid}</guid>
    <pubDate>2026-11-21T00:00:00Z</pubDate><enclosure url="https://media.example.test/{guid}.mp3" /></item>
    </channel></rss>""".encode()


def test_public_page_accepts_only_free_pid_scoped_media_and_sanitizes_description():
    result = ap.parse_xiaoyuzhou_public_page(_page([
        _entry(),
        _entry("paid", payType="PAY_EPISODE", isPrivateMedia=True, requiresSubscription="no"),
        _entry("not-free", payType="TRIAL"),
        _entry("private", isPrivateMedia=True),
        _entry("placeholder", enclosure={"url": "https://media.xyzcdn.net/FiOrBdbOS-STpCiLoCfcqTw-x5sp.m4a"}),
        _entry("wrong-host", enclosure={"url": f"https://example.test/{PODCAST_ID}/wrong.m4a"}),
        _entry("http", enclosure={"url": f"http://media.xyzcdn.net/{PODCAST_ID}/http.m4a"}),
    ]), _show())

    assert result["stats"]["item_count"] == 7
    assert result["stats"]["episode_count"] == 1
    assert result["stats"]["invalid_media_count"] == 6
    assert result["limited_public_page_fallback"] is True
    assert result["feed"]["cover_url"] == "https://image.xyzcdn.net/podcast/cover.jpg"
    episode = result["episodes"][0]
    assert episode["episode_id"] == "free-1"
    assert episode["guid"] == "free-1"
    assert episode["audio_url"] == f"https://media.xyzcdn.net/{PODCAST_ID}/free-1.m4a"
    assert episode["duration_seconds"] == 125
    assert episode["published_at_utc"] == "2026-11-20T08:00:00+00:00"
    assert episode["cover_url"] == "https://image.xyzcdn.net/podcast/cover.jpg"
    assert "script" not in episode["description_html"]
    assert "drop" not in episode["description_text"]
    assert result["episodes"].__len__() != 999


def test_page_fallback_is_opt_in_and_never_preempts_valid_rss(tmp_path, monkeypatch):
    fallback = _show()
    ordinary = _show("ordinary", xiaoyuzhou_page_fallback=None, xiaoyuzhou_podcast_id=None,
                     source_page="https://publisher.example.test/ordinary")
    config = _config(tmp_path / "config.yaml", [fallback, ordinary])
    calls = []

    def fetch_rss(url, **_kwargs):
        if "fallback" in url:
            return _rss("rss-wins")
        return b"<!doctype html><title>not rss</title>"

    def forbidden_page(show, **_kwargs):
        calls.append(show["slug"])
        raise AssertionError("page fallback must not run")

    monkeypatch.setattr(ap, "fetch_rss", fetch_rss)
    monkeypatch.setattr(ap, "fetch_xiaoyuzhou_public_page", forbidden_page)
    export = ap.ingest(config_path=config, output_path=tmp_path / "out.json", cache_dir=tmp_path / "cache", now=NOW)
    records = {show["slug"]: show for show in export["shows"]}
    assert records["fallback"]["fetch_status"] == "fresh"
    assert records["fallback"]["episodes"][0]["episode_id"] == "rss-wins"
    assert records["fallback"]["limited_public_page_fallback"] is False
    assert records["ordinary"]["fetch_status"] == "unavailable"
    assert calls == []


def test_page_failure_keeps_cached_fallback_and_other_show_history(tmp_path, monkeypatch):
    fallback = _show()
    other = _show("other", xiaoyuzhou_page_fallback=None, xiaoyuzhou_podcast_id=None,
                  source_page="https://publisher.example.test/other")
    config = _config(tmp_path / "config.yaml", [fallback, other])
    output = tmp_path / "out.json"
    cache = tmp_path / "cache"

    def initial_rss(url, **_kwargs):
        if "fallback" in url:
            raise ap.RSSFetchError("HTML response")
        return _rss("other-old")

    monkeypatch.setattr(ap, "fetch_rss", initial_rss)
    monkeypatch.setattr(ap, "fetch_xiaoyuzhou_public_page", lambda *_args, **_kwargs: _page([_entry("page-new")]))
    first = ap.ingest(config_path=config, output_path=output, cache_dir=cache, now=NOW)
    assert {show["slug"] for show in first["shows"]} == {"fallback", "other"}
    assert next(show for show in first["shows"] if show["slug"] == "fallback")["episode_count"] == 1

    monkeypatch.setattr(ap, "fetch_rss", lambda *_args, **_kwargs: (_ for _ in ()).throw(ap.RSSFetchError("still HTML")))
    monkeypatch.setattr(ap, "fetch_xiaoyuzhou_public_page", lambda *_args, **_kwargs: (_ for _ in ()).throw(ap.RSSFetchError("page down")))
    merged = ap.ingest(config_path=config, output_path=output, cache_dir=cache, now=NOW, only_show="fallback")
    records = {show["slug"]: show for show in merged["shows"]}
    assert records["fallback"]["fetch_status"] == "cache_fallback"
    assert records["fallback"]["episodes"][0]["episode_id"] == "page-new"
    assert records["fallback"]["limited_public_page_fallback"] is True
    assert records["other"]["episodes"][0]["episode_id"] == "other-old"


def test_page_fallback_merges_existing_history_without_using_official_total(tmp_path, monkeypatch):
    config = _config(tmp_path / "config.yaml", [_show()])
    output = tmp_path / "out.json"
    previous_episode = ap._xiaoyuzhou_episode(_entry("old-history"), PODCAST_ID)
    output.write_text(json.dumps({"shows": [{
        "slug": "fallback", "episodes": [previous_episode], "episode_count": 1,
        "feed": {}, "parse_stats": {},
    }]}), encoding="utf-8")
    monkeypatch.setattr(ap, "fetch_rss", lambda *_args, **_kwargs: (_ for _ in ()).throw(ap.RSSFetchError("HTML")))
    monkeypatch.setattr(ap, "fetch_xiaoyuzhou_public_page", lambda *_args, **_kwargs: _page([_entry("recent")]))
    export = ap.ingest(config_path=config, output_path=output, cache_dir=tmp_path / "cache", now=NOW, only_show="fallback")
    record = export["shows"][0]
    assert {episode["episode_id"] for episode in record["episodes"]} == {"recent", "old-history"}
    assert record["episode_count"] == 2
    assert record["episode_count"] != 999
    assert record["limited_public_page_fallback"] is True


def test_only_show_merge_does_not_keyerror_when_previous_export_lacks_a_configured_slug(tmp_path, monkeypatch):
    config = _config(tmp_path / "config.yaml", [_show(), _show("other", xiaoyuzhou_page_fallback=None,
                                                               xiaoyuzhou_podcast_id=None,
                                                               source_page="https://publisher.example.test/other")])
    output = tmp_path / "out.json"
    output.write_text(json.dumps({"shows": [{"slug": "other", "episodes": [], "feed": {}, "parse_stats": {}}]}), encoding="utf-8")
    monkeypatch.setattr(ap, "fetch_rss", lambda *_args, **_kwargs: (_ for _ in ()).throw(ap.RSSFetchError("HTML")))
    monkeypatch.setattr(ap, "fetch_xiaoyuzhou_public_page", lambda *_args, **_kwargs: _page([_entry("new")]))
    export = ap.ingest(config_path=config, output_path=output, cache_dir=tmp_path / "cache", now=NOW, only_show="fallback")
    assert {show["slug"] for show in export["shows"]} == {"fallback", "other"}
    assert next(show for show in export["shows"] if show["slug"] == "fallback")["episode_count"] == 1


def test_public_page_config_rejects_unscoped_or_nonofficial_urls(tmp_path):
    invalid = _show(source_page=f"https://www.xiaoyuzhoufm.com/podcast/{PODCAST_ID}?page=2")
    with pytest.raises(ValueError, match="invalid explicit Xiaoyuzhou"):
        ap.load_config(_config(tmp_path / "invalid.yaml", [invalid]))


def test_public_page_without_next_data_is_not_a_successful_import():
    with pytest.raises(ap.PublicPageParseError, match="__NEXT_DATA__"):
        ap.parse_xiaoyuzhou_public_page(b"<html><body>challenge</body></html>", _show())


def test_public_page_rejects_non_image_cdn_or_malformed_cover_objects():
    result = ap.parse_xiaoyuzhou_public_page(
        _page(
            [_entry("cover-invalid", image={"picUrl": f"https://media.xyzcdn.net/{PODCAST_ID}/not-cover.m4a"})],
            image={"picUrl": "http://image.xyzcdn.net/podcast/insecure.jpg"},
        ),
        _show(),
    )
    assert result["feed"]["cover_url"] is None
    assert result["episodes"][0]["cover_url"] is None


def test_public_page_decodes_only_verified_bts_image_wrappers():
    target = "https://image.xyzcdn.net/FsEH5zvWkHggy7eqHP6lC7kjcoe5.jpg"
    bts = "https://bts-image.xyzcdn.net/aHR0cHM6Ly9pbWFnZS54eXpjZG4ubmV0L0ZzRUg1enZXa0hnZ3k3ZXFIUDZsQzdramNvZTUuanBn.jpg"
    result = ap.parse_xiaoyuzhou_public_page(_page([_entry("bts-cover")], image={"picUrl": bts}), _show())
    assert result["feed"]["cover_url"] == target
    assert result["episodes"][0]["cover_url"] == target

    invalid = ap.parse_xiaoyuzhou_public_page(
        _page([_entry("bad-bts")], image={"picUrl": "https://bts-image.xyzcdn.net/not-base64.jpg"}),
        _show(),
    )
    assert invalid["feed"]["cover_url"] is None
    assert invalid["episodes"][0]["cover_url"] is None
