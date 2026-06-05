from dataclasses import dataclass
from pathlib import Path

import yaml

from engine.character import Character

DEFAULT_MAX_ROUNDS = 20


@dataclass
class StoryConfig:
    title: str
    scene: str
    max_rounds: int
    characters: list[Character]


def load_config(path: str | Path) -> StoryConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    characters = [
        Character(
            name=c["name"],
            persona=c["persona"],
            goal=c["goal"],
            voice=c["voice"],
        )
        for c in data["characters"]
    ]
    return StoryConfig(
        title=data["title"],
        scene=data["scene"],
        max_rounds=data.get("max_rounds", DEFAULT_MAX_ROUNDS),
        characters=characters,
    )
