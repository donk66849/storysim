from dataclasses import dataclass


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
