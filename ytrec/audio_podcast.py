"""Official publisher ingestion for official publisher podcast RSS feeds.

The ingest reads feed metadata only, keeps the publisher's HTTPS enclosure
URL unchanged, and never downloads, proxies, transcodes, or stores audio.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_module
import json
import math
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
import yaml


DEFAULT_CONFIG_PATH = Path("config/audio_podcasts.yaml")
DEFAULT_OUTPUT_PATH = Path("site/src/data/audio_podcast.json")
DEFAULT_CACHE_DIR = Path("data/audio_podcast_cache")

SCHEMA_VERSION = 1
CACHE_VERSION = 1
FETCH_TIMEOUT_SECONDS = 45
FETCH_RETRIES = 2
MAX_RESPONSE_BYTES = 14 * 1024 * 1024
USER_AGENT = "fewgood-audio/0.1 (+https://fewgood.io; RSS metadata)"
SELECTION_WINDOW_DAYS = 30
SELECTION_MAX_PER_SHOW = 2
EPISODE_COUNT_LABEL = "当前公开RSS收录"
TRUNCATION_MARKERS = (
    "去小宇宙查看完整单集简介",
    "查看完整单集简介",
    "查看完整简介",
)

try:
    SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:  # pragma: no cover - standard on supported Linux images
    SHANGHAI_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")

_BLOCKED_CONTENT_TAGS = frozenset({
    "script", "style", "iframe", "object", "embed", "template", "svg", "math", "noscript",
})
_ALLOWED_DESCRIPTION_TAGS = frozenset({
    "p", "br", "em", "strong", "a", "ul", "ol", "li", "blockquote",
})
_TEXT_BOUNDARY_TAGS = frozenset({
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main",
    "nav", "ol", "p", "pre", "section", "table", "td", "th", "tr", "ul",
})
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class RSSFetchError(RuntimeError):
    """A bounded RSS request failed or returned an unsafe payload."""


class FeedParseError(RuntimeError):
    """An RSS document is malformed or cannot be parsed safely."""


class _HTMLSanitizer(HTMLParser):
    """Small allowlist sanitizer that also supports a plain-text mode."""

    def __init__(self, *, plain: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.plain = plain
        self._out: list[str] = []
        self._blocked_stack: list[str] = []

    def _boundary(self) -> None:
        if self._out and not self._out[-1].endswith((" ", "\n")):
            self._out.append(" ")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._blocked_stack:
            if tag in _BLOCKED_CONTENT_TAGS:
                self._blocked_stack.append(tag)
            return
        if tag in _BLOCKED_CONTENT_TAGS:
            self._blocked_stack.append(tag)
            return

        if self.plain:
            if tag in _TEXT_BOUNDARY_TAGS:
                self._boundary()
            return

        if tag == "br":
            self._out.append("<br>")
            return
        if tag == "a":
            href = next((value for key, value in attrs if key.lower() == "href"), None)
            safe_href = _safe_url(href, {"http", "https"})
            if safe_href:
                escaped = html_module.escape(safe_href, quote=True)
                self._out.append(f'<a href="{escaped}">')
            return
        if tag in _ALLOWED_DESCRIPTION_TAGS:
            self._out.append(f"<{tag}>")
        elif tag in _TEXT_BOUNDARY_TAGS:
            self._boundary()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "br":
            if self.plain:
                self._boundary()
            else:
                self._out.append("<br>")
            return
        self.handle_starttag(tag, attrs)
        if not self.plain and tag == "a":
            self._out.append("</a>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._blocked_stack:
            if self._blocked_stack[-1] == tag:
                self._blocked_stack.pop()
            return
        if self.plain:
            if tag in _TEXT_BOUNDARY_TAGS:
                self._boundary()
            return
        if tag in _ALLOWED_DESCRIPTION_TAGS and tag != "br":
            self._out.append(f"</{tag}>")
        elif tag == "a":
            self._out.append("</a>")
        elif tag in _TEXT_BOUNDARY_TAGS:
            self._boundary()

    def handle_data(self, data: str) -> None:
        if self._blocked_stack:
            return
        if self.plain:
            self._out.append(data)
        else:
            self._out.append(html_module.escape(data, quote=False))

    def render(self) -> str:
        return "".join(self._out).strip()


def _safe_url(value: Any, schemes: set[str] | frozenset[str]) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or any(ord(char) < 32 or ord(char) == 127 for char in candidate):
        return None
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return None
    if parts.scheme.lower() not in schemes or not parts.netloc:
        return None
    return candidate


def sanitize_html(value: Any) -> str:
    """Return a conservative HTML fragment for untrusted RSS descriptions."""
    if not isinstance(value, str) or not value:
        return ""
    parser = _HTMLSanitizer()
    parser.feed(value)
    parser.close()
    clean = parser.render()
    if not plain_text(clean):
        return ""
    return clean


def plain_text(value: Any) -> str:
    """Strip all markup and collapse whitespace, including blocked-tag content."""
    if not isinstance(value, str) or not value:
        return ""
    parser = _HTMLSanitizer(plain=True)
    parser.feed(value)
    parser.close()
    return re.sub(r"\s+", " ", parser.render()).strip()


def parse_duration(value: Any) -> int | None:
    """Parse itunes:duration as HH:MM:SS, MM:SS, or seconds."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if ":" in raw:
            parts = raw.split(":")
            if len(parts) not in (2, 3):
                return None
            numbers = [float(part) for part in parts]
            if any(number < 0 or not math.isfinite(number) for number in numbers):
                return None
            total = numbers[-1]
            total += numbers[-2] * 60
            if len(numbers) == 3:
                total += numbers[0] * 3600
        else:
            total = float(raw)
    except (TypeError, ValueError):
        return None
    if total < 0 or not math.isfinite(total):
        return None
    return int(total)


