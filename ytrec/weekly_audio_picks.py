"""Honest weekly audio-pick state.

The public sources currently configured for audio podcasts do not expose a
reliable, documented episode-level popularity metric.  This command therefore
records a deterministic skipped state instead of deriving fake "hot" picks
from publish time, programme rank, or subscription counts.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audio_podcast import DEFAULT_CONFIG_PATH, _coerce_now, _format_utc, load_config


DEFAULT_OUTPUT_PATH = Path("site/src/data/audio_weekly_picks.json")
SCHEMA_VERSION = 1
SKIP_REASON = (
    "暂无可靠的公开单集热度源：官方 RSS 与 iTunes 只提供节目或发布时间信息，"
    "不能用它们生成或冒充热度精选。"
)


def build_weekly_state(config: dict[str, Any], now: str | datetime | None = None) -> dict[str, Any]:
    """Build the independent, deliberately empty weekly-picks artifact."""
    now_utc = _coerce_now(now)
    catalog = config.get("catalog") if isinstance(config.get("catalog"), dict) else {}
    weekly = catalog.get("weekly_picks") if isinstance(catalog.get("weekly_picks"), dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _format_utc(now_utc),
        "status": "skipped",
        "reason": str(weekly.get("reason") or SKIP_REASON),
        "selection_rules": {
            "minimum_distinct_shows_per_category": 4,
            "minimum_episodes_per_show": 1,
            "exclude_daily_update": True,
        },
        "categories": list(catalog.get("categories") or []),
        "items": [],
    }


def write_weekly_state(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write honest weekly audio-pick status without fabricating heat.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--now", help="UTC ISO timestamp for deterministic output")
    args = parser.parse_args(argv)
    try:
        payload = build_weekly_state(load_config(args.config), args.now)
        write_weekly_state(args.output, payload)
    except (OSError, ValueError) as error:
        parser.exit(1, f"weekly audio picks failed: {error}\n")
    print(json.dumps({"output": args.output, "status": payload["status"], "reason": payload["reason"], "selected": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
