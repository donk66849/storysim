import argparse

from dotenv import load_dotenv
from rich.console import Console

from engine.archive import Archive
from engine.config import load_config
from engine.director import apply_command, parse_command
from engine.llm import make_llm_from_env
from engine.narrator import Narrator
from engine.round_engine import play_round
from engine.stage import Stage

console = Console()

_STYLE = {
    "narration": "italic dim",
    "speech": "bold cyan",
    "action": "green",
    "world_event": "bold yellow",
    "director": "magenta",
}


def print_event(event) -> None:
    style = _STYLE.get(event.type, "white")
    if event.type == "narration":
        console.print(f"  〔{event.content}〕", style=style)
    elif event.type == "world_event":
        console.print(f"【世界】{event.content}", style=style)
    elif event.type == "director":
        console.print(f"【导演】{event.content}", style=style)
    else:
        console.print(f"{event.actor}:{event.content}", style=style)


def main() -> None:
    parser = argparse.ArgumentParser(description="StorySim 剧情推演引擎")
    parser.add_argument(
        "config", nargs="?", default="config/雨夜古宅.yaml", help="故事配置 YAML 路径"
    )
    args = parser.parse_args()

    load_dotenv()
    cfg = load_config(args.config)
    stage = Stage(cfg.scene)
    narrator = Narrator()
    char_map = {c.name: c for c in cfg.characters}
    llm = make_llm_from_env()
    archive = Archive("runs", cfg.title)

    console.rule(f"[bold]{cfg.title}")
    console.print(f"场景:{cfg.scene}\n", style="dim")

    def emit(event) -> None:
        print_event(event)
        archive.log(event)

    while stage.round < cfg.max_rounds:
        finale = stage.round + 1 >= cfg.max_rounds
        with console.status(f"[dim]第 {stage.round + 1} 回合演绎中…[/dim]"):
            play_round(stage, narrator, cfg.characters, llm, on_event=emit, finale=finale)

        console.print(
            "\n[dim]导演指令:回车继续 / event: <文本> / tell <角色>: <文本> "
            "/ set <角色> <字段>=<值> / save / quit[/dim]"
        )
        cmd = parse_command(console.input("[bold]导演> [/bold]"))

        if cmd.kind == "quit":
            break
        if cmd.kind == "save":
            archive.write_markdown(stage)
            console.print(f"[green]已存档 → {archive.md_path}[/green]")
            continue
        if cmd.kind == "continue":
            continue

        status, new_events = apply_command(cmd, stage, char_map)
        for event in new_events:
            print_event(event)
            archive.log(event)
        console.print(f"[dim]{status}[/dim]")

    archive.write_markdown(stage)
    console.rule("[bold]剧终")
    console.print(f"[green]故事已保存:[/green]\n  {archive.md_path}\n  {archive.jsonl_path}")


if __name__ == "__main__":
    main()
