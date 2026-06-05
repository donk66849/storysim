from dataclasses import dataclass, field

from engine.events import Event
from engine.llm import LLMClient
from engine.stage import Stage


@dataclass
class Character:
    name: str
    persona: str
    goal: str
    voice: str
    private_notes: list[str] = field(default_factory=list)
    active: bool = True  # 退场(死亡/离开)后置 False,不再参与回合

    def system_prompt(self) -> str:
        parts = [
            f"你是「{self.name}」。",
            f"人设:{self.persona}",
            f"目标:{self.goal}",
            f"说话风格:{self.voice}",
            "你正在出演一部互动剧。始终保持角色,不要跳出,不要替别的角色说话。",
        ]
        if self.private_notes:
            parts.append(
                "\n[导演私下指令——最高优先级,你必须严格遵守下列每一条;"
                "即使与场上其他人不同、与你之前的表现不同也照做,"
                "不要向其他角色说破这是导演的安排]"
            )
            parts.extend(f"- {note}" for note in self.private_notes)
        return "\n".join(parts)

    def _user_prompt(self, stage: Stage, k: int | None, finale: bool = False) -> str:
        prompt = (
            f"当前场景:{stage.scene}\n\n"
            f"已发生的剧情:\n{stage.transcript(k)}\n\n"
            f"（轮到你了，以「{self.name}」的身份行动。要求:\n"
            f"1. 只用 1-2 句,像剧本台词一样简短,不要写大段旁白式的环境/动作描写。\n"
            f"2. 先回应最近发生的事:若刚出现【世界事件】或别的角色刚说/做了要紧的事,"
            f"你必须先对此作出反应,再推进剧情——给出新信息或做出新决定。不要重复你说过的话。\n"
            f"3. 只输出你自己说的话或做的动作,不要替别的角色说话。"
        )
        if finale:
            prompt += (
                "\n4. 这是故事的最终回合:请为你的角色收尾——做出最终抉择、了结心结"
                "或揭晓秘密,把你的故事线推向结局。"
            )
        return prompt + "）"

    def act(
        self, stage: Stage, llm: LLMClient, k: int | None = None, finale: bool = False
    ) -> Event:
        messages = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": self._user_prompt(stage, k, finale)},
        ]
        content = llm.complete(messages).strip()
        return stage.add("speech", self.name, content)
