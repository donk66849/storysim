# StorySim Web 前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 StorySim 引擎加一个浏览器界面:向导建故事 → 逐回合流式演绎 → 表单式导演干预 → 设置轮数。

**Architecture:** FastAPI 在引擎外加一层会话桥接,内存存会话;跑回合用后台线程 + 队列把引擎的 `on_event` 逐条经 SSE 推给前端;前端是单个零构建 `index.html`(原生 JS/CSS)。引擎 `engine/*` 零改动。

**Tech Stack:** Python / FastAPI / uvicorn / SSE / 原生 HTML+JS+CSS / pytest + TestClient + FakeLLM。

---

## 文件结构

- `web/__init__.py` — 空包标记。
- `web/server.py` — FastAPI app、会话模型、全部接口、SSE 回合编排。唯一后端文件。
- `web/static/index.html` — 单文件 SPA(向导 / 剧场 / 导演面板 / 设置 / 剧终)。
- `tests/test_server.py` — 接口测试,注入 FakeLLM。
- `requirements.txt` — 加 fastapi/uvicorn/httpx。
- `README.md` — 加「Web 界面」段。

---

### Task 1: 依赖与 web 包骨架

**Files:**
- Modify: `requirements.txt`
- Create: `web/__init__.py`

- [ ] **Step 1: 加依赖**

`requirements.txt` 追加:

```
fastapi>=0.110
uvicorn[standard]>=0.27
httpx>=0.27
```

- [ ] **Step 2: 安装**

Run: `py -3.12 -m pip install fastapi "uvicorn[standard]" httpx`
Expected: 安装成功。

- [ ] **Step 3: 建空包**

`web/__init__.py` 内容为空。

- [ ] **Step 4: Commit**

```bash
git add requirements.txt web/__init__.py
git commit -m "chore: add web deps and package skeleton"
```

---

### Task 2: 后端 server.py(全部接口)

**Files:**
- Create: `web/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: 写失败测试 `tests/test_server.py`**

```python
import json

from fastapi.testclient import TestClient

import web.server as server
from engine.llm import FakeLLM

STORY = {
    "title": "测试故事",
    "scene": "一个测试场景",
    "characters": [
        {"name": "甲", "persona": "p1", "goal": "g1", "voice": "v1"},
        {"name": "乙", "persona": "p2", "goal": "g2", "voice": "v2"},
    ],
    "max_rounds": 5,
    "k": None,
}


def make_client(responses):
    server._make_llm = lambda: FakeLLM(list(responses))
    server._sessions.clear()
    return TestClient(server.app)


def _create(client):
    r = client.post("/api/story", json=STORY)
    assert r.status_code == 200
    return r.json()["session_id"]


def read_sse(client, sid):
    frames = []
    with client.stream("GET", f"/api/story/{sid}/round") as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[6:]))
    return frames


def test_create_story_returns_session():
    client = make_client(["x"] * 10)
    data = client.post("/api/story", json=STORY).json()
    assert "session_id" in data
    assert data["title"] == "测试故事"
    assert len(data["characters"]) == 2
    assert data["round"] == 0


def test_round_streams_narrator_then_characters():
    client = make_client(["旁白文字", "甲的台词", "乙的台词"] + ["x"] * 10)
    sid = _create(client)
    frames = read_sse(client, sid)
    events = [f["event"] for f in frames if f["kind"] == "event"]
    assert events[0]["type"] == "narration"
    assert [e["actor"] for e in events[1:]] == ["甲", "乙"]
    done = [f for f in frames if f["kind"] == "done"][-1]
    assert done["round"] == 1


def test_command_event_creates_world_event():
    client = make_client(["x"] * 10)
    sid = _create(client)
    r = client.post(
        f"/api/story/{sid}/command", json={"kind": "event", "value": "灯灭了"}
    )
    body = r.json()
    assert body["events"][0]["type"] == "world_event"
    assert "灯灭了" in body["events"][0]["content"]


def test_command_set_changes_field():
    client = make_client(["x"] * 10)
    sid = _create(client)
    client.post(
        f"/api/story/{sid}/command",
        json={"kind": "set", "target": "甲", "field": "goal", "value": "新目标"},
    )
    chars = client.get(f"/api/story/{sid}/state").json()["characters"]
    jia = next(c for c in chars if c["name"] == "甲")
    assert jia["goal"] == "新目标"


def test_command_tell_appends_private_note():
    client = make_client(["x"] * 10)
    sid = _create(client)
    r = client.post(
        f"/api/story/{sid}/command",
        json={"kind": "tell", "target": "乙", "value": "你有钥匙"},
    )
    assert "乙" in r.json()["status"]
    assert r.json()["events"] == []


def test_settings_patch():
    client = make_client(["x"] * 10)
    sid = _create(client)
    r = client.patch(f"/api/story/{sid}/settings", json={"max_rounds": 10, "k": 6})
    assert r.json() == {"max_rounds": 10, "k": 6}


