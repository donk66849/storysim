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


def test_private_notes_framed_as_must_obey():
    ch = make_char(private_notes=["从现在起你只能说英语"])
    sp = ch.system_prompt()
    # 私下叮嘱要被表述成必须执行的硬指令,而不只是"你知道的秘密"
    assert "严格遵守" in sp


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


def test_act_prompt_allows_longer_reaction_to_big_events():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char()
    llm = FakeLLM(["……"])
    ch.act(stage, llm)
    user = llm.calls[0][-1]["content"]
    # 大事件/被逼问时允许用更长的篇幅消化冲击
    assert "3-4 句" in user


def test_act_prompt_asks_to_pick_up_unresolved_hooks():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char()
    llm = FakeLLM(["……"])
    ch.act(stage, llm)
    user = llm.calls[0][-1]["content"]
    # 鼓励角色主动回收埋下的伏笔,别让它凭空消失
    assert "凭空消失" in user


def test_private_notes_framed_to_be_woven_naturally():
    ch = make_char(private_notes=["你其实是凶手"])
    sp = ch.system_prompt()
    # 叮嘱要自然揉进表演,而非生硬宣读
    assert "自然地揉进" in sp


def test_oneshot_note_appears_in_system_prompt():
    ch = make_char(oneshot_notes=["这一回合突然崩溃大哭"])
    assert "这一回合突然崩溃大哭" in ch.system_prompt()


def test_oneshot_notes_consumed_after_act_but_persistent_notes_kept():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char(private_notes=["你藏着钥匙"], oneshot_notes=["突然翻脸"])
    llm = FakeLLM(["你们都给我站住!"])
    ch.act(stage, llm)
    # 一次性叮嘱演完即止,长期人设保留
    assert ch.oneshot_notes == []
    assert ch.private_notes == ["你藏着钥匙"]


def test_act_prompt_drops_stale_attachments_but_keeps_director_goal():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char()
    llm = FakeLLM(["……"])
    ch.act(stage, llm)
    user = llm.calls[0][-1]["content"]
    # 世界剧变后:无关旧执念可放下,但导演钦定目标必须坚持(翻转旧的"目标随之调整")
    assert "旧执念可以放下" in user
    assert "必须坚持" in user
    assert "目标也应随之调整" not in user


def test_system_prompt_shows_directive_above_old_goal():
    ch = make_char(directive="当上一品大臣")
    sp = ch.system_prompt()
    assert "当上一品大臣" in sp
    assert "旧目标" in sp
    # 钦定的首要目标呈现在旧目标之上
    assert sp.index("当上一品大臣") < sp.index("查清古宅里发生过什么")


def test_system_prompt_without_directive_keeps_plain_goal():
    ch = make_char()  # directive 默认空
    sp = ch.system_prompt()
    assert "目标:查清古宅里发生过什么" in sp
    assert "旧目标" not in sp


def test_system_prompt_includes_director_will_when_given():
    ch = make_char()
    sp = ch.system_prompt(director_will="全员卷入夺嫡")
    assert "全员卷入夺嫡" in sp


def test_system_prompt_callable_without_args():
    # 向后兼容:无参调用仍可用(默认无旨意)
    assert "林探长" in make_char().system_prompt()


def test_user_prompt_has_recency_anchor_when_directive_set():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char(directive="当上一品大臣")
    llm = FakeLLM(["……"])
    ch.act(stage, llm)
    user = llm.calls[0][-1]["content"]
    assert "当上一品大臣" in user
    assert "推进一步" in user


def test_user_prompt_no_anchor_when_no_directive_or_will():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char()  # 无 directive,stage 无 will
    llm = FakeLLM(["……"])
    ch.act(stage, llm)
    assert "推进一步" not in llm.calls[0][-1]["content"]


def test_act_system_message_carries_director_will():
    stage = Stage("古宅大厅")
    stage.start_round()
    stage.set_will("林探长青云直上")
    ch = make_char()
    llm = FakeLLM(["……"])
    ch.act(stage, llm)
    assert "林探长青云直上" in llm.calls[0][0]["content"]


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
