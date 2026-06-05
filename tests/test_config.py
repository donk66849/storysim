from engine.config import load_config, StoryConfig
from engine.character import Character


YAML_TEXT = """\
title: 雨夜古宅
scene: 三个陌生人被暴雨困在断电的古宅里,大门反锁。
max_rounds: 12
characters:
  - name: 林探长
    persona: 退休侦探,多疑
    goal: 查清真相
    voice: 冷静爱反问
  - name: 苏小姐
    persona: 神秘访客
    goal: 隐藏秘密
    voice: 温柔含糊
"""


def test_load_config_parses_top_level_fields(tmp_path):
    p = tmp_path / "story.yaml"
    p.write_text(YAML_TEXT, encoding="utf-8")
    cfg = load_config(p)
    assert isinstance(cfg, StoryConfig)
    assert cfg.title == "雨夜古宅"
    assert cfg.scene.startswith("三个陌生人")
    assert cfg.max_rounds == 12


def test_load_config_builds_characters(tmp_path):
    p = tmp_path / "story.yaml"
    p.write_text(YAML_TEXT, encoding="utf-8")
    cfg = load_config(p)
    assert len(cfg.characters) == 2
    first = cfg.characters[0]
    assert isinstance(first, Character)
    assert first.name == "林探长"
    assert first.goal == "查清真相"
    assert first.private_notes == []


def test_load_config_defaults_max_rounds_when_missing(tmp_path):
    p = tmp_path / "story.yaml"
    p.write_text(
        "title: t\nscene: s\ncharacters:\n  - name: A\n    persona: p\n"
        "    goal: g\n    voice: v\n",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.max_rounds == 20
