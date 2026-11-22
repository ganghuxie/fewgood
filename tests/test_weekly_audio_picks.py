import json
from pathlib import Path

from ytrec import weekly_audio_picks as weekly


ROOT = Path(__file__).resolve().parents[1]


def test_weekly_audio_picks_records_a_skip_without_fabricating_items(tmp_path):
    output = tmp_path / "audio_weekly_picks.json"
    exit_code = weekly.main([
        "--config", str(ROOT / "config/audio_podcasts.yaml"),
        "--output", str(output),
        "--now", "2026-11-22T00:00:00Z",
    ])
    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf8"))
    assert payload["status"] == "skipped"
    assert payload["items"] == []
    assert "单集热度" in payload["reason"]
    assert "不能" in payload["reason"]
    assert any(token in payload["reason"] for token in ("伪造", "冒充"))
    assert payload["selection_rules"] == {
        "minimum_distinct_shows_per_category": 4,
        "minimum_episodes_per_show": 1,
        "exclude_daily_update": True,
    }
    assert payload["categories"] == ["认知", "商业", "心理", "人文", "搞笑", "生活"]


def test_weekly_audio_command_is_independent_from_daily_recent_selection():
    source = (ROOT / "ytrec" / "weekly_audio_picks.py").read_text(encoding="utf8")
    cli = (ROOT / "ytrec" / "__main__.py").read_text(encoding="utf8")
    workflow = (ROOT / ".github" / "workflows" / "weekly-audio-picks.yml").read_text(encoding="utf8")
    assert "recent_selection" not in source
    assert "weekly-audio-picks" in cli
    assert "0 21 * * 5" in workflow
    assert "group: weekly-audio-picks" in workflow
    assert "deploy-pages" not in workflow
