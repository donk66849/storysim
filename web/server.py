import json
import logging
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 允许直接 `python web/server.py` 运行(把项目根加入 import 路径)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.archive import Archive
from engine.character import Character
from engine.config import load_config
from engine.director import DirectorCommand, apply_command
from engine.llm import make_llm_from_env
from engine.narrator import Narrator
from engine.round_engine import play_round
from engine.stage import Stage
from web.limits import Quota, RateLimiter, _env_int

load_dotenv()

logger = logging.getLogger("storysim")

# 上线防护:输入封顶,单个会话就烧不出天价账单
MAX_ROUNDS_CAP = 30
MAX_CHARACTERS = 8
MAX_TITLE = 100
MAX_FIELD = 2000

# 上线防护:会话与请求体上限,挡内存 / 磁盘滥用
MAX_SESSIONS = _env_int("STORYSIM_MAX_SESSIONS", 500)        # 内存里同时存活的会话数上限
SESSION_TTL = _env_int("STORYSIM_SESSION_TTL", 1800)          # 闲置多少秒后回收(默认 30 分钟)
MAX_BODY_BYTES = _env_int("STORYSIM_MAX_BODY_BYTES", 64 * 1024)  # 请求体字节上限

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
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_active: float = field(default_factory=time.monotonic)


_sessions: dict[str, Session] = {}
_quota = Quota()  # 每日体验配额(每 IP / 每浏览器 / 全站)
# 高频接口限流:建故事 / 提反馈,按 IP 挡刷接口的内存与磁盘滥用
_story_limiter = RateLimiter(_env_int("STORYSIM_CREATE_PER_MIN", 20), 60)
_feedback_limiter = RateLimiter(_env_int("STORYSIM_FEEDBACK_PER_10MIN", 10), 600)

app = FastAPI(title="StorySim Web")

# 静态资源(收款码等图片);assets 子目录单独挂载,不暴露 index.html
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.middleware("http")
async def _limit_body_size(request: Request, call_next):
    # 据 Content-Length 提前挡掉超大请求体,避免 Pydantic 解析前就吃内存
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "请求体过大"})
    return await call_next(request)


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


class FeedbackIn(BaseModel):
    text: str
    contact: str | None = None


def _validate_story(body: "StoryIn") -> None:
    if not body.title.strip() or not body.scene.strip():
        raise HTTPException(status_code=400, detail="标题和场景不能为空")
    if len(body.title) > MAX_TITLE or len(body.scene) > MAX_FIELD:
        raise HTTPException(status_code=400, detail="标题或场景过长")
    named = [c for c in body.characters if c.name.strip()]
    if not named:
        raise HTTPException(status_code=400, detail="至少需要一个有名字的角色")
    if len(body.characters) > MAX_CHARACTERS:
        raise HTTPException(status_code=400, detail=f"角色最多 {MAX_CHARACTERS} 个")
    for c in body.characters:
        if any(len(x) > MAX_FIELD for x in (c.persona, c.goal, c.voice)) or len(c.name) > MAX_TITLE:
            raise HTTPException(status_code=400, detail="角色字段过长")


def _char_dicts(session: Session) -> list[dict]:
    return [
        {"name": c.name, "persona": c.persona, "goal": c.goal, "voice": c.voice}
        for c in session.characters
    ]


def _client_ip(request: Request) -> str:
    # 配了 --proxy-headers 后,Caddy 传来的 X-Forwarded-For 已反映到 request.client
    return request.client.host if request.client else "?"


def _evict_sessions() -> None:
    """回收闲置会话,并在数量超限时淘汰最久未活动的,防内存被建会话刷爆。"""
    now = time.monotonic()
    for sid in [sid for sid, s in _sessions.items() if now - s.last_active > SESSION_TTL]:
        _sessions.pop(sid, None)
    if len(_sessions) >= MAX_SESSIONS:
        ordered = sorted(_sessions.items(), key=lambda kv: kv[1].last_active)
        for sid, _ in ordered[: len(_sessions) - MAX_SESSIONS + 1]:
            _sessions.pop(sid, None)


