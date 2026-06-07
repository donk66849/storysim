from dataclasses import dataclass

from engine.character import Character
from engine.events import Event
from engine.stage import Stage


@dataclass
class DirectorCommand:
    kind: str  # continue | event | beat | will | mandate | unmandate | tell | set | save | quit | unknown
    target: str | None = None
    field: str | None = None
    value: str | None = None
    once: bool = False  # tell 专用:一次性叮嘱,只在下一回合生效


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
    if s.startswith("beat:"):
        return DirectorCommand("beat", value=s[len("beat:"):].strip())
    if s.startswith("twist:"):
        return DirectorCommand("beat", value=s[len("twist:"):].strip())
    if s.startswith("will:"):
        return DirectorCommand("will", value=s[len("will:"):].strip())
    if s.startswith("mandate ") and ":" in s:
        head, value = s[len("mandate "):].split(":", 1)
        return DirectorCommand("mandate", target=head.strip(), value=value.strip())
    if s.startswith("unmandate "):
        return DirectorCommand("unmandate", target=s[len("unmandate "):].strip())
    if s.startswith("exit "):
        return DirectorCommand("exit", target=s[len("exit "):].strip())
    if s.startswith("enter "):
        return DirectorCommand("enter", target=s[len("enter "):].strip())
    if s.startswith("tell ") and ":" in s:
        head, value = s[len("tell "):].split(":", 1)
        target = head.strip()
        once = False
        parts = target.split()
        if len(parts) >= 2 and parts[-1].lower() == "once":
            once = True
            target = " ".join(parts[:-1])
        return DirectorCommand("tell", target=target, value=value.strip(), once=once)
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
        # 大转折同时改写常驻场景:否则旧 scene 每回合复读,新设定只活一轮
        stage.scene = cmd.value
        return f"已注入世界事件并更新场景:{cmd.value}", [event]

    if cmd.kind == "beat":
        # 小插曲:只加一条世界事件制造张力,不冲掉常驻场景
        event = stage.add("world_event", "世界", cmd.value)
        return f"已加入插曲(未改场景):{cmd.value}", [event]

    if cmd.kind == "will":
        stage.set_will(cmd.value)
        if cmd.value:
            # 公开宣告一条锚点事件,让全场都知道走向已被导演接管(常驻约束另存于 stage.director_will)
            event = stage.add("director", "导演", f"剧情走向:{cmd.value}")
            return f"已设定剧情走向:{cmd.value}", [event]
        return "已清空剧情走向", []

    if cmd.kind == "mandate":
        ch = characters.get(cmd.target)
        if ch is None:
            return f"找不到角色「{cmd.target}」", []
        ch.directive = cmd.value  # 钦定牵引:写 directive,不硬覆盖底层 goal
        return f"已钦定「{cmd.target}」的首要目标:{cmd.value}", []

    if cmd.kind == "unmandate":
        ch = characters.get(cmd.target)
        if ch is None:
            return f"找不到角色「{cmd.target}」", []
        ch.directive = ""
        return f"已解除「{cmd.target}」的钦定目标", []

    if cmd.kind == "tell":
        ch = characters.get(cmd.target)
        if ch is None:
            return f"找不到角色「{cmd.target}」", []
        if cmd.once:
            ch.oneshot_notes.append(cmd.value)
            return f"已私下叮嘱「{cmd.target}」(仅本回合)", []
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
