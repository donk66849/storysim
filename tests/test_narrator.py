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


def test_narrate_prompt_includes_cast_override_for_conflicting_scene_count():
    stage = Stage("三个陌生人被暴雨困在古宅里")
    stage.start_round()
    llm = FakeLLM(["雨声盖过了两人的呼吸。"])
    Narrator().narrate(stage, llm, cast_names=["林探长", "苏小姐"])
    user = llm.calls[0][-1]["content"]
    assert "当前登场角色:林探长、苏小姐" in user
    assert "以名单为准" in user
    assert "不要凭空添加名单外的第三人" in user


def test_narrate_user_includes_director_will():
    stage = Stage("汴京街头")
    stage.start_round()
    stage.set_will("林探长青云直上,最终位极人臣")
    llm = FakeLLM(["晨雾里酒旗招展。"])
    Narrator().narrate(stage, llm)
    user = llm.calls[0][-1]["content"]
    assert "林探长青云直上,最终位极人臣" in user


def test_narrate_omits_will_line_when_empty():
    stage = Stage("汴京街头")
    stage.start_round()
    llm = FakeLLM(["晨雾里酒旗招展。"])
    Narrator().narrate(stage, llm)
    assert "导演当前走向" not in llm.calls[0][-1]["content"]


def test_narrate_system_dramatizes_recent_world_event():
    stage = Stage("古宅")
    stage.start_round()
    llm = FakeLLM(["余烬未熄。"])
    Narrator().narrate(stage, llm)
    system = llm.calls[0][0]["content"]
    # 旁白被要求顺着刚发生的世界事件渲染余波,而非另起炉灶
    assert "余波" in system


def test_finale_narrate_uses_finale_framing():
    stage = Stage("古宅")
    stage.start_round()
    llm = FakeLLM(["最后的雷声炸响。"])
    Narrator().narrate(stage, llm, finale=True)
    system = llm.calls[0][0]["content"]
    assert "最终回合" in system


def test_epilogue_writes_closing_narration():
    stage = Stage("古宅")
    stage.start_round()
    llm = FakeLLM(["尘埃落定,众人各自离去。"])
    event = Narrator().epilogue(stage, llm)
    assert event.type == "narration"
    assert event.actor == "旁白"
    assert event.content == "尘埃落定,众人各自离去。"
    assert stage.events[-1] is event
    assert "大结局" in llm.calls[0][0]["content"]
