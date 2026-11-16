#!/usr/bin/env python3
"""Package the isolated audio-podcast TEST preview for GitHub Pages.

Remaps production audio-podcast HTML to audio-podcast-preview, with required CSS/public assets from an
Astro isolated dist. Strips official-site Header/Sidebar/Layout/AuthMenu module
scripts so library/analytics/auth never load. Keeps inline player scripts and
CSS. Adds noindex, robots Disallow, stubs for leftover official-nav hrefs, and
never writes CNAME, env files, or audio.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin

BASE = "/fewgood-audio-podcast-preview"
KEEP_PUBLIC = [
    "favicon.svg", "favicon.ico", "favicon-16.png", "favicon-32.png",
    "apple-touch-icon-180.png", "logo-mark.svg", "og-image-1200x630.png",
    "icon-192.png", "icon-512.png", "maskable-512.png", "site.webmanifest",
]
STUB_ROUTES = [
    "history/", "favorites/", "watch-later/", "following/",
    "trending/", "ai/", "podcast/", "music/", "community/",
    "community/newest/", "search/", "channel/", "about/",
]
BANNED_JS = (
    "library.DVTIhGWm.js", "analytics.DyV4FvHL.js", "format.Ds2wr4QH.js",
    "AuthMenu.", "Header.astro_astro_type_script", "Sidebar.astro_astro_type_script",
    "Layout.astro_astro_type_script", "affinity.", "prompts.",
)
NOINDEX = '<meta name="robots" content="noindex,nofollow">'
TEST_STYLE = '<style id="isolated-test-overrides">[data-auth-root],.sidebar,.sidebar-backdrop{display:none!important}</style>'
SCRIPT_SRC_RE = re.compile(
    r'<script type="module" src="' + re.escape(BASE) + r'/_astro/[^"]+"></script>\s*',
    re.I,
)
HREF_RE = re.compile(r"""(?:href|src)=["']([^"']+)["']""")
CSS_URL_RE = re.compile(r"""url\((?:'|"|)([^'"]+)(?:'|"|)\)""")
IMPORT_RE = re.compile(
    r"""(?:import\s*\(\s*["']([^"']+)["']\s*\)|(?:import|export)\s+(?:[^'"\n]+from\s+)?["']([^"']+)["'])"""
)
EXTERNAL = ("data:", "http:", "https:", "mailto:", "javascript:", "#")
MEDIA_EXT = {".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac", ".mp4"}


def rewrite_html(html: str) -> str:
    if 'name="robots"' not in html:
        html = html.replace("<meta charset=\"utf-8\">", "<meta charset=\"utf-8\">\n" + NOINDEX, 1)
        if 'name="robots"' not in html:
            html = html.replace("<head>", "<head>" + NOINDEX, 1)
    if "isolated-test-overrides" not in html:
        html = html.replace("</head>", TEST_STYLE + "</head>", 1)
    html = SCRIPT_SRC_RE.sub("", html)
    html = re.sub(r'<script[^>]*src=["\'][^"\']+["\'][^>]*>.*?</script>', '', html, flags=re.S | re.I)
    html = html.replace(BASE + '/audio-podcast/', BASE + '/audio-podcast-preview/')
    html = html.replace('https://fewgood.io' + BASE, 'https://ganghuxie.github.io' + BASE)
    return html


def not_here() -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<meta name="viewport" content="width=device-width">
<title>本测试站不含该页面</title>
</head>
<body>
<p>这是独立的音频播客测试预览站，不含 fewgood 正式站的其他栏目，也不会跳转到正式站自动打开那些页面。</p>
<p><a href="{BASE}/audio-podcast-preview/">返回音频播客测试预览</a></p>
</body>
</html>
"""


def write_stub(art: Path, route: str) -> None:
    dest = art / route / "index.html" if route.endswith("/") else art / route
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(not_here(), encoding="utf-8")


def as_index(rel: str) -> str:
    rel = unquote(rel.split("?")[0]).split("#")[0]
    if rel.endswith("/"):
        return rel + "index.html"
    if rel in {"", "."}:
        return "index.html"
    return rel


def package(src: Path, art: Path, source_commit: str) -> dict:
    if art.exists():
        shutil.rmtree(art)
    art.mkdir(parents=True)

    html_src = list((src / "audio-podcast").rglob("*.html"))
    if not html_src:
        raise SystemExit(f"missing isolated html under {src}")
    for path in html_src:
        dest = art / "audio-podcast-preview" / path.relative_to(src / "audio-podcast")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rewrite_html(path.read_text(encoding="utf-8")), encoding="utf-8")

    for name in KEEP_PUBLIC:
        src_file = src / name
        if src_file.is_file():
            shutil.copy2(src_file, art / name)

    needed = set()
    for path in (art / "audio-podcast-preview").rglob("*.html"):
        for raw in HREF_RE.findall(path.read_text(encoding="utf-8")):
            if raw.startswith(BASE + "/"):
                needed.add(raw[len(BASE) + 1:].split("#")[0].split("?")[0])
            elif raw.startswith("/_astro/"):
                raise SystemExit(f"bare /_astro ref in {path}: {raw}")

    def copy_file(rel: str) -> Path:
        rel = rel.split("?")[0].split("#")[0].lstrip("/")
        dest = art / rel
        if dest.exists():
            return dest
        src_file = src / rel
        if not src_file.is_file():
            raise SystemExit(f"missing static asset: {rel}")
        if any(token in rel for token in BANNED_JS):
            raise SystemExit(f"refused telemetry/shell bundle: {rel}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)
        return dest

    for rel in needed:
        if not rel or rel.endswith("/"):
            continue
        if any(rel.endswith(ext) for ext in (".css", ".js", ".svg", ".png", ".ico", ".webmanifest", ".jpg", ".webp")):
            copy_file(rel)

    seen_css: set[str] = set()

    def walk_css(path: Path) -> None:
        rel = str(path.relative_to(art))
        if rel in seen_css:
            return
        seen_css.add(rel)
        if path.suffix != ".css":
            return
        text = path.read_text(encoding="utf-8", errors="replace")
        for ref in CSS_URL_RE.findall(text):
            if not ref or ref.startswith(("data:", "http:", "https:", "#")):
                continue
            if ref.startswith("/_astro/"):
                raise SystemExit(f"bare /_astro in {rel}: {ref}")
            if ref.startswith(BASE + "/"):
                dest_rel = ref[len(BASE) + 1:]
            elif ref.startswith("/"):
                raise SystemExit(f"root-absolute in {rel}: {ref}")
            else:
                dest_rel = urljoin(rel, ref).split("?")[0]
            walk_css(copy_file(dest_rel))

    for path in list(art.rglob("*.css")):
        walk_css(path)

    for route in STUB_ROUTES:
        write_stub(art, route)
    (art / "404.html").write_text(not_here(), encoding="utf-8")
    (art / "index.html").write_text(
        f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<meta name="viewport" content="width=device-width">
<title>音频播客测试预览 · 独立测试站（非正式 fewgood 站）</title>
<link rel="canonical" href="https://ganghuxie.github.io{BASE}/audio-podcast-preview/">
<meta http-equiv="refresh" content="0; url={BASE}/audio-podcast-preview/">
</head>
<body>
<p>这是独立测试站，不是 fewgood.io 正式站。</p>
<p><a href="{BASE}/audio-podcast-preview/">进入音频播客测试预览</a></p>
</body>
</html>
""",
        encoding="utf-8",
    )
    (art / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (art / ".nojekyll").write_text("", encoding="utf-8")
    (art / "README.md").write_text(
        f"""# fewgood audio podcast — independent TEST preview

This repository hosts a **shareable independent test site** for the
fewgood audio-podcast preview. It is **not** the official fewgood.io site.

- Official site: https://fewgood.io/ (unchanged)
- Test preview path: `/audio-podcast-preview/`
- Source commit in ganghuxie/fewgood branch `audio-podcast-design-preview`: `{source_commit}`
- Official publisher RSS metadata only. Audio is streamed from official enclosure URLs in the browser; no audio files are hosted here.
- `noindex,nofollow` on all pages. No production CNAME.
- Isolated preview does not load official-site library, analytics, or auth scripts.

Do not treat this as a production launch.
""",
        encoding="utf-8",
    )
    return audit(art)


def audit(art: Path) -> dict:
    errors: list[str] = []
    missing: list[str] = []

    def resolve_from(file_rel: str, spec: str) -> str | None:
        spec = spec.strip()
        if not spec or spec.startswith(EXTERNAL) or spec.startswith("#"):
            return None
        if spec.startswith("//"):
            return None
        if spec.startswith("/_astro/"):
            errors.append(f"bare /_astro in {file_rel}: {spec}")
            return spec.lstrip("/")
        if spec.startswith(BASE + "/"):
            return as_index(spec[len(BASE) + 1:])
        if spec.startswith("/"):
            errors.append(f"root-absolute path in {file_rel}: {spec}")
            return None
        return as_index(urljoin(file_rel, spec))

    queue = [str(p.relative_to(art)) for p in art.rglob("*.html")]
    seen: set[str] = set()
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        seen.add(rel)
        path = art / rel
        if not path.is_file():
            missing.append(rel)
            continue
        if path.suffix not in {".html", ".js", ".css", ".mjs"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        refs = HREF_RE.findall(text)
        if path.suffix == ".css":
            refs += CSS_URL_RE.findall(text)
        if path.suffix in {".js", ".mjs"}:
            refs += [a or b for a, b in IMPORT_RE.findall(text)]
        else:
            for match in re.finditer(r"<script(?![^>]*src=)[^>]*>([\s\S]*?)</script>", text):
                refs += [a or b for a, b in IMPORT_RE.findall(match.group(1))]
        for ref in refs:
            dest = resolve_from(rel, ref)
            if dest and dest not in seen:
                queue.append(dest)

    forbidden: list[str] = []
    for path in art.rglob("*"):
        if not path.is_file():
            continue
        if any(token in path.name for token in ("library.DVTIhGWm.js", "analytics.DyV4FvHL.js", "format.Ds2wr4QH.js", "AuthMenu")):
            forbidden.append("file " + str(path.relative_to(art)))
        if path.suffix in {".html", ".js", ".css"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in ("library.DVTIhGWm.js", "analytics.DyV4FvHL.js", "format.Ds2wr4QH.js", "AuthMenu."):
                if token in text:
                    forbidden.append(f"ref {path.relative_to(art)} -> {token}")

    env_hits: dict[str, list[str]] = {}
    env_path = Path(__file__).resolve().parents[1] / "site/.env.production"
    if env_path.is_file():
        env_values = {}
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if value and key != "PUBLIC_AUTH_OAUTH" and len(value) >= 8:
                env_values[key] = value
        for path in art.rglob("*"):
            if not path.is_file() or path.suffix.lower() in {".png", ".ico", ".jpg", ".jpeg", ".webp"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for key, value in env_values.items():
                if value in text:
                    env_hits.setdefault(key, []).append(str(path.relative_to(art)))

    media = [str(p.relative_to(art)) for p in art.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXT]
    idx = (art / "audio-podcast-preview" / "index.html").read_text(encoding="utf-8")
    show = (art / "audio-podcast-preview" / "xie-xing-liao-tian-hui" / "index.html").read_text(encoding="utf-8")
    detail_paths = [p for p in (art / "audio-podcast-preview").glob("*/*/index.html") if p.parent.name != 'page']
    details = [p.read_text(encoding='utf8') for p in detail_paths]
    detail = details[0] if details else ''
    for path in art.rglob('*.html'):
        markup = path.read_text(encoding='utf8')
        if 'noindex,nofollow' not in markup:
            errors.append(f'missing noindex: {path.relative_to(art)}')
        if BASE + '/audio-podcast/' in markup or 'href="/audio-podcast/' in markup:
            errors.append(f'unmapped audio route: {path.relative_to(art)}')
    astro_js = sorted(p.name for p in (art / "_astro").glob("*.js")) if (art / "_astro").exists() else []
    report = {
        "files": sum(1 for p in art.rglob("*") if p.is_file()),
        "bytes": sum(p.stat().st_size for p in art.rglob("*") if p.is_file()),
        "preview_html": sum(1 for p in (art / "audio-podcast-preview").rglob("*.html")),
        "astro_js": astro_js,
        "astro_css": sorted(p.name for p in (art / "_astro").glob("*.css")) if (art / "_astro").exists() else [],
        "has_cname": (art / "CNAME").exists(),
        "media": media,
        "missing": missing,
        "errors": errors,
        "forbidden": forbidden,
        "env_hits": env_hits,
        "index_banner": "测试预览 · 不上线 · 非正式栏目" in idx,
        "index_recent": idx.count("audio-recent-card"),
        "index_shows": idx.count("audio-show-card"),
        "index_planned": idx.count("规划中 / 本次测试未收录"),
        "index_external_js": bool(re.search(r"<script[^>]+src=", idx)),
        "detail_pages": len(details),
        "detail_players": sum(t.count("data-audio-player data-audio-url") for t in details),
        "show_loading_hint": "加载中" in detail,
        "show_inline_player": "setAttribute(" in detail and "src" in detail,
        "show_preload_none": 'preload="none"' in detail,
        "show_audio_src_attr": bool(re.search(r"<audio[^>]*\ssrc=", show)),
        "graph_seen": len(seen),
    }
    failed = (
        missing or errors or forbidden or env_hits or report["has_cname"] or media
        or report["index_banner"] or report["index_external_js"] or astro_js
        or not details or report["detail_players"] != len(details)
        or any(t.count('<audio ') != 1 or 'preload="none"' not in t
               or re.search(r'<audio[^>]*\ssrc=', t) for t in details)
        or "data-audio-player" in show or 'class="chipbar"' not in idx
        or not report["show_inline_player"] or not report["show_loading_hint"]
        or report["index_shows"] != 15 or report["index_planned"] != 0
    )
    report["ok"] = not failed
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default="site/dist")
    parser.add_argument("--dest", default="/tmp/fewgood-audio-preview-repack")
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    report = package(Path(args.src), Path(args.dest), args.source_commit)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
