from engine.round_engine import play_round
from engine.stage import Stage
from engine.narrator import Narrator
from engine.character import Character
from engine.llm import FakeLLM


def make_chars():
    a = Character("甲", "人设甲", "目标甲", "风格甲")
    b = Character("乙", "人设乙", "目标乙", "风格乙")
    return [a, b]


def test_play_round_order_is_narrator_then_characters():
    stage = Stage("场景")
    chars = make_chars()
    llm = FakeLLM(["旁白词", "甲的台词", "乙的台词"])
    produced = play_round(stage, Narrator(), chars, llm)
    assert [(e.type, e.actor) for e in produced] == [
        ("narration", "旁白"),
        ("speech", "甲"),
        ("speech", "乙"),
    ]
    assert stage.round == 1


def test_later_character_sees_earlier_character_within_same_round():
    stage = Stage("场景")
    chars = make_chars()
    llm = FakeLLM(["旁白词", "甲的台词", "乙的台词"])
    play_round(stage, Narrator(), chars, llm)
    # 第三次调用是「乙」,其 user prompt 应包含「甲」刚说的话
    yi_user = llm.calls[2][-1]["content"]
    assert "甲:甲的台词" in yi_user


def test_on_event_called_for_each_event_in_order():
    stage = Stage("场景")
    chars = make_chars()
    llm = FakeLLM(["旁白词", "甲的台词", "乙的台词"])
    seen = []
    produced = play_round(stage, Narrator(), chars, llm, on_event=seen.append)
    assert seen == produced
    assert [(e.type, e.actor) for e in seen] == [
        ("narration", "旁白"),
        ("speech", "甲"),
        ("speech", "乙"),
    ]


def test_finale_round_appends_closing_epilogue():
    stage = Stage("场景")
    chars = make_chars()
    # 开场旁白、甲、乙,最后再加一条旁白大结局
    llm = FakeLLM(["开场", "甲台词", "乙台词", "尘埃落定的大结局"])
    produced = play_round(stage, Narrator(), chars, llm, finale=True)
    assert [(e.type, e.actor) for e in produced] == [
        ("narration", "旁白"),
        ("speech", "甲"),
        ("speech", "乙"),
        ("narration", "旁白"),
    ]
    assert produced[-1].content == "尘埃落定的大结局"


def test_non_finale_round_has_no_epilogue():
    stage = Stage("场景")
    chars = make_chars()
    llm = FakeLLM(["旁白词", "甲的台词", "乙的台词"])
    produced = play_round(stage, Narrator(), chars, llm, finale=False)
    assert len(produced) == 3  # 不多出大结局旁白


def test_play_round_advances_round_number_each_call():
    stage = Stage("场景")
    chars = make_chars()
    llm = FakeLLM(["n1", "a1", "b1", "n2", "a2", "b2"])
    play_round(stage, Narrator(), chars, llm)
    play_round(stage, Narrator(), chars, llm)
    assert stage.round == 2
    assert stage.events[-1].round == 2
