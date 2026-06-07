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


def test_tell_once_command():
    cmd = parse_command("tell 苏小姐 once: 这回合突然崩溃")
    assert cmd.kind == "tell"
    assert cmd.target == "苏小姐"
    assert cmd.value == "这回合突然崩溃"
    assert cmd.once is True


def test_plain_tell_is_not_once():
    cmd = parse_command("tell 苏小姐: 你藏着一把钥匙")
    assert cmd.once is False


def test_beat_command():
    cmd = parse_command("beat: 远处传来一声惨叫")
    assert cmd.kind == "beat"
    assert cmd.value == "远处传来一声惨叫"


def test_twist_is_alias_for_beat():
    cmd = parse_command("twist: 灯忽明忽暗")
    assert cmd.kind == "beat"
    assert cmd.value == "灯忽明忽暗"


def test_will_command_parsed():
    cmd = parse_command("will: 全员卷入夺嫡")
    assert cmd.kind == "will"
    assert cmd.value == "全员卷入夺嫡"


def test_empty_will_command_parsed():
    cmd = parse_command("will:")
    assert cmd.kind == "will"
    assert cmd.value == ""


def test_mandate_command_parsed():
    cmd = parse_command("mandate 林探长: 当上一品大臣")
    assert cmd.kind == "mandate"
    assert cmd.target == "林探长"
    assert cmd.value == "当上一品大臣"


def test_unmandate_command_parsed():
    cmd = parse_command("unmandate 林探长")
    assert cmd.kind == "unmandate"
    assert cmd.target == "林探长"


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


def test_apply_event_overwrites_scene_as_new_world_state():
    stage, chars = make_stage_and_chars()  # 初始 scene="场景"
    cmd = parse_command("event: 所有人被传送到明朝的京城")
    apply_command(cmd, stage, chars)
    # 世界事件成为新的常驻场景,后续每回合 prompt 都以此为准
    assert stage.scene == "所有人被传送到明朝的京城"


def test_apply_tell_once_appends_oneshot_note():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("tell 苏小姐 once: 突然崩溃")
    status, events = apply_command(cmd, stage, chars)
    assert chars["苏小姐"].oneshot_notes == ["突然崩溃"]
    assert chars["苏小姐"].private_notes == []  # 一次性叮嘱不进长期人设
    assert events == []


def test_apply_will_sets_stage_and_emits_director_event():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("will: 全员卷入夺嫡")
    status, events = apply_command(cmd, stage, chars)
    assert stage.director_will == "全员卷入夺嫡"
    assert len(events) == 1
    assert events[0].type == "director"
    assert "全员卷入夺嫡" in status


def test_apply_empty_will_clears_without_event():
    stage, chars = make_stage_and_chars()
    stage.set_will("旧走向")
    status, events = apply_command(parse_command("will:"), stage, chars)
    assert stage.director_will == ""
    assert events == []


def test_apply_mandate_sets_directive_without_touching_goal():
    stage, chars = make_stage_and_chars()  # 林探长 goal="g"
    status, events = apply_command(
        parse_command("mandate 林探长: 当上一品大臣"), stage, chars
    )
    assert chars["林探长"].directive == "当上一品大臣"
    assert chars["林探长"].goal == "g"  # 钦定牵引:不硬覆盖底层 goal
    assert events == []
    assert "林探长" in status


def test_apply_unmandate_clears_directive():
    stage, chars = make_stage_and_chars()
    chars["林探长"].directive = "当上一品大臣"
    apply_command(parse_command("unmandate 林探长"), stage, chars)
    assert chars["林探长"].directive == ""


def test_apply_mandate_unknown_character_returns_error():
    stage, chars = make_stage_and_chars()
    status, events = apply_command(
        parse_command("mandate 张三: 目标"), stage, chars
    )
    assert events == []
    assert "张三" in status


def test_apply_beat_adds_event_without_changing_scene():
    stage, chars = make_stage_and_chars()  # 初始 scene="场景"
    cmd = parse_command("beat: 远处传来一声惨叫")
    status, events = apply_command(cmd, stage, chars)
    assert len(events) == 1
    assert events[0].type == "world_event"
    assert events[0].content == "远处传来一声惨叫"
    assert stage.scene == "场景"  # 小插曲不冲掉常驻场景


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


def test_exit_command_parsed():
    cmd = parse_command("exit 老周")
    assert cmd.kind == "exit"
    assert cmd.target == "老周"


def test_enter_command_parsed():
    cmd = parse_command("enter 老周")
    assert cmd.kind == "enter"
    assert cmd.target == "老周"


def test_apply_exit_deactivates_character():
    stage, chars = make_stage_and_chars()
    status, events = apply_command(DirectorCommand("exit", target="苏小姐"), stage, chars)
    assert chars["苏小姐"].active is False
    assert events == []
    assert "苏小姐" in status


def test_apply_enter_reactivates_character():
    stage, chars = make_stage_and_chars()
    chars["苏小姐"].active = False
    apply_command(DirectorCommand("enter", target="苏小姐"), stage, chars)
    assert chars["苏小姐"].active is True


def test_apply_exit_unknown_character_returns_error():
    stage, chars = make_stage_and_chars()
    status, events = apply_command(DirectorCommand("exit", target="张三"), stage, chars)
    assert events == []
    assert "张三" in status
