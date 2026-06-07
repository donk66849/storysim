from engine.events import Event

_FORMATTERS = {
    "narration": lambda e: f"〔{e.content}〕",
    "speech": lambda e: f"{e.actor}:{e.content}",
    "action": lambda e: f"{e.actor}({e.content})",
    "world_event": lambda e: f"【世界事件】{e.content}",
    "director": lambda e: f"【导演】{e.content}",
}


def render_event(event: Event) -> str:
    fmt = _FORMATTERS.get(event.type, lambda e: f"{e.actor}:{e.content}")
    return fmt(event)


class Stage:
    """共享剧情记录 + 上下文拼装。这串事件即「记忆」。"""

    def __init__(self, scene: str):
        self.scene = scene
        self.events: list[Event] = []
        self.round = 0
        self.director_will = ""  # 导演常驻旨意/走向:抗 k 截断、不进 events,每回合下发给旁白与所有角色

    def set_will(self, text: str) -> None:
        """覆盖式更新导演走向;空串=清空(不像 private_notes 那样越堆越稀释)。"""
        self.director_will = (text or "").strip()

    def start_round(self) -> int:
        self.round += 1
        return self.round

    def add(self, type: str, actor: str, content: str) -> Event:
        event = Event(round=self.round, type=type, actor=actor, content=content)
        self.events.append(event)
        return event

    def recent(self, k: int | None = None) -> list[Event]:
        if k is None:
            return list(self.events)
        return self.events[-k:]

    def transcript(self, k: int | None = None) -> str:
        return "\n".join(render_event(e) for e in self.recent(k))
