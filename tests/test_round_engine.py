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


def test_play_round_advances_round_number_each_call():
    stage = Stage("场景")
    chars = make_chars()
    llm = FakeLLM(["n1", "a1", "b1", "n2", "a2", "b2"])
    play_round(stage, Narrator(), chars, llm)
    play_round(stage, Narrator(), chars, llm)
    assert stage.round == 2
    assert stage.events[-1].round == 2
