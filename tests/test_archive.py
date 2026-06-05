import json
from datetime import datetime

from engine.archive import Archive
from engine.stage import Stage


def build_stage():
    stage = Stage("暴雨古宅")
    stage.start_round()
    stage.add("narration", "旁白", "雷声轰鸣")
    stage.add("speech", "林探长", "都别动")
    stage.start_round()
    stage.add("speech", "苏小姐", "我害怕")
    return stage


def test_archive_paths_use_timestamp(tmp_path):
    fixed = datetime(2026, 6, 5, 14, 30, 0)
    arc = Archive(tmp_path, "暴雨古宅", now=fixed)
    assert arc.md_path.name == "20260605-143000.md"
    assert arc.jsonl_path.name == "20260605-143000.jsonl"


def test_log_appends_jsonl_lines(tmp_path):
    stage = build_stage()
    arc = Archive(tmp_path, "暴雨古宅", now=datetime(2026, 6, 5, 14, 30, 0))
    for e in stage.events:
        arc.log(e)
    lines = arc.jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    first = json.loads(lines[0])
    assert first == {
        "round": 1,
        "type": "narration",
        "actor": "旁白",
        "content": "雷声轰鸣",
    }


def test_write_markdown_is_readable(tmp_path):
    stage = build_stage()
    arc = Archive(tmp_path, "暴雨古宅", now=datetime(2026, 6, 5, 14, 30, 0))
    arc.write_markdown(stage)
    md = arc.md_path.read_text(encoding="utf-8")
    assert "# 暴雨古宅" in md
    assert "暴雨古宅" in md
    assert "## 第 1 回合" in md
    assert "## 第 2 回合" in md
    assert "林探长:都别动" in md
    assert "〔雷声轰鸣〕" in md
