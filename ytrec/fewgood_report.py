"""Render read-only Markdown reports for the Fewgood MVP experiment."""
import argparse
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULT = ROOT / "data/experiments/fewgood-mvp-result.json"
DEFAULT_USAGE = ROOT / "data/experiments/fewgood-mvp-usage.json"
DEFAULT_JUDGMENTS = ROOT / "docs/mvp/preliminary-judgments.json"
DEFAULT_OUT = ROOT / "docs/mvp"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def load(path, default):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def cell(value):
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", "<br>")


def table(headers, rows):
    lines = ["| " + " | ".join(cell(x) for x in headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(cell(x) for x in row) + " |" for row in rows)
    return "\n".join(lines)


def local_time(value):
    if not value:
        return "未知"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S") + " 北京时间"
    except ValueError:
        return str(value)


def parse_date(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def date_only(value):
    dt = parse_date(value)
    return dt.astimezone(SHANGHAI).strftime("%Y-%m-%d") if dt else "未知"


def duration(value):
    try:
        seconds = max(0, int(value or 0))
    except (TypeError, ValueError):
        seconds = 0
    return f"{seconds // 60}:{seconds % 60:02d}"


def views(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "未知"


def link_title(video):
    title, url = video.get("title", ""), video.get("url", "")
    return f"[{title}]({url})" if url else title


def source_text(video):
    sources = video.get("sources", [])
    if not sources:
        return "未知"
    return "<br>".join(str(source) for source in sources)


def reasons(video):
    return "<br>".join(str(x) for x in video.get("reasons", [])) or "未知"


def judgment(judgments, video_id):
    item = judgments.get(video_id, {}) if isinstance(judgments, dict) else {}
    verdict = item.get("verdict") if isinstance(item, dict) else None
    note = item.get("note") if isinstance(item, dict) else None
    if not verdict:
        return "待评"
    return verdict + (f"：{note}" if note else "")


def usage_calls(result, usage):
    return usage.get("calls") or result.get("usage_summary", {}).get("calls", []) or []


def usage_rows(result, usage):
    calls = usage_calls(result, usage)
    searches = [x for x in calls if x.get("endpoint") == "search"]
    baseline = sum(str(x.get("purpose", "")).startswith("baseline:") for x in searches)
    topic = sum(str(x.get("purpose", "")).startswith("topic:") for x in searches)
    endpoints = Counter(x.get("endpoint", "未知") for x in calls if x.get("endpoint") != "search")
    statuses = Counter(str(x.get("http_status", "未知")) for x in calls)
    old_units = usage.get("old_model_units")
    if old_units is None:
        old_units = len(searches) * 100 + sum(1 for x in calls if x.get("endpoint") != "search")
    endpoint_text = "<br>".join(f"{k}: {v}" for k, v in sorted(endpoints.items())) or "无"
    status_text = "<br>".join(f"HTTP {k}: {v}" for k, v in sorted(statuses.items())) or "无"
    return [
        ["search.list 次数", len(searches)],
        ["其中 baseline / topic", f"{baseline} / {topic}"],
        ["其他端点单位（按 endpoint）", endpoint_text],
        ["HTTP 状态分布", status_text],
        ["按旧模型 search=100 折算总单位", old_units],
        ["aborted_reason", usage.get("aborted_reason", result.get("usage_summary", {}).get("aborted_reason")) or "无"],
    ]


def quality_report(result, usage, judgments):
    refreshed = result.get("data_refreshed_at") or result.get("generated_at")
    out = ["# Fewgood MVP 质量报告", "", f"数据刷新时间：{local_time(refreshed)}", ""]
    out += ["## pool_stats", "", table(["指标", "值"], [[k, v] for k, v in result.get("pool_stats", {}).items() if k != "duplicate_pairs"]), ""]
    out += ["## timing", "", table(["指标", "秒"], [[k, v] for k, v in result.get("timing", {}).items()]), ""]
    out += ["## usage 汇总", "", table(["项目", "值"], usage_rows(result, usage)), ""]
    for topic in result.get("topics", []):
        stats = topic.get("stats", {})
        name = topic.get("name_zh") or topic.get("id", "未命名主题")
        out += [f"## {name}", "", "### stats", ""]
        stat_rows = []
        for key in ("searches", "baseline_searches", "topic_search_results", "matched", "matched_tier1", "matched_tier2", "matched_tier3", "eligible", "shown", "duplicates_in_topic"):
            stat_rows.append([key, stats.get(key, 0)])
        stat_rows += [["excluded_by_rule", "<br>".join(f"{k}: {v}" for k, v in stats.get("excluded_by_rule", {}).items()) or "无"],
                      ["channel_distribution_eligible 前 10", "<br>".join(f"{k}: {v}" for k, v in sorted(stats.get("channel_distribution_eligible", {}).items(), key=lambda x: (-x[1], x[0]))[:10]) or "无"],
                      ["channel_distribution_shown", "<br>".join(f"{k}: {v}" for k, v in stats.get("channel_distribution_shown", {}).items()) or "无"]]
        out += [table(["指标", "值"], stat_rows), "", "### Top 6", "", table(
            ["#", "标题", "频道", "发布日期", "时长 m:ss", "播放量", "发现来源", "推荐依据", "初步相关性（Grok Bot，待 Jason 复核）"],
            [[i, link_title(video), video.get("channel_title", ""), date_only(video.get("published_at")), duration(video.get("duration_seconds")), views(video.get("view_count")), source_text(video), reasons(video), judgment(judgments, video.get("video_id"))]
             for i, video in enumerate(topic.get("videos", [])[:6], 1)]), ""]
        shown = topic.get("videos", [])[:6]
        counts = Counter((judgments.get(v.get("video_id"), {}).get("verdict") if isinstance(judgments.get(v.get("video_id")), dict) else None) for v in shown)
        denominator = len(shown)
        rate = f"{counts['相关']}/{denominator}" if denominator else "0/0"
        out += [f"初步主题相关率 = {rate}（部分相关单独计数：{counts['部分相关']}）", ""]
    return "\n".join(out).rstrip() + "\n"


def days_old(value, refreshed):
    published, reference = parse_date(value), parse_date(refreshed)
    if not published or not reference:
        return None
    return max(0, (reference - published).days)


def ab_row(video, other_ids, refreshed):
    return [video.get("rank", ""), link_title(video), video.get("channel_title", ""), date_only(video.get("published_at")), duration(video.get("duration_seconds")), views(video.get("view_count")), "是" if video.get("video_id") in other_ids else "否"]


def ab_comparison(result, judgments):
    refreshed = result.get("data_refreshed_at") or result.get("generated_at")
    topics = result.get("topics", [])
    out = ["# Fewgood MVP A/B 对比", "", "C 组（Jason 人工挑选）待补充", "", "## C 组模板", "", table(["#", "标题", "频道", "发布日期", "时长", "播放量", "备注"], [[i, "", "", "", "", "", ""] for i in range(1, 7)]), ""]
    summary = []
    for topic in topics:
        tid = topic.get("id")
        a = result.get("baseline", {}).get(tid, [])[:6]
        b = topic.get("videos", [])[:6]
        a_ids, b_ids = {x.get("video_id") for x in a}, {x.get("video_id") for x in b}
        name = topic.get("name_zh") or tid or "未命名主题"
        out += [f"## {name}", "", "### A 组（YouTube 搜索 API 默认相关度前 6，原样）", "", table(["#", "标题", "频道", "发布日期", "时长", "播放量", "是否也在另一组"], [ab_row(v, b_ids, refreshed) for v in a]), "", "### B 组（fewgood Top 6）", "", table(["#", "标题", "频道", "发布日期", "时长", "播放量", "是否也在另一组"], [ab_row(v, a_ids, refreshed) for v in b]), ""]
        a_days = [days_old(x.get("published_at"), refreshed) for x in a if days_old(x.get("published_at"), refreshed) is not None]
        b_days = [days_old(x.get("published_at"), refreshed) for x in b if days_old(x.get("published_at"), refreshed) is not None]
        def rate(rows):
            verdicts = [judgments.get(x.get("video_id"), {}).get("verdict") for x in rows if isinstance(judgments.get(x.get("video_id")), dict)]
            return f"{sum(x == '相关' for x in verdicts)}/{len(rows)}" if rows else "0/0"
        summary.append([name, statistics.median(a_days) if a_days else "未知", statistics.median(b_days) if b_days else "未知", sum(int(x.get("duration_seconds", 0) or 0) < 240 for x in a), sum(int(x.get("duration_seconds", 0) or 0) < 240 for x in b), len({x.get("channel_title") for x in a}), len({x.get("channel_title") for x in b}), len(a_ids & b_ids), sum((days_old(x.get("published_at"), refreshed) or 0) > 30 for x in a), rate(b), rate(a)])
    out += ["## 汇总", "", "中位发布天数均相对数据刷新时间计算。", "", table(["主题", "A 中位发布天数", "B 中位发布天数", "A <4 分钟", "B <4 分钟", "A 不同频道", "B 不同频道", "两组重叠", "A 超出 30 天", "B 初步相关率", "A 初步相关率"], summary), ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--usage", type=Path, default=DEFAULT_USAGE)
    parser.add_argument("--judgments", type=Path, default=DEFAULT_JUDGMENTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    result, usage = load(args.result, {}), load(args.usage, {})
    judgments = load(args.judgments, {})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "quality-tables.md").write_text(quality_report(result, usage, judgments))
    (args.out_dir / "ab-comparison.md").write_text(ab_comparison(result, judgments))


if __name__ == "__main__":
    main()
