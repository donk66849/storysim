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

    def system_prompt(self) -> str:
        parts = [
            f"你是「{self.name}」。",
            f"人设:{self.persona}",
            f"目标:{self.goal}",
            f"说话风格:{self.voice}",
            "你正在出演一部互动剧。始终保持角色,不要跳出,不要替别的角色说话。",
        ]
        if self.private_notes:
            parts.append("\n[导演私下叮嘱(只有你知道)]")
            parts.extend(f"- {note}" for note in self.private_notes)
        return "\n".join(parts)

    def _user_prompt(self, stage: Stage, k: int | None) -> str:
        return (
            f"当前场景:{stage.scene}\n\n"
            f"已发生的剧情:\n{stage.transcript(k)}\n\n"
            f"（轮到你了。以「{self.name}」的身份说一句台词或做一个动作，"
            f"只输出你自己的内容，简短自然。）"
        )

    def act(self, stage: Stage, llm: LLMClient, k: int | None = None) -> Event:
        messages = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": self._user_prompt(stage, k)},
        ]
        content = llm.complete(messages).strip()
        return stage.add("speech", self.name, content)
