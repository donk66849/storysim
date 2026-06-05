import json
import queue
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from engine.archive import Archive
from engine.character import Character
from engine.config import load_config
from engine.director import DirectorCommand, apply_command
from engine.llm import make_llm_from_env
from engine.narrator import Narrator
from engine.round_engine import play_round
from engine.stage import Stage

load_dotenv()

# 可替换的 LLM 工厂(测试注入 FakeLLM)
_make_llm = make_llm_from_env

STATIC_DIR = Path(__file__).parent / "static"
PRESET_PATH = Path(__file__).parent.parent / "config" / "雨夜古宅.yaml"


@dataclass
class Session:
    title: str
    stage: Stage
    characters: list
    char_map: dict
    narrator: Narrator
    llm: object
    archive: Archive
    max_rounds: int
    k: int | None


_sessions: dict[str, Session] = {}

app = FastAPI(title="StorySim Web")


class CharacterIn(BaseModel):
    name: str
    persona: str = ""
    goal: str = ""
    voice: str = ""


class StoryIn(BaseModel):
    title: str
    scene: str
    characters: list[CharacterIn]
    max_rounds: int = 20
    k: int | None = None


class CommandIn(BaseModel):
    kind: str
    target: str | None = None
    field: str | None = None
    value: str | None = None


class SettingsIn(BaseModel):
    max_rounds: int | None = None
    k: int | None = None


def _char_dicts(session: Session) -> list[dict]:
    return [
        {"name": c.name, "persona": c.persona, "goal": c.goal, "voice": c.voice}
        for c in session.characters
    ]


def _get(session_id: str) -> Session:
    s = _sessions.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="会话不存在,请重新创建故事")
    return s


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/preset")
def preset():
    cfg = load_config(PRESET_PATH)
    return {
        "title": cfg.title,
        "scene": cfg.scene,
        "max_rounds": cfg.max_rounds,
        "characters": [
            {"name": c.name, "persona": c.persona, "goal": c.goal, "voice": c.voice}
            for c in cfg.characters
        ],
    }


@app.post("/api/story")
def create_story(body: StoryIn):
    try:
        llm = _make_llm()
    except Exception as exc:  # 缺 key 等
        raise HTTPException(status_code=500, detail=f"LLM 初始化失败:{exc}")
    characters = [
        Character(name=c.name, persona=c.persona, goal=c.goal, voice=c.voice)
        for c in body.characters
    ]
    stage = Stage(body.scene)
    session = Session(
        title=body.title,
        stage=stage,
        characters=characters,
        char_map={c.name: c for c in characters},
        narrator=Narrator(),
        llm=llm,
        archive=Archive("runs", body.title),
        max_rounds=body.max_rounds,
        k=body.k,
    )
    sid = uuid.uuid4().hex
    _sessions[sid] = session
    return {
        "session_id": sid,
        "title": session.title,
        "scene": stage.scene,
        "characters": _char_dicts(session),
        "round": stage.round,
        "max_rounds": session.max_rounds,
        "k": session.k,
    }


@app.get("/api/story/{session_id}/round")
def play(session_id: str):
    session = _get(session_id)

    def gen():
        q: queue.Queue = queue.Queue()
        sentinel = object()

        def worker():
            try:
                play_round(
                    session.stage,
                    session.narrator,
                    session.characters,
                    session.llm,
                    k=session.k,
                    on_event=lambda e: q.put(("event", e)),
                )
            except Exception as exc:  # LLM 超时 / 报错
                q.put(("error", str(exc)))
            finally:
                q.put((sentinel, None))

        threading.Thread(target=worker, daemon=True).start()
        while True:
            kind, payload = q.get()
            if kind is sentinel:
                break
            if kind == "event":
                session.archive.log(payload)
                yield _sse({"kind": "event", "event": payload.to_dict()})
            else:
                yield _sse({"kind": "error", "message": payload})
        yield _sse({"kind": "done", "round": session.stage.round})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/story/{session_id}/command")
def command(session_id: str, body: CommandIn):
    session = _get(session_id)
    cmd = DirectorCommand(
        kind=body.kind, target=body.target, field=body.field, value=body.value
    )
    status, events = apply_command(cmd, session.stage, session.char_map)
    for e in events:
        session.archive.log(e)
    return {"status": status, "events": [e.to_dict() for e in events]}


@app.post("/api/story/{session_id}/save")
def save(session_id: str):
    session = _get(session_id)
    session.archive.write_markdown(session.stage)
    return {
        "md_path": str(session.archive.md_path),
        "jsonl_path": str(session.archive.jsonl_path),
    }


@app.get("/api/story/{session_id}/state")
def state(session_id: str):
    session = _get(session_id)
    return {
        "title": session.title,
        "scene": session.stage.scene,
        "characters": _char_dicts(session),
        "round": session.stage.round,
        "max_rounds": session.max_rounds,
        "k": session.k,
        "events": [e.to_dict() for e in session.stage.events],
    }


@app.patch("/api/story/{session_id}/settings")
def settings(session_id: str, body: SettingsIn):
    session = _get(session_id)
    if body.max_rounds is not None:
        session.max_rounds = body.max_rounds
    if body.k is not None:
        session.k = body.k
    return {"max_rounds": session.max_rounds, "k": session.k}