def _get(session_id: str) -> Session:
    s = _sessions.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="会话不存在,请重新创建故事")
    s.last_active = time.monotonic()
    return s


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/")
def index():
    # 开发期禁缓存,避免浏览器拿到旧的 index.html
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


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
def create_story(body: StoryIn, request: Request):
    if not _story_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="创建太频繁啦,歇一会儿再试~")
    _validate_story(body)
    _evict_sessions()
    try:
        llm = _make_llm()
    except Exception:  # 缺 key 等;细节只进服务端日志,不回传客户端
        logger.exception("LLM 初始化失败")
        raise HTTPException(status_code=500, detail="服务暂时不可用,请稍后再试")
    characters = [
        Character(name=c.name, persona=c.persona, goal=c.goal, voice=c.voice)
        for c in body.characters
        if c.name.strip()
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
        max_rounds=max(1, min(body.max_rounds, MAX_ROUNDS_CAP)),
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
def play(session_id: str, request: Request):
    session = _get(session_id)
    # 服务端兜底:到达总轮数就不再演,直接回 done(前端按钮也会禁用)
    if session.stage.round >= session.max_rounds:
        return StreamingResponse(
            iter([_sse({"kind": "done", "round": session.stage.round})]),
            media_type="text/event-stream",
        )
    # 同一会话同一时刻只允许一个回合在演,避免并发把 Stage 改乱
    if not session.lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="本回合仍在进行中,请稍候")
    # 每日体验配额:每 IP / 每浏览器 / 全站总量。被拦则礼貌提示,不推进、不扣额度
    ip = request.client.host if request.client else "?"
    cid = request.query_params.get("cid", "")
    reason = _quota.try_consume(ip, cid)
    if reason is not None:
        session.lock.release()
        return StreamingResponse(
            iter([
                _sse({"kind": "error", "message": reason}),
                _sse({"kind": "done", "round": session.stage.round}),
            ]),
            media_type="text/event-stream",
        )

    # 即将要演的这一回合就是设定的最后一回合 → 走大结局
    finale = session.stage.round + 1 >= session.max_rounds

    def gen():
        q: queue.Queue = queue.Queue()
        sentinel = object()
        round_before = session.stage.round
        produced = 0

        def on_event(e):
            nonlocal produced
            produced += 1
            session.archive.log(e)  # 在产生处即落盘,客户端中断也不会让 jsonl 缺行
            q.put(("event", e))

        def worker():
            try:
                play_round(
                    session.stage,
                    session.narrator,
                    session.characters,
                    session.llm,
                    k=session.k,
                    on_event=on_event,
                    finale=finale,
                )
            except Exception:  # LLM 超时 / 报错;细节进日志,不回传客户端
                logger.exception("回合生成失败")
                if produced == 0:
                    session.stage.round = round_before  # 整回合空转,不消耗轮数
                q.put(("error", "本回合生成失败,请稍后重试"))
            finally:
                q.put((sentinel, None))

        threading.Thread(target=worker, daemon=True).start()
        try:
            while True:
                kind, payload = q.get()
                if kind is sentinel:
                    break
                if kind == "event":
                    yield _sse({"kind": "event", "event": payload.to_dict()})
                else:
                    yield _sse({"kind": "error", "message": payload})
            yield _sse({"kind": "done", "round": session.stage.round})
        finally:
            session.lock.release()

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
        session.max_rounds = max(1, min(body.max_rounds, MAX_ROUNDS_CAP))
    # 用 model_fields_set 区分「没传 k」与「显式传 k=null(恢复全部历史)」
    if "k" in body.model_fields_set:
        session.k = body.k
    return {"max_rounds": session.max_rounds, "k": session.k}


@app.delete("/api/story/{session_id}")
def delete_story(session_id: str):
    _sessions.pop(session_id, None)
    return {"ok": True}


@app.post("/api/feedback")
def feedback(body: FeedbackIn, request: Request):
    if not _feedback_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="提交太频繁啦,歇一会儿再试~")
    text = body.text.strip()[:MAX_FIELD]
    if not text:
        raise HTTPException(status_code=400, detail="反馈内容不能为空")
    rec = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "text": text,
        "contact": (body.contact or "").strip()[:200],
    }
    path = Path("runs") / "feedback.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
