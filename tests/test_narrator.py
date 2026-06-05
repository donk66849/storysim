from engine.narrator import Narrator
from engine.stage import Stage
from engine.llm import FakeLLM


def test_narrate_writes_narration_event():
    stage = Stage("暴雨中的古宅")
    stage.start_round()
    llm = FakeLLM(["闪电划过,照亮空荡的大厅。"])
    event = Narrator().narrate(stage, llm)
    assert event.type == "narration"
    assert event.actor == "旁白"
    assert event.content == "闪电划过,照亮空荡的大厅。"
    assert stage.events[-1] is event


def test_narrate_prompt_includes_scene_and_history():
    stage = Stage("暴雨中的古宅")
    stage.start_round()
    stage.add("speech", "林探长", "门被锁死了")
    llm = FakeLLM(["雨声盖过了呼吸。"])
    Narrator().narrate(stage, llm)
    user = llm.calls[0][-1]["content"]
    assert "暴雨中的古宅" in user
    assert "林探长:门被锁死了" in user
