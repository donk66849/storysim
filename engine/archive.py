import json
from datetime import datetime
from pathlib import Path

from engine.events import Event
from engine.stage import Stage, render_event


class Archive:
    """落盘:.jsonl 结构化事件流(增量追加)+ .md 可读故事(随时重写)。"""

    def __init__(self, runs_dir: str | Path, title: str, now: datetime | None = None):
        ts = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        self.dir = Path(runs_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.title = title
        self.md_path = self.dir / f"{ts}.md"
        self.jsonl_path = self.dir / f"{ts}.jsonl"

    def log(self, event: Event) -> None:
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def write_markdown(self, stage: Stage) -> None:
        lines = [f"# {self.title}", "", f"> 场景:{stage.scene}", ""]
        current_round = None
        for e in stage.events:
            if e.round != current_round:
                current_round = e.round
                lines.append(f"## 第 {current_round} 回合")
                lines.append("")
            lines.append(render_event(e))
            lines.append("")
        self.md_path.write_text("\n".join(lines), encoding="utf-8")
