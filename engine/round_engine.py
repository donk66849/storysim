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
) -> list[Event]:
    """跑完一整回合:旁白开场,然后每个角色按固定顺序行动。
    角色台词立刻写回 Stage,故同回合后面的角色能看到前面的(对戏)。"""
    stage.start_round()
    produced: list[Event] = [narrator.narrate(stage, llm, k)]
    for ch in characters:
        produced.append(ch.act(stage, llm, k))
    return produced
