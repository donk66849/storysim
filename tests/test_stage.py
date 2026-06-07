from engine.events import Event
from engine.stage import Stage


def test_event_to_dict_keeps_field_order():
    e = Event(round=3, type="speech", actor="林探长", content="谁在那儿?")
    assert e.to_dict() == {
        "round": 3,
        "type": "speech",
        "actor": "林探长",
        "content": "谁在那儿?",
    }


def test_stage_starts_at_round_zero_with_scene():
    stage = Stage("三个陌生人被困古宅")
    assert stage.scene == "三个陌生人被困古宅"
    assert stage.round == 0
    assert stage.events == []


def test_new_stage_has_empty_director_will():
    assert Stage("场景").director_will == ""


def test_set_will_sets_and_strips_and_clears():
    stage = Stage("场景")
    stage.set_will("  全员卷入夺嫡  ")
    assert stage.director_will == "全员卷入夺嫡"
    stage.set_will("")
    assert stage.director_will == ""


def test_director_will_does_not_enter_transcript():
    stage = Stage("场景")
    stage.start_round()
    stage.set_will("林探长青云直上")
    # 旨意是常驻字段,不进 events / transcript
    assert stage.events == []
    assert "林探长青云直上" not in stage.transcript()


def test_start_round_increments_and_returns():
    stage = Stage("场景")
    assert stage.start_round() == 1
    assert stage.start_round() == 2
    assert stage.round == 2


def test_add_uses_current_round_and_returns_event():
    stage = Stage("场景")
    stage.start_round()
    e = stage.add("speech", "苏小姐", "我不知道")
    assert e.round == 1
    assert e.type == "speech"
    assert e.actor == "苏小姐"
    assert e.content == "我不知道"
    assert stage.events == [e]


def test_recent_returns_last_k_or_all():
    stage = Stage("场景")
    stage.start_round()
    for i in range(5):
        stage.add("speech", "A", str(i))
    assert [e.content for e in stage.recent(2)] == ["3", "4"]
    assert len(stage.recent()) == 5
    assert len(stage.recent(None)) == 5


def test_transcript_formats_each_type():
    stage = Stage("场景")
    stage.start_round()
    stage.add("narration", "旁白", "雨更大了")
    stage.add("speech", "林探长", "别动")
    stage.add("action", "苏小姐", "后退一步")
    stage.add("world_event", "世界", "灯全灭了")
    stage.add("director", "导演", "时间跳到午夜")
    text = stage.transcript()
    assert "〔雨更大了〕" in text
    assert "林探长:别动" in text
    assert "苏小姐(后退一步)" in text
    assert "【世界事件】灯全灭了" in text
    assert "【导演】时间跳到午夜" in text


def test_transcript_respects_k():
    stage = Stage("场景")
    stage.start_round()
    stage.add("speech", "A", "旧")
    stage.add("speech", "A", "新")
    assert "旧" not in stage.transcript(1)
    assert "新" in stage.transcript(1)
