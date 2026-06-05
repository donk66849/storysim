from dataclasses import dataclass

EVENT_TYPES = {"narration", "speech", "action", "world_event", "director"}


@dataclass
class Event:
    round: int
    type: str
    actor: str
    content: str

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "type": self.type,
            "actor": self.actor,
            "content": self.content,
        }
