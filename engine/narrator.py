from engine.events import Event
from engine.llm import LLMClient
from engine.stage import Stage

_SYSTEM = (
    "你是这部互动剧的旁白。用简洁、有画面感的语言描述本回合开场的场景与氛围,"
    "2-3 句即可。只描写环境与气氛,不替任何角色说话或行动。"
)

_FINALE_SYSTEM = (
    "你是这部互动剧的旁白。现在是故事的最终回合,请用收束、有分量的笔触为大结局铺陈开场,"
    "把张力推向顶点。2-3 句即可,只描写环境与气氛,不替任何角色说话或行动。"
)

_EPILOGUE_SYSTEM = (
    "你是这部互动剧的旁白。请为整个故事写下大结局:用 2-4 句交代尘埃落定后的图景与余韵,"
    "给整段剧情一个明确的收束。只用旁白口吻,不替任何角色新增台词。"
)


class Narrator:
    def narrate(
        self, stage: Stage, llm: LLMClient, k: int | None = None, finale: bool = False
    ) -> Event:
        user = (
            f"场景设定:{stage.scene}\n\n"
            f"已发生的剧情:\n{stage.transcript(k)}\n\n"
            f"请描写本回合的开场氛围。"
        )
        messages = [
            {"role": "system", "content": _FINALE_SYSTEM if finale else _SYSTEM},
            {"role": "user", "content": user},
        ]
        content = llm.complete(messages).strip()
        return stage.add("narration", "旁白", content)

    def epilogue(self, stage: Stage, llm: LLMClient, k: int | None = None) -> Event:
        """最终回合所有角色行动后,补一条收束全局的大结局旁白。"""
        user = (
            f"场景设定:{stage.scene}\n\n"
            f"已发生的剧情:\n{stage.transcript(k)}\n\n"
            f"请写下这个故事的大结局。"
        )
        messages = [
            {"role": "system", "content": _EPILOGUE_SYSTEM},
            {"role": "user", "content": user},
        ]
        content = llm.complete(messages).strip()
        return stage.add("narration", "旁白", content)
