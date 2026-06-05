from engine.director import parse_command, DirectorCommand, apply_command
from engine.stage import Stage
from engine.character import Character


def test_blank_means_continue():
    assert parse_command("").kind == "continue"
    assert parse_command("   ").kind == "continue"


def test_event_command():
    cmd = parse_command("event: 灯突然全灭了")
    assert cmd.kind == "event"
    assert cmd.value == "灯突然全灭了"


def test_tell_command():
    cmd = parse_command("tell 苏小姐: 你藏着一把钥匙")
    assert cmd.kind == "tell"
    assert cmd.target == "苏小姐"
    assert cmd.value == "你藏着一把钥匙"


def test_set_command():
    cmd = parse_command("set 苏小姐 goal=隐瞒真相")
    assert cmd.kind == "set"
    assert cmd.target == "苏小姐"
    assert cmd.field == "goal"
    assert cmd.value == "隐瞒真相"


def test_save_and_quit():
    assert parse_command("save").kind == "save"
    assert parse_command("quit").kind == "quit"


def test_unknown_command():
    assert parse_command("blah blah").kind == "unknown"


def make_stage_and_chars():
    stage = Stage("场景")
    stage.start_round()
    chars = {
        "苏小姐": Character("苏小姐", "p", "原目标", "v"),
        "林探长": Character("林探长", "p", "g", "v"),
    }
    return stage, chars


def test_apply_event_adds_world_event_and_returns_it():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("event: 灯全灭了")
    status, events = apply_command(cmd, stage, chars)
    assert len(events) == 1
    assert events[0].type == "world_event"
    assert events[0].actor == "世界"
    assert events[0].content == "灯全灭了"
    assert stage.events[-1] is events[0]
    assert "灯全灭了" in status


def test_apply_tell_appends_private_note_only():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("tell 苏小姐: 你有钥匙")
    status, events = apply_command(cmd, stage, chars)
    assert chars["苏小姐"].private_notes == ["你有钥匙"]
    assert events == []  # 私聊不进公共剧情记录
    assert "苏小姐" in status


def test_apply_set_changes_field():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("set 苏小姐 goal=隐瞒真相")
    status, events = apply_command(cmd, stage, chars)
    assert chars["苏小姐"].goal == "隐瞒真相"
    assert events == []
    assert "goal" in status


def test_apply_unknown_character_returns_error():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("tell 张三: 你好")
    status, events = apply_command(cmd, stage, chars)
    assert events == []
    assert "张三" in status