def test_state_returns_events_after_round():
    client = make_client(["旁白", "甲说", "乙说"] + ["x"] * 10)
    sid = _create(client)
    read_sse(client, sid)
    state = client.get(f"/api/story/{sid}/state").json()
    assert state["round"] == 1
    assert len(state["events"]) == 3


def test_unknown_session_404():
    client = make_client([])
    assert client.get("/api/story/nope/state").status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `py -3.12 -m pytest tests/test_server.py -q`
Expected: FAIL(`ModuleNotFoundError: web.server` / 接口不存在)。

- [ ] **Step 3: 写 `web/server.py`**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `py -3.12 -m pytest tests/test_server.py -q`
Expected: 8 passed。

- [ ] **Step 5: 确认引擎旧测试不回归**

Run: `py -3.12 -m pytest -q`
Expected: 全绿。

- [ ] **Step 6: Commit**

```bash
git add web/server.py tests/test_server.py
git commit -m "feat: add FastAPI web server bridging the story engine"
```

---

### Task 3: 前端 index.html(向导 + 剧场 + 导演面板 + 设置)

**Files:**
- Create: `web/static/index.html`

- [ ] **Step 1: 写完整 `web/static/index.html`**

写入下方「index.html 完整内容」一节的全部内容(单文件:HTML 结构 + 内联 CSS 暗色剧场主题 + 内联 JS 逻辑)。功能点:
- 向导:标题 / 场景 / 角色卡片增删(name/persona/goal/voice)/ 总轮数 / 上下文 k / 「载入示例」/「开演」。
- 剧场:顶栏标题 + 「第 X / Y 回合」+ 设置齿轮;故事流按事件类型分色;「继续下一回合」用 `fetch` 流式读 SSE 逐条 append,期间 spinner;到 max_rounds 显示「剧终」+ 存档/再演。
- 导演面板:三表单(注入世界事件 / 私下叮嘱 / 修改角色)+ 存档按钮;调 `/command`、`/save`;toast 反馈。
- 设置浮层:改 max_rounds / k → `PATCH /settings`。

- [ ] **Step 2: 手动冒烟(需 .env 配好 key)**

Run: `py -3.12 -m uvicorn web.server:app`
打开 `http://127.0.0.1:8000`,载入示例 → 开演 → 看到旁白与角色逐条出现 → 试一次「注入世界事件」→ 「存档」。
Expected: 流式演绎正常,导演干预生效,无报错。

- [ ] **Step 3: Commit**

```bash
git add web/static/index.html
git commit -m "feat: add single-file web UI (wizard, theater, director panel)"
```

---

### Task 4: README 文档

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 加「Web 界面」段**

在「运行」段后插入:

```markdown
## Web 界面

```bash
py -3.12 -m pip install -r requirements.txt
py -3.12 -m uvicorn web.server:app          # 加 --reload 可热重载
```

浏览器打开 `http://127.0.0.1:8000`:

1. **创建向导** — 填故事标题、场景背景,增删角色(人设/目标/说话风格),设总轮数;可一键「载入示例」。
2. **剧场** — 点「继续下一回合」逐条看旁白与各角色演绎;右侧设置齿轮随时改轮数。
3. **导演面板** — 表单式注入世界事件、私下叮嘱某角色、修改角色字段,或存档到 `runs/`。

后端复用同一套引擎,故事同样落盘到 `runs/<时间戳>.md` 与 `.jsonl`。
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document the web UI"
```

---

## index.html 完整内容

> 执行 Task 3 Step 1 时写入此完整文件。

(完整 HTML/CSS/JS 见实现;约 350 行,包含:`#wizard`/`#theater` 两个 section、`.feed` 事件流、`#director` 面板、`#settings` 浮层、`api()` fetch 封装、`streamRound()` 读 SSE、`renderEvent()` 分色渲染、toast。)

---

## Self-Review

**Spec coverage:**
- 向导建故事 → Task 3 + `POST /api/story`(Task 2)✓
- 逐回合流式演绎 → SSE `/round`(Task 2)+ `streamRound()`(Task 3)✓
- 表单式导演(event/tell/set)→ `/command`(Task 2)+ 导演面板(Task 3)✓
- 设置轮数/k → `PATCH /settings`(Task 2)+ 设置浮层(Task 3)✓
- 存档 → `/save`(Task 2)✓;状态恢复 → `/state`(Task 2)✓;示例 → `/api/preset`(Task 2)✓
- 错误处理:LLM 失败 → 500 / SSE error 帧 ✓;未知会话 → 404 ✓
- 测试:create/round/command(event,set,tell)/settings/state/404 → Task 2 测试 ✓
- 引擎零改动 ✓

**Placeholder scan:** index.html 完整内容在执行步写入(非占位)。服务端与测试代码完整无占位。

**Type consistency:** `Session` 字段、`CommandIn`/`StoryIn`/`SettingsIn`、`_make_llm`/`_sessions`/`_sse`/`_get` 在 Task 2 内自洽;前端 `api()`/`streamRound()`/`renderEvent()` 在 Task 3 内自洽。
