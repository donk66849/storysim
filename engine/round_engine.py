from typing import Callable

from engine.character import Character
from engine.events import Event
from engine.llm import LLMClient
from engine.narrator import Narrator
from engine.stage import Stage


def play_round(
    stage: Stage,
    narrator: Narrator,
    characters: list[Character],
    llm: LLMClient,
    k: int | None = None,
    on_event: Callable[[Event], None] | None = None,
    finale: bool = False,
) -> list[Event]:
    """跑完一整回合:旁白开场,然后每个角色按固定顺序行动。
    角色台词立刻写回 Stage,故同回合后面的角色能看到前面的(对戏)。

    on_event:每产生一条事件就立刻回调一次(用于实时打印 / 落盘),
    让使用者看到逐条推进而非整回合一次性冒出。

    finale:最终回合。旁白开场与角色行动都会被引导收尾,所有角色行动后再补一条
    旁白大结局,给整段剧情一个明确收束。"""
    stage.start_round()
    produced: list[Event] = []

    def emit(event: Event) -> None:
        produced.append(event)
        if on_event is not None:
            on_event(event)

    emit(narrator.narrate(stage, llm, k, finale=finale))
    for ch in characters:
        if not ch.active:  # 已退场(死亡/离开)的角色不再发言
            continue
        emit(ch.act(stage, llm, k, finale=finale))
    if finale:
        emit(narrator.epilogue(stage, llm, k))
    return produced