def format_duration(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    minutes, remainder = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{remainder:02d}"
    return f"{minutes}:{remainder:02d}"


def parse_pub_date(raw: Any) -> tuple[datetime | None, bool]:
    """Return a timezone-aware datetime and whether the source had no meaningful time."""
    if not isinstance(raw, str) or not raw.strip():
        return None, False
    value = raw.strip()
    date_only = bool(_DATE_ONLY_RE.fullmatch(value))
    try:
        if date_only:
            parsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        else:
            parsed = parsedate_to_datetime(value)
            if parsed is None:
                raise ValueError("unrecognised date")
    except (TypeError, ValueError, OverflowError):
        try:
            iso_value = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
            parsed = datetime.fromisoformat(iso_value)
        except (TypeError, ValueError, OverflowError):
            return None, False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc if parsed.utcoffset() == timedelta(0) else parsed.tzinfo)
    if not date_only and parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0 \
            and parsed.microsecond == 0 and parsed.utcoffset() == timedelta(0):
        date_only = True
    return parsed, date_only


def _published_fields(raw: Any) -> dict[str, Any]:
    value = raw.strip() if isinstance(raw, str) else ""
    parsed, date_only = parse_pub_date(value)
    if parsed is None:
        return {
            "pub_date_raw": value or None,
            "published_at": None,
            "published_at_utc": None,
            "published_at_asia_shanghai": None,
            "published_display": None,
            "published_date_only": False,
        }
    shanghai = parsed.astimezone(SHANGHAI_TZ)
    return {
        "pub_date_raw": value,
        "published_at": parsed.isoformat(),
        "published_at_utc": parsed.astimezone(timezone.utc).isoformat(),
        "published_at_asia_shanghai": (
            shanghai.date().isoformat() if date_only
            else shanghai.isoformat(timespec="seconds")
        ),
        "published_display": (
            shanghai.date().isoformat() if date_only
            else shanghai.strftime("%Y-%m-%d %H:%M")
        ),
        "published_date_only": date_only,
    }


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _find_direct(element: ET.Element, *names: str) -> ET.Element | None:
    wanted = {name.lower() for name in names}
    for child in element:
        if _local_name(child.tag) in wanted:
            return child
    return None


def _element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _element_content(element: ET.Element | None) -> str:
    """Return text or inner markup without losing child tags for sanitization."""
    if element is None:
        return ""
    if len(element) == 0:
        return (element.text or "").strip()
    return ET.tostring(element, encoding="unicode").strip()


def _first_text(element: ET.Element, *names: str) -> str:
    for name in names:
        value = _element_text(_find_direct(element, name))
        if value:
            return value
    return ""


