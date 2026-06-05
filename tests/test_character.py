from engine.character import Character
from engine.stage import Stage
from engine.llm import FakeLLM


def make_char(**kw):
    defaults = dict(
        name="林探长",
        persona="退休侦探,多疑、逻辑强",
        goal="查清古宅里发生过什么",
        voice="冷静,爱用反问",
    )
    defaults.update(kw)
    return Character(**defaults)


def test_system_prompt_contains_persona_fields():
    ch = make_char()
    sp = ch.system_prompt()
    assert "林探长" in sp
    assert "退休侦探" in sp
    assert "查清古宅里发生过什么" in sp
    assert "冷静,爱用反问" in sp


def test_system_prompt_includes_private_notes():
    ch = make_char(private_notes=["你其实早就认识苏小姐"])
    assert "你其实早就认识苏小姐" in ch.system_prompt()


def test_act_calls_llm_and_writes_speech_to_stage():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char()
    llm = FakeLLM(["谁在那儿?"])
    event = ch.act(stage, llm)
    assert event.type == "speech"
    assert event.actor == "林探长"
    assert event.content == "谁在那儿?"
    assert stage.events[-1] is event


def test_act_finale_prompt_asks_for_an_ending():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char()
    llm = FakeLLM(["我知道凶手是谁了。"])
    ch.act(stage, llm, finale=True)
    user = llm.calls[0][-1]["content"]
    assert "最终回合" in user


def test_act_non_finale_prompt_has_no_ending_instruction():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char()
    llm = FakeLLM(["谁在那儿?"])
    ch.act(stage, llm)
    assert "最终回合" not in llm.calls[0][-1]["content"]


def test_act_messages_carry_scene_and_recent_transcript():
    stage = Stage("古宅大厅")
    stage.start_round()
    stage.add("speech", "苏小姐", "我先到的")
    ch = make_char()
    llm = FakeLLM(["你几点到的?"])
    ch.act(stage, llm)
    messages = llm.calls[0]
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    user = messages[-1]["content"]
    assert "古宅大厅" in user
    assert "苏小姐:我先到的" in user
