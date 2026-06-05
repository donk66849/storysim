from engine.events import Event
from engine.llm import LLMClient
from engine.stage import Stage

_SYSTEM = (
    "你是这部互动剧的旁白。用简洁、有画面感的语言描述本回合开场的场景与氛围,"
    "2-3 句即可。只描写环境与气氛,不替任何角色说话或行动。"
)


class Narrator:
    def narrate(self, stage: Stage, llm: LLMClient, k: int | None = None) -> Event:
        user = (
            f"场景设定:{stage.scene}\n\n"
            f"已发生的剧情:\n{stage.transcript(k)}\n\n"
            f"请描写本回合的开场氛围。"
        )
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ]
        content = llm.complete(messages).strip()
        return stage.add("narration", "旁白", content)
