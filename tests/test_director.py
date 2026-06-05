from engine.director import parse_command, DirectorCommand


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