def _first_content(element: ET.Element, *names: str) -> str:
    for name in names:
        value = _element_content(_find_direct(element, name))
        if value:
            return value
    return ""


def _is_truncated(raw: str, text: str) -> bool:
    if any(marker in raw or marker in text for marker in TRUNCATION_MARKERS):
        return True
    if not text:
        return False
    tail = text.rstrip()
    return bool(re.search(r"(?:\.{3,}|…+|⋯+)\s*$", tail))


def _episode_datetime(episode: dict[str, Any]) -> datetime | None:
    value = episode.get("published_at_utc")
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def sort_episodes(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Newest first, with a stable GUID/URL tie-break."""
    tied = sorted(
        episodes,
        key=lambda episode: (
            str(episode.get("episode_id") or ""),
            str(episode.get("audio_url") or ""),
        ),
    )
    minimum = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(tied, key=lambda episode: _episode_datetime(episode) or minimum, reverse=True)


def dedupe_episodes(episodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    duplicate_count = 0
    for episode in episodes:
        key = str(episode.pop("_dedup_key", ""))
        if key and key in seen:
            duplicate_count += 1
            continue
        if key:
            seen.add(key)
        unique.append(episode)
    return unique, duplicate_count


def _parse_episode(item: ET.Element) -> dict[str, Any] | None:
    enclosure = _find_direct(item, "enclosure")
    enclosure_url = enclosure.get("url") if enclosure is not None else None
    audio_url = _safe_url(enclosure_url, {"https"})
    if not audio_url:
        return None

    title_raw = _first_content(item, "title")
    title = plain_text(title_raw)
    description_raw = _first_content(item, "encoded", "description", "summary")
    description_html = sanitize_html(description_raw)
    description_text = plain_text(description_html)
    description_missing = not bool(description_text)

    guid = _first_text(item, "guid", "id")
    pub_date_raw = _first_text(item, "pubDate", "published", "updated", "date")
    author = _first_text(item, "author", "creator")
    link = _safe_url(_first_text(item, "link"), {"http", "https"})
    duration_seconds = parse_duration(_first_text(item, "duration"))

    fallback_basis = "\x1f".join((audio_url, pub_date_raw, title))
    fallback_hash = hashlib.sha256(fallback_basis.encode("utf-8")).hexdigest()
    dedup_key_kind = "guid" if guid else "fallback"
    dedup_key = f"guid:{guid}" if guid else f"fallback:{fallback_hash}"
    episode_id = guid or f"fallback-{fallback_hash[:24]}"
    length_raw = enclosure.get("length") if enclosure is not None else None
    length_bytes = int(length_raw) if isinstance(length_raw, str) and length_raw.isdigit() else None

    episode: dict[str, Any] = {
        "episode_id": episode_id,
        "guid": guid or None,
        "dedup_key_kind": dedup_key_kind,
        "title": title,
        "description_html": description_html,
        "description_text": description_text,
        "description_missing": description_missing,
        "description_truncated": _is_truncated(description_raw, description_text),
        "description_source": (
            "content:encoded" if _first_content(item, "encoded")
            else "description" if _first_content(item, "description")
            else "itunes:summary" if _first_content(item, "summary")
            else None
        ),
        "episode_link": link,
        "audio_url": audio_url,
        "audio_type": enclosure.get("type") if enclosure is not None else None,
        "audio_length_bytes": length_bytes,
        "duration_seconds": duration_seconds,
        "duration_display": format_duration(duration_seconds),
        "author": author or None,
    }
    episode.update(_published_fields(pub_date_raw))
    episode["_dedup_key"] = dedup_key
    return episode


def parse_feed(xml_bytes: bytes, show: dict[str, Any] | None = None) -> dict[str, Any]:
    """Safely parse RSS metadata without resolving DTDs or external entities."""
    if not isinstance(xml_bytes, (bytes, bytearray)):
        raise FeedParseError("feed payload must be bytes")
    payload = bytes(xml_bytes)
    if not payload:
        raise FeedParseError("empty RSS response")
    if len(payload) > MAX_RESPONSE_BYTES:
        raise FeedParseError("RSS response exceeds the size limit")

    scan = payload.replace(b"\x00", b"").lower()
    if b"<!doctype" in scan or b"<!entity" in scan:
        raise FeedParseError("DTD or entity declarations are not allowed")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise FeedParseError(f"malformed XML: {error}") from error

    channel = next((element for element in root.iter() if _local_name(element.tag) == "channel"), None)
    if channel is None:
        raise FeedParseError("RSS channel not found")

    feed_description_raw = _first_content(channel, "description", "subtitle")
    feed_description_html = sanitize_html(feed_description_raw)
    feed = {
        "title": plain_text(_first_content(channel, "title")) or None,
        "link": _safe_url(_first_text(channel, "link"), {"http", "https"}),
        "description_html": feed_description_html,
        "description_text": plain_text(feed_description_html),
        "copyright": plain_text(_first_content(channel, "copyright")) or None,
        "author": plain_text(_first_text(channel, "author", "creator", "managingEditor")) or None,
        "managing_editor": plain_text(_first_text(channel, "managingEditor")) or None,
        "language": plain_text(_first_text(channel, "language")) or None,
        "last_build_date_raw": _first_text(channel, "lastBuildDate", "updated") or None,
    }

    items = [element for element in root.iter() if _local_name(element.tag) in {"item", "entry"}]
    parsed_episodes: list[dict[str, Any]] = []
    invalid_media_count = 0
    for item in items:
        episode = _parse_episode(item)
        if episode is None:
            invalid_media_count += 1
            continue
        parsed_episodes.append(episode)

    unique_episodes, duplicate_count = dedupe_episodes(parsed_episodes)
    episodes = sort_episodes(unique_episodes)
    return {
        "feed": feed,
        "episodes": episodes,
        "stats": {
            "item_count": len(items),
            "episode_count": len(episodes),
            "duplicate_count": duplicate_count,
            "invalid_media_count": invalid_media_count,
        },
    }


def _empty_result() -> dict[str, Any]:
    return {
        "feed": {
            "title": None,
            "link": None,
            "description_html": "",
            "description_text": "",
            "copyright": None,
            "author": None,
            "managing_editor": None,
            "language": None,
            "last_build_date_raw": None,
        },
        "episodes": [],
        "stats": {
            "item_count": 0,
            "episode_count": 0,
            "duplicate_count": 0,
            "invalid_media_count": 0,
        },
    }


def fetch_rss(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = FETCH_TIMEOUT_SECONDS,
    max_bytes: int = MAX_RESPONSE_BYTES,
    retries: int = FETCH_RETRIES,
    sleep_fn=time.sleep,
) -> bytes:
    """Fetch one RSS document with bounded retries, redirects, and payload size."""
    if not _safe_url(url, {"http", "https"}):
        raise RSSFetchError("RSS URL must be HTTP(S)")
    client = session or requests.Session()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8",
    }
    last_error = "unknown fetch error"
    for attempt in range(retries + 1):
        try:
            response = client.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
        except requests.RequestException as error:
            last_error = f"{type(error).__name__}: {error}"
            if attempt < retries:
                sleep_fn(0.5 * (attempt + 1))
                continue
            raise RSSFetchError(last_error) from error

        status = int(getattr(response, "status_code", 200))
        if status >= 400:
            last_error = f"HTTP {status}"
            if status in _RETRYABLE_STATUSES and attempt < retries:
                sleep_fn(0.5 * (attempt + 1))
                continue
            raise RSSFetchError(last_error)

        content_type = str(getattr(response, "headers", {}).get("Content-Type", "")).lower()
        if content_type.startswith(("audio/", "video/", "image/")):
            raise RSSFetchError(f"redirected to non-XML content: {content_type}")
        content_length = getattr(response, "headers", {}).get("Content-Length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    raise RSSFetchError("RSS response exceeds the size limit")
            except ValueError:
                pass

        chunks: list[bytes] = []
        total = 0
        iterator = response.iter_content(chunk_size=65536) if hasattr(response, "iter_content") \
            else [getattr(response, "content", b"")]
        try:
            for chunk in iterator:
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise RSSFetchError("RSS response exceeds the size limit")
                chunks.append(chunk)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
        payload = b"".join(chunks)
        if not payload:
            raise RSSFetchError("empty RSS response")
        return payload
    raise RSSFetchError(last_error)


def _coerce_now(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = value.strip()
        if not raw:
            raise ValueError("--now cannot be empty")
        try:
            parsed = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw)
        except ValueError as error:
            raise ValueError(f"invalid --now value: {value}") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config_path = Path(path)
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"cannot read podcast config: {config_path}") from error
    if not isinstance(payload, dict):
        raise ValueError("podcast config must be a mapping")
    shows = payload.get("shows")
    planned_shows = payload.get("planned_shows")
    if not isinstance(shows, list) or not isinstance(planned_shows, list):
        raise ValueError("podcast config needs `shows` and `planned_shows` lists")

    seen_slugs: set[str] = set()
    for show in shows:
        if not isinstance(show, dict):
            raise ValueError("each enabled show must be a mapping")
        for field in ("name", "display_name", "slug", "publisher", "host_kind", "rss_url", "source_page"):
            if not isinstance(show.get(field), str) or not show[field].strip():
                raise ValueError(f"enabled show is missing `{field}`")
        if show.get("status") != "enabled":
            raise ValueError(f"enabled show {show['slug']} must have status=enabled")
        if show["slug"] in seen_slugs:
            raise ValueError(f"duplicate show slug: {show['slug']}")
        seen_slugs.add(show["slug"])
        if not _safe_url(show["rss_url"], {"https"}):
            raise ValueError(f"RSS URL must be HTTPS for {show['slug']}")
        if not _safe_url(show["source_page"], {"http", "https"}):
            raise ValueError(f"invalid source page for {show['slug']}")
        for field in ("optional_spotify", "apple"):
            if show.get(field) is not None and not _safe_url(show[field], {"https"}):
                raise ValueError(f"invalid {field} URL for {show['slug']}")

    for show in planned_shows:
        if not isinstance(show, dict):
            raise ValueError("each planned show must be a mapping")
        for field in ("name", "publisher", "host_kind", "rss_url"):
            if not isinstance(show.get(field), str) or not show[field].strip():
                raise ValueError(f"planned show is missing `{field}`")
        if show.get("status") != "planned":
            raise ValueError(f"planned show {show['name']} must have status=planned")
        if show["name"] in seen_slugs:
            raise ValueError(f"duplicate show identifier: {show['name']}")
        seen_slugs.add(show["name"])
    return payload


def _cache_path(cache_dir: Path, slug: str, suffix: str) -> Path:
    return cache_dir / f"{slug}.{suffix}"


def load_cached_result(cache_dir: str | Path, slug: str) -> dict[str, Any] | None:
    path = _cache_path(Path(cache_dir), slug, "json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("cache_version") != CACHE_VERSION:
        return None
    if payload.get("show_slug") != slug:
        return None
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("feed"), dict) \
            or not isinstance(result.get("episodes"), list):
        return None
    result = dict(result)
    result["episodes"] = sort_episodes(result["episodes"])
    return result


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    _write_bytes_atomic(path, serialized.encode("utf-8"))


def write_cached_result(
    cache_dir: str | Path,
    slug: str,
    raw_xml: bytes,
    result: dict[str, Any],
    *,
    fetched_at: str,
) -> None:
    directory = Path(cache_dir)
    raw_path = _cache_path(directory, slug, "xml")
    parsed_path = _cache_path(directory, slug, "json")
    _write_bytes_atomic(raw_path, raw_xml)
    _write_json_atomic(parsed_path, {
        "cache_version": CACHE_VERSION,
        "show_slug": slug,
        "fetched_at": fetched_at,
        "raw_sha256": hashlib.sha256(raw_xml).hexdigest(),
        "result": result,
    })


def _show_record(
    show_config: dict[str, Any],
    result: dict[str, Any],
    *,
    fetch_status: str,
    fetch_error: str | None = None,
    cache_error: str | None = None,
) -> dict[str, Any]:
    feed = dict(result.get("feed") or _empty_result()["feed"])
    episodes = sort_episodes(list(result.get("episodes") or []))
    record = {
        "slug": show_config["slug"],
        "name": show_config["name"],
        "display_name": show_config["display_name"],
        "publisher": show_config["publisher"],
        "host_kind": show_config["host_kind"],
        "status": "enabled",
        "rss_url": show_config["rss_url"],
        "source_page": show_config["source_page"],
        "optional_spotify": show_config.get("optional_spotify"),
        "apple": show_config.get("apple"),
        "fetch_status": fetch_status,
        "cache_used": fetch_status in {"cache_fallback", "cache_only"},
        "episode_count": len(episodes),
        "episode_count_label": EPISODE_COUNT_LABEL,
        "parse_stats": dict(result.get("stats") or {}),
        "feed": feed,
        "episodes": episodes,
    }
    if fetch_error:
        record["fetch_error"] = fetch_error
    if cache_error:
        record["cache_error"] = cache_error
    return record


def _process_show(
    show: dict[str, Any],
    *,
    cache_dir: Path,
    no_network: bool,
    dry_run: bool,
    session: requests.Session | None,
    sleep_fn,
    fetched_at: str,
) -> dict[str, Any]:
    cached = load_cached_result(cache_dir, show["slug"])
    if no_network:
        if cached is None:
            return _show_record(
                show,
                _empty_result(),
                fetch_status="unavailable",
                fetch_error="无网络模式且没有可用缓存",
            )
        return _show_record(show, cached, fetch_status="cache_only")

    try:
        raw = fetch_rss(show["rss_url"], session=session, sleep_fn=sleep_fn)
        assert isinstance(raw, bytes)
        result = parse_feed(raw, show)
    except Exception as error:  # one bad publisher must not stop the whole catalog
        message = f"{type(error).__name__}: {error}"
        if cached is not None:
            return _show_record(
                show,
                cached,
                fetch_status="cache_fallback",
                fetch_error=message,
            )
        return _show_record(
            show,
            _empty_result(),
            fetch_status="unavailable",
            fetch_error=message,
        )

    cache_error = None
    if not dry_run:
        try:
            write_cached_result(cache_dir, show["slug"], raw, result, fetched_at=fetched_at)
        except OSError as error:
            cache_error = f"{type(error).__name__}: {error}"
    return _show_record(
        show,
        result,
        fetch_status="fresh",
        cache_error=cache_error,
    )


def select_recent(
    shows: list[dict[str, Any]],
    now: str | datetime | None = None,
    *,
    window_days: int = SELECTION_WINDOW_DAYS,
    max_per_show: int = SELECTION_MAX_PER_SHOW,
) -> dict[str, Any]:
    """Select the global recent feed without backfilling stale shows."""
    now_utc = _coerce_now(now)
    window_start = now_utc - timedelta(days=window_days)
    within_window: list[tuple[dict[str, Any], dict[str, Any], datetime]] = []
    for show in shows:
        for episode in show.get("episodes", []):
            published = _episode_datetime(episode)
            if published is not None and window_start <= published <= now_utc:
                within_window.append((show, episode, published))

    candidates_by_show: dict[str, list[tuple[dict[str, Any], dict[str, Any], datetime]]] = {}
    for candidate in within_window:
        candidates_by_show.setdefault(candidate[0]["slug"], []).append(candidate)
    selected: list[tuple[dict[str, Any], dict[str, Any], datetime]] = []
    for candidates in candidates_by_show.values():
        candidates.sort(
            key=lambda candidate: (
                str(candidate[1].get("episode_id") or ""),
                str(candidate[1].get("audio_url") or ""),
            ),
        )
        candidates.sort(key=lambda candidate: candidate[2], reverse=True)
        selected.extend(candidates[:max_per_show])
    selected.sort(
        key=lambda candidate: (
            str(candidate[1].get("episode_id") or ""),
            str(candidate[1].get("audio_url") or ""),
        ),
    )
    selected.sort(key=lambda candidate: candidate[2], reverse=True)

    reason = f"近{window_days}天内更新 · 该节目最多收录{max_per_show}条"
    items = [
        {
            "show_slug": show["slug"],
            "show_name": show["display_name"],
            "publisher": show["publisher"],
            "host_kind": show["host_kind"],
            "reason": reason,
            "episode": episode,
        }
        for show, episode, _published in selected
    ]
    return {
        "title": "近期精选",
        "selection_rules": (
            f"仅收录发布时间位于最近{window_days}天内（含边界）的单集；"
            f"每个节目最多收录{max_per_show}条；按发布时间从新到旧排列；"
            "不会用更旧单集回填更新较慢的节目。"
        ),
        "window_days": window_days,
        "window_start": _format_utc(window_start),
        "window_end": _format_utc(now_utc),
        "window_start_asia_shanghai": window_start.astimezone(SHANGHAI_TZ).isoformat(timespec="seconds"),
        "window_end_asia_shanghai": now_utc.astimezone(SHANGHAI_TZ).isoformat(timespec="seconds"),
        "max_episodes_per_show": max_per_show,
        "candidate_count": len(within_window),
        "selected_count": len(items),
        "items": items,
    }


def _planned_record(show: dict[str, Any]) -> dict[str, Any]:
    record = {
        "name": show["name"],
        "publisher": show["publisher"],
        "host_kind": show["host_kind"],
        "rss_url": show["rss_url"],
        "status": "planned",
    }
    if show.get("note"):
        record["note"] = show["note"]
    return record


def build_export(
    config: dict[str, Any],
    shows: list[dict[str, Any]],
    now: str | datetime | None = None,
) -> dict[str, Any]:
    now_utc = _coerce_now(now)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _format_utc(now_utc),
        "generated_at_asia_shanghai": now_utc.astimezone(SHANGHAI_TZ).isoformat(timespec="seconds"),
        "preview_policy": (
            "仅读取并展示官方发布者 RSS 中的元数据与 HTTPS 音频地址；"
            "不转存、不代理、不转码音频，也不提供下载。"
        ),
        "episode_count_label": EPISODE_COUNT_LABEL,
        "show_count": len(shows),
        "recent_selection": select_recent(shows, now_utc),
        "shows": shows,
        "planned_shows": [_planned_record(show) for show in config["planned_shows"]],
    }


def ingest(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    now: str | datetime | None = None,
    no_network: bool = False,
    dry_run: bool = False,
    only_show: str | None = None,
    session: requests.Session | None = None,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    """Ingest enabled shows, select recent items, and write the JSON export."""
    config = load_config(config_path)
    now_utc = _coerce_now(now)
    fetched_at = _format_utc(now_utc)
    selected_configs = list(config["shows"])
    if only_show:
        selected_configs = [show for show in selected_configs if show["slug"] == only_show]
        if not selected_configs:
            raise ValueError(f"unknown enabled show slug: {only_show}")

    cache_path = Path(cache_dir)
    records = [
        _process_show(
            show,
            cache_dir=cache_path,
            no_network=no_network,
            dry_run=dry_run,
            session=session,
            sleep_fn=sleep_fn,
            fetched_at=fetched_at,
        )
        for show in selected_configs
    ]
    # Fresh CI checkouts have the committed export but may have no local cache.
    try:
        previous = json.loads(Path(output_path).read_text(encoding="utf8"))
        previous_shows = {show["slug"]: show for show in previous["shows"]}
    except (OSError, ValueError, KeyError, TypeError):
        previous_shows = {}
    for record in records:
        old = previous_shows.get(record["slug"])
        if record["fetch_status"] == "unavailable" and old and old.get("episodes"):
            record.update({key: old[key] for key in ("episodes", "episode_count", "feed", "parse_stats") if key in old})
            record["fetch_status"] = "snapshot_fallback"
    export = build_export(config, records, now_utc)
    if not dry_run:
        _write_json_atomic(Path(output_path), export)
    return export


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Official publisher ingestion for official publisher audio podcast RSS feeds.",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--show", help="only process one enabled show slug")
    parser.add_argument("--now", help="UTC ISO timestamp used for deterministic selection/tests")
    parser.add_argument("--no-network", action="store_true", help="read only the parsed cache")
    parser.add_argument("--dry-run", action="store_true", help="fetch and select without writing files")
    args = parser.parse_args(argv)
    try:
        export = ingest(
            config_path=args.config,
            output_path=args.output,
            cache_dir=args.cache_dir,
            now=args.now,
            no_network=args.no_network,
            dry_run=args.dry_run,
            only_show=args.show,
        )
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"audio podcast ingestion failed: {error}\n")
    summary = {
        "dry_run": args.dry_run,
        "output": None if args.dry_run else args.output,
        "generated_at": export["generated_at"],
        "shows": export["show_count"],
        "selected": export["recent_selection"]["selected_count"],
        "cache_only": args.no_network,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
