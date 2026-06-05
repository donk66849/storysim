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
) -> list[Event]:
    """跑完一整回合:旁白开场,然后每个角色按固定顺序行动。
    角色台词立刻写回 Stage,故同回合后面的角色能看到前面的(对戏)。

    on_event:每产生一条事件就立刻回调一次(用于实时打印 / 落盘),
    让使用者看到逐条推进而非整回合一次性冒出。"""
    stage.start_round()
    produced: list[Event] = []

    def emit(event: Event) -> None:
        produced.append(event)
        if on_event is not None:
            on_event(event)

    emit(narrator.narrate(stage, llm, k))
    for ch in characters:
        emit(ch.act(stage, llm, k))
    return produced
