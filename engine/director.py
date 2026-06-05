from dataclasses import dataclass

from engine.character import Character
from engine.events import Event
from engine.stage import Stage


@dataclass
class DirectorCommand:
    kind: str  # continue | event | tell | set | save | quit | unknown
    target: str | None = None
    field: str | None = None
    value: str | None = None


def parse_command(text: str) -> DirectorCommand:
    s = text.strip()
    if s == "":
        return DirectorCommand("continue")
    if s == "save":
        return DirectorCommand("save")
    if s == "quit":
        return DirectorCommand("quit")
    if s.startswith("event:"):
        return DirectorCommand("event", value=s[len("event:"):].strip())
    if s.startswith("exit "):
        return DirectorCommand("exit", target=s[len("exit "):].strip())
    if s.startswith("enter "):
        return DirectorCommand("enter", target=s[len("enter "):].strip())
    if s.startswith("tell ") and ":" in s:
        head, value = s[len("tell "):].split(":", 1)
        return DirectorCommand("tell", target=head.strip(), value=value.strip())
    if s.startswith("set ") and "=" in s:
        rest = s[len("set "):]
        left, value = rest.split("=", 1)
        parts = left.strip().split(None, 1)
        if len(parts) == 2:
            target, field = parts
            return DirectorCommand(
                "set", target=target.strip(), field=field.strip(), value=value.strip()
            )
    return DirectorCommand("unknown")


def apply_command(
    cmd: DirectorCommand,
    stage: Stage,
    characters: dict[str, Character],
) -> tuple[str, list[Event]]:
    """施加 event/tell/set 干预。返回 (状态文本, 新增的公共事件列表)。
    continue/save/quit 等控制流由主循环处理,不在此函数职责内。"""
    if cmd.kind == "event":
        event = stage.add("world_event", "世界", cmd.value)
        return f"已注入世界事件:{cmd.value}", [event]

    if cmd.kind == "tell":
        ch = characters.get(cmd.target)
        if ch is None:
            return f"找不到角色「{cmd.target}」", []
        ch.private_notes.append(cmd.value)
        return f"已私下告知「{cmd.target}」", []

    if cmd.kind == "set":
        ch = characters.get(cmd.target)
        if ch is None:
            return f"找不到角色「{cmd.target}」", []
        if not hasattr(ch, cmd.field):
            return f"角色没有字段「{cmd.field}」", []
        setattr(ch, cmd.field, cmd.value)
        return f"已修改「{cmd.target}」的 {cmd.field}", []

    if cmd.kind in ("exit", "enter"):
        ch = characters.get(cmd.target)
        if ch is None:
            return f"找不到角色「{cmd.target}」", []
        ch.active = cmd.kind == "enter"
        word = "重新登场" if ch.active else "退场,后续回合不再发言"
        return f"「{cmd.target}」已{word}", []

    return "无法识别的命令", []
