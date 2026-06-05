# StorySim 剧情推演引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Python 命令行剧情推演引擎:数个有独立人设的角色 agent 自动一回合接一回合演出故事,使用者作为「导演」在回合之间注入事件、私聊角色、改角色状态。

**Architecture:** 路线 B「一个角色=一个 agent」。一个轻量 `Stage` 持有共享剧情记录(即「记忆」);`Narrator` 每回合开场描述氛围;每个 `Character` 按固定顺序调 LLM 产出台词并立刻写回 Stage(实现对戏);`Director` 解析并施加回合间干预。LLM 走依赖倒置(`LLMClient` 协议),真实实现走 DeepSeek(OpenAI 兼容),测试注入 `FakeLLM`,使所有确定性逻辑可单测。

**Tech Stack:** Python 3.12(`py -3.12`)、`openai`、`python-dotenv`、`pyyaml`、`rich`、`pytest`。无数据库、无多 agent 框架。

---

## 文件结构

```
storysim/
├── engine/
│   ├── __init__.py
│   ├── events.py        # Event 数据类(剧情记录最小单位)
│   ├── stage.py         # Stage:共享剧情记录 + 上下文拼装
│   ├── llm.py           # LLMClient 协议 + DeepSeekClient + FakeLLM + 工厂
│   ├── character.py     # Character agent:持人设,act() 产台词
│   ├── narrator.py      # Narrator agent:每回合开场描述氛围
│   ├── round_engine.py  # play_round():一回合编排(可单测)
│   ├── config.py        # StoryConfig + load_config()(读 YAML)
│   ├── director.py      # parse_command() + apply_command()
│   └── archive.py       # Archive:落盘 .md(可读)+ .jsonl(结构化)
├── config/
│   └── 雨夜古宅.yaml     # 示例故事配置
├── runs/                # 运行存档输出目录(.gitkeep)
├── tests/
│   ├── test_stage.py
│   ├── test_llm.py
│   ├── test_character.py
│   ├── test_narrator.py
│   ├── test_round_engine.py
│   ├── test_config.py
│   ├── test_director.py
│   └── test_archive.py
├── main.py              # 主循环(导演提示符)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

职责边界:`events.py` 只定义数据;`stage.py` 只管事件存取与文本拼装(纯逻辑);`llm.py` 隔离一切外部 API;agent 文件只负责 prompt 组装 + 调 LLM;`round_engine.py` 编排顺序;`director.py` 解析与施加干预;`archive.py` 只管落盘。`main.py` 仅做接线 + I/O,不放业务逻辑(便于其余全部单测)。

---

### Task 1: 项目脚手架

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `engine/__init__.py`
- Create: `tests/__init__.py`
- Create: `runs/.gitkeep`

- [ ] **Step 1: 写 `requirements.txt`**

```
openai>=1.0
python-dotenv>=1.0
pyyaml>=6.0
rich>=13.0
pytest>=8.0
```

- [ ] **Step 2: 写 `.env.example`**

```
LLM_API_KEY=your_deepseek_key_here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_NAME=deepseek-chat
```

- [ ] **Step 3: 写 `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
runs/*.md
runs/*.jsonl
```

- [ ] **Step 4: 建空包文件**

`engine/__init__.py` 内容:`# StorySim engine package`
`tests/__init__.py` 内容:空
`runs/.gitkeep` 内容:空

- [ ] **Step 5: 安装依赖**

Run: `py -3.12 -m pip install -r requirements.txt`
Expected: 成功安装(openai/pyyaml/rich 等),无报错。

- [ ] **Step 6: 验证 pytest 可运行**

Run: `py -3.12 -m pytest -q`
Expected: `no tests ran`(收集到 0 个测试,退出码 5),证明环境就绪。

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .env.example .gitignore engine/__init__.py tests/__init__.py runs/.gitkeep
git commit -m "chore: scaffold storysim project"
```

---

### Task 2: Event 数据类 + Stage

**Files:**
- Create: `engine/events.py`
- Create: `engine/stage.py`
- Test: `tests/test_stage.py`

- [ ] **Step 1: 写失败测试 `tests/test_stage.py`**

```python
from engine.events import Event
from engine.stage import Stage


def test_event_to_dict_keeps_field_order():
    e = Event(round=3, type="speech", actor="林探长", content="谁在那儿?")
    assert e.to_dict() == {
        "round": 3,
        "type": "speech",
        "actor": "林探长",
        "content": "谁在那儿?",
    }


def test_stage_starts_at_round_zero_with_scene():
    stage = Stage("三个陌生人被困古宅")
    assert stage.scene == "三个陌生人被困古宅"
    assert stage.round == 0
    assert stage.events == []


def test_start_round_increments_and_returns():
    stage = Stage("场景")
    assert stage.start_round() == 1
    assert stage.start_round() == 2
    assert stage.round == 2


def test_add_uses_current_round_and_returns_event():
    stage = Stage("场景")
    stage.start_round()
    e = stage.add("speech", "苏小姐", "我不知道")
    assert e.round == 1
    assert e.type == "speech"
    assert e.actor == "苏小姐"
    assert e.content == "我不知道"
    assert stage.events == [e]


def test_recent_returns_last_k_or_all():
    stage = Stage("场景")
    stage.start_round()
    for i in range(5):
        stage.add("speech", "A", str(i))
    assert [e.content for e in stage.recent(2)] == ["3", "4"]
    assert len(stage.recent()) == 5
    assert len(stage.recent(None)) == 5


def test_transcript_formats_each_type():
    stage = Stage("场景")
    stage.start_round()
    stage.add("narration", "旁白", "雨更大了")
    stage.add("speech", "林探长", "别动")
    stage.add("action", "苏小姐", "后退一步")
    stage.add("world_event", "世界", "灯全灭了")
    stage.add("director", "导演", "时间跳到午夜")
    text = stage.transcript()
    assert "〔雨更大了〕" in text
    assert "林探长:别动" in text
    assert "苏小姐(后退一步)" in text
    assert "【世界事件】灯全灭了" in text
    assert "【导演】时间跳到午夜" in text


def test_transcript_respects_k():
    stage = Stage("场景")
    stage.start_round()
    stage.add("speech", "A", "旧")
    stage.add("speech", "A", "新")
    assert "旧" not in stage.transcript(1)
    assert "新" in stage.transcript(1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `py -3.12 -m pytest tests/test_stage.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.events'`

- [ ] **Step 3: 写 `engine/events.py`**

```python
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
```

- [ ] **Step 4: 写 `engine/stage.py`**

```python
from engine.events import Event

_FORMATTERS = {
    "narration": lambda e: f"〔{e.content}〕",
    "speech": lambda e: f"{e.actor}:{e.content}",
    "action": lambda e: f"{e.actor}({e.content})",
    "world_event": lambda e: f"【世界事件】{e.content}",
    "director": lambda e: f"【导演】{e.content}",
}


def render_event(event: Event) -> str:
    fmt = _FORMATTERS.get(event.type, lambda e: f"{e.actor}:{e.content}")
    return fmt(event)


class Stage:
    """共享剧情记录 + 上下文拼装。这串事件即「记忆」。"""

    def __init__(self, scene: str):
        self.scene = scene
        self.events: list[Event] = []
        self.round = 0

    def start_round(self) -> int:
        self.round += 1
        return self.round

    def add(self, type: str, actor: str, content: str) -> Event:
        event = Event(round=self.round, type=type, actor=actor, content=content)
        self.events.append(event)
        return event

    def recent(self, k: int | None = None) -> list[Event]:
        if k is None:
            return list(self.events)
        return self.events[-k:]

    def transcript(self, k: int | None = None) -> str:
        return "\n".join(render_event(e) for e in self.recent(k))
```

- [ ] **Step 5: 运行测试确认通过**

Run: `py -3.12 -m pytest tests/test_stage.py -q`
Expected: PASS(7 passed)

- [ ] **Step 6: Commit**

```bash
git add engine/events.py engine/stage.py tests/test_stage.py
git commit -m "feat: add Event and Stage with transcript rendering"
```

---

### Task 3: LLM 抽象(协议 + FakeLLM + DeepSeekClient + 工厂)

**Files:**
- Create: `engine/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: 写失败测试 `tests/test_llm.py`**

```python
from types import SimpleNamespace

import pytest

from engine.llm import FakeLLM, DeepSeekClient, make_llm_from_env


def test_fake_llm_returns_scripted_responses_in_order():
    llm = FakeLLM(["第一句", "第二句"])
    assert llm.complete([{"role": "user", "content": "a"}]) == "第一句"
    assert llm.complete([{"role": "user", "content": "b"}]) == "第二句"


def test_fake_llm_records_calls():
    llm = FakeLLM(["x"])
    msgs = [{"role": "user", "content": "hi"}]
    llm.complete(msgs)
    assert llm.calls == [msgs]


def test_fake_llm_raises_when_exhausted():
    llm = FakeLLM([])
    with pytest.raises(IndexError):
        llm.complete([{"role": "user", "content": "a"}])


def test_deepseek_client_calls_underlying_client():
    captured = {}

    def fake_create(model, messages):
        captured["model"] = model
        captured["messages"] = messages
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="回答"))]
        )

    fake_openai = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))
    )
    client = DeepSeekClient(fake_openai, "deepseek-chat")
    out = client.complete([{"role": "user", "content": "问"}])
    assert out == "回答"
    assert captured["model"] == "deepseek-chat"
    assert captured["messages"] == [{"role": "user", "content": "问"}]


def test_make_llm_from_env_reads_config(monkeypatch):
    created = {}

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            created["api_key"] = api_key
            created["base_url"] = base_url

    import engine.llm as llm_mod
    monkeypatch.setattr(llm_mod, "OpenAI", FakeOpenAI)

    env = {
        "LLM_API_KEY": "k1",
        "LLM_BASE_URL": "https://api.deepseek.com/v1",
        "LLM_MODEL_NAME": "deepseek-chat",
    }
    client = make_llm_from_env(env)
    assert created["api_key"] == "k1"
    assert created["base_url"] == "https://api.deepseek.com/v1"
    assert client.model == "deepseek-chat"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `py -3.12 -m pytest tests/test_llm.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.llm'`

- [ ] **Step 3: 写 `engine/llm.py`**

```python
from typing import Protocol

try:  # 真实依赖;测试通过 monkeypatch 替换,故容忍缺失
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


class FakeLLM:
    """测试用:按脚本顺序返回响应,并记录每次调用的 messages。"""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self._responses.pop(0)


class DeepSeekClient:
    """DeepSeek(OpenAI 兼容)的薄封装。client 由外部注入,便于测试。"""

    def __init__(self, client, model: str):
        self._client = client
        self.model = model

    def complete(self, messages: list[dict[str, str]]) -> str:
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages
        )
        return resp.choices[0].message.content


def make_llm_from_env(env: dict | None = None) -> DeepSeekClient:
    import os

    env = env if env is not None else os.environ
    client = OpenAI(api_key=env["LLM_API_KEY"], base_url=env["LLM_BASE_URL"])
    return DeepSeekClient(client, env["LLM_MODEL_NAME"])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `py -3.12 -m pytest tests/test_llm.py -q`
Expected: PASS(5 passed)

- [ ] **Step 5: Commit**

```bash
git add engine/llm.py tests/test_llm.py
git commit -m "feat: add injectable LLM client with DeepSeek impl and FakeLLM"
```

---

### Task 4: Character agent

**Files:**
- Create: `engine/character.py`
- Test: `tests/test_character.py`

- [ ] **Step 1: 写失败测试 `tests/test_character.py`**

```python
from engine.character import Character
from engine.stage import Stage
from engine.llm import FakeLLM


def make_char(**kw):
    defaults = dict(
        name="林探长",
        persona="退休侦探,多疑、逻辑强",
        goal="查清古宅里发生过什么",
        voice="冷静,爱用反问",
    )
    defaults.update(kw)
    return Character(**defaults)


def test_system_prompt_contains_persona_fields():
    ch = make_char()
    sp = ch.system_prompt()
    assert "林探长" in sp
    assert "退休侦探" in sp
    assert "查清古宅里发生过什么" in sp
    assert "冷静,爱用反问" in sp


def test_system_prompt_includes_private_notes():
    ch = make_char(private_notes=["你其实早就认识苏小姐"])
    assert "你其实早就认识苏小姐" in ch.system_prompt()


def test_act_calls_llm_and_writes_speech_to_stage():
    stage = Stage("古宅大厅")
    stage.start_round()
    ch = make_char()
    llm = FakeLLM(["谁在那儿?"])
    event = ch.act(stage, llm)
    assert event.type == "speech"
    assert event.actor == "林探长"
    assert event.content == "谁在那儿?"
    assert stage.events[-1] is event


def test_act_messages_carry_scene_and_recent_transcript():
    stage = Stage("古宅大厅")
    stage.start_round()
    stage.add("speech", "苏小姐", "我先到的")
    ch = make_char()
    llm = FakeLLM(["你几点到的?"])
    ch.act(stage, llm)
    messages = llm.calls[0]
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    user = messages[-1]["content"]
    assert "古宅大厅" in user
    assert "苏小姐:我先到的" in user
```

- [ ] **Step 2: 运行测试确认失败**

Run: `py -3.12 -m pytest tests/test_character.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.character'`

- [ ] **Step 3: 写 `engine/character.py`**

```python
from dataclasses import dataclass, field

from engine.events import Event
from engine.llm import LLMClient
from engine.stage import Stage


@dataclass
class Character:
    name: str
    persona: str
    goal: str
    voice: str
    private_notes: list[str] = field(default_factory=list)

    def system_prompt(self) -> str:
        parts = [
            f"你是「{self.name}」。",
            f"人设:{self.persona}",
            f"目标:{self.goal}",
            f"说话风格:{self.voice}",
            "你正在出演一部互动剧。始终保持角色,不要跳出,不要替别的角色说话。",
        ]
        if self.private_notes:
            parts.append("\n[导演私下叮嘱(只有你知道)]")
            parts.extend(f"- {note}" for note in self.private_notes)
        return "\n".join(parts)

    def _user_prompt(self, stage: Stage, k: int | None) -> str:
        return (
            f"当前场景:{stage.scene}\n\n"
            f"已发生的剧情:\n{stage.transcript(k)}\n\n"
            f"（轮到你了。以「{self.name}」的身份说一句台词或做一个动作，"
            f"只输出你自己的内容，简短自然。）"
        )

    def act(self, stage: Stage, llm: LLMClient, k: int | None = None) -> Event:
        messages = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": self._user_prompt(stage, k)},
        ]
        content = llm.complete(messages).strip()
        return stage.add("speech", self.name, content)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `py -3.12 -m pytest tests/test_character.py -q`
Expected: PASS(4 passed)

- [ ] **Step 5: Commit**

```bash
git add engine/character.py tests/test_character.py
git commit -m "feat: add Character agent that acts via LLM and writes to Stage"
```

---

### Task 5: Narrator agent

**Files:**
- Create: `engine/narrator.py`
- Test: `tests/test_narrator.py`

- [ ] **Step 1: 写失败测试 `tests/test_narrator.py`**

```python
from engine.narrator import Narrator
from engine.stage import Stage
from engine.llm import FakeLLM


def test_narrate_writes_narration_event():
    stage = Stage("暴雨中的古宅")
    stage.start_round()
    llm = FakeLLM(["闪电划过,照亮空荡的大厅。"])
    event = Narrator().narrate(stage, llm)
    assert event.type == "narration"
    assert event.actor == "旁白"
    assert event.content == "闪电划过,照亮空荡的大厅。"
    assert stage.events[-1] is event


def test_narrate_prompt_includes_scene_and_history():
    stage = Stage("暴雨中的古宅")
    stage.start_round()
    stage.add("speech", "林探长", "门被锁死了")
    llm = FakeLLM(["雨声盖过了呼吸。"])
    Narrator().narrate(stage, llm)
    user = llm.calls[0][-1]["content"]
    assert "暴雨中的古宅" in user
    assert "林探长:门被锁死了" in user
```

- [ ] **Step 2: 运行测试确认失败**

Run: `py -3.12 -m pytest tests/test_narrator.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.narrator'`

- [ ] **Step 3: 写 `engine/narrator.py`**

```python
from engine.events import Event
from engine.llm import LLMClient
from engine.stage import Stage

_SYSTEM = (
    "你是这部互动剧的旁白。用简洁、有画面感的语言描述本回合开场的场景与氛围,"
    "2-3 句即可。只描写环境与气氛,不替任何角色说话或行动。"
)


class Narrator:
    def narrate(self, stage: Stage, llm: LLMClient, k: int | None = None) -> Event:
        user = (
            f"场景设定:{stage.scene}\n\n"
            f"已发生的剧情:\n{stage.transcript(k)}\n\n"
            f"请描写本回合的开场氛围。"
        )
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ]
        content = llm.complete(messages).strip()
        return stage.add("narration", "旁白", content)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `py -3.12 -m pytest tests/test_narrator.py -q`
Expected: PASS(2 passed)

- [ ] **Step 5: Commit**

```bash
git add engine/narrator.py tests/test_narrator.py
git commit -m "feat: add Narrator agent for per-round scene-setting"
```

---

### Task 6: 一回合编排 play_round

**Files:**
- Create: `engine/round_engine.py`
- Test: `tests/test_round_engine.py`

- [ ] **Step 1: 写失败测试 `tests/test_round_engine.py`**

```python
from engine.round_engine import play_round
from engine.stage import Stage
from engine.narrator import Narrator
from engine.character import Character
from engine.llm import FakeLLM


def make_chars():
    a = Character("甲", "人设甲", "目标甲", "风格甲")
    b = Character("乙", "人设乙", "目标乙", "风格乙")
    return [a, b]


def test_play_round_order_is_narrator_then_characters():
    stage = Stage("场景")
    chars = make_chars()
    llm = FakeLLM(["旁白词", "甲的台词", "乙的台词"])
    produced = play_round(stage, Narrator(), chars, llm)
    assert [(e.type, e.actor) for e in produced] == [
        ("narration", "旁白"),
        ("speech", "甲"),
        ("speech", "乙"),
    ]
    assert stage.round == 1


def test_later_character_sees_earlier_character_within_same_round():
    stage = Stage("场景")
    chars = make_chars()
    llm = FakeLLM(["旁白词", "甲的台词", "乙的台词"])
    play_round(stage, Narrator(), chars, llm)
    # 第三次调用是「乙」,其 user prompt 应包含「甲」刚说的话
    yi_user = llm.calls[2][-1]["content"]
    assert "甲:甲的台词" in yi_user


def test_play_round_advances_round_number_each_call():
    stage = Stage("场景")
    chars = make_chars()
    llm = FakeLLM(["n1", "a1", "b1", "n2", "a2", "b2"])
    play_round(stage, Narrator(), chars, llm)
    play_round(stage, Narrator(), chars, llm)
    assert stage.round == 2
    assert stage.events[-1].round == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `py -3.12 -m pytest tests/test_round_engine.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.round_engine'`

- [ ] **Step 3: 写 `engine/round_engine.py`**

```python
from engine.character import Character
from engine.events import Event
from engine.llm import LLMClient
from engine.narrator import Narrator
from engine.stage import Stage


def play_round(
    stage: Stage,
    narrator: Narrator,
    characters: list[Character],
    llm: LLMClient,
    k: int | None = None,
) -> list[Event]:
    """跑完一整回合:旁白开场,然后每个角色按固定顺序行动。
    角色台词立刻写回 Stage,故同回合后面的角色能看到前面的(对戏)。"""
    stage.start_round()
    produced: list[Event] = [narrator.narrate(stage, llm, k)]
    for ch in characters:
        produced.append(ch.act(stage, llm, k))
    return produced
```

- [ ] **Step 4: 运行测试确认通过**

Run: `py -3.12 -m pytest tests/test_round_engine.py -q`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add engine/round_engine.py tests/test_round_engine.py
git commit -m "feat: add play_round orchestration with in-round visibility"
```

---

### Task 7: 故事配置加载(YAML)

**Files:**
- Create: `engine/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试 `tests/test_config.py`**

```python
from engine.config import load_config, StoryConfig
from engine.character import Character


YAML_TEXT = """\
title: 雨夜古宅
scene: 三个陌生人被暴雨困在断电的古宅里,大门反锁。
max_rounds: 12
characters:
  - name: 林探长
    persona: 退休侦探,多疑
    goal: 查清真相
    voice: 冷静爱反问
  - name: 苏小姐
    persona: 神秘访客
    goal: 隐藏秘密
    voice: 温柔含糊
"""


def test_load_config_parses_top_level_fields(tmp_path):
    p = tmp_path / "story.yaml"
    p.write_text(YAML_TEXT, encoding="utf-8")
    cfg = load_config(p)
    assert isinstance(cfg, StoryConfig)
    assert cfg.title == "雨夜古宅"
    assert cfg.scene.startswith("三个陌生人")
    assert cfg.max_rounds == 12


def test_load_config_builds_characters(tmp_path):
    p = tmp_path / "story.yaml"
    p.write_text(YAML_TEXT, encoding="utf-8")
    cfg = load_config(p)
    assert len(cfg.characters) == 2
    first = cfg.characters[0]
    assert isinstance(first, Character)
    assert first.name == "林探长"
    assert first.goal == "查清真相"
    assert first.private_notes == []


def test_load_config_defaults_max_rounds_when_missing(tmp_path):
    p = tmp_path / "story.yaml"
    p.write_text(
        "title: t\nscene: s\ncharacters:\n  - name: A\n    persona: p\n"
        "    goal: g\n    voice: v\n",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.max_rounds == 20
```

- [ ] **Step 2: 运行测试确认失败**

Run: `py -3.12 -m pytest tests/test_config.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.config'`

- [ ] **Step 3: 写 `engine/config.py`**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `py -3.12 -m pytest tests/test_config.py -q`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add engine/config.py tests/test_config.py
git commit -m "feat: load story config from YAML into StoryConfig"
```

---

### Task 8: 导演命令解析 parse_command

**Files:**
- Create: `engine/director.py`
- Test: `tests/test_director.py`(本任务先建文件,只测 parse)

- [ ] **Step 1: 写失败测试 `tests/test_director.py`**

```python
from engine.director import parse_command, DirectorCommand


def test_blank_means_continue():
    assert parse_command("").kind == "continue"
    assert parse_command("   ").kind == "continue"


def test_event_command():
    cmd = parse_command("event: 灯突然全灭了")
    assert cmd.kind == "event"
    assert cmd.value == "灯突然全灭了"


def test_tell_command():
    cmd = parse_command("tell 苏小姐: 你藏着一把钥匙")
    assert cmd.kind == "tell"
    assert cmd.target == "苏小姐"
    assert cmd.value == "你藏着一把钥匙"


def test_set_command():
    cmd = parse_command("set 苏小姐 goal=隐瞒真相")
    assert cmd.kind == "set"
    assert cmd.target == "苏小姐"
    assert cmd.field == "goal"
    assert cmd.value == "隐瞒真相"


def test_save_and_quit():
    assert parse_command("save").kind == "save"
    assert parse_command("quit").kind == "quit"


def test_unknown_command():
    assert parse_command("blah blah").kind == "unknown"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `py -3.12 -m pytest tests/test_director.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.director'`

- [ ] **Step 3: 写 `engine/director.py`(先只到 parse_command)**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `py -3.12 -m pytest tests/test_director.py -q`
Expected: PASS(7 passed)

- [ ] **Step 5: Commit**

```bash
git add engine/director.py tests/test_director.py
git commit -m "feat: parse director commands (event/tell/set/save/quit)"
```

---

### Task 9: 导演干预施加 apply_command

**Files:**
- Modify: `engine/director.py`(追加 `apply_command`)
- Modify: `tests/test_director.py`(追加测试)

- [ ] **Step 1: 追加失败测试到 `tests/test_director.py`**

```python
from engine.director import apply_command
from engine.stage import Stage
from engine.character import Character


def make_stage_and_chars():
    stage = Stage("场景")
    stage.start_round()
    chars = {
        "苏小姐": Character("苏小姐", "p", "原目标", "v"),
        "林探长": Character("林探长", "p", "g", "v"),
    }
    return stage, chars


def test_apply_event_adds_world_event_and_returns_it():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("event: 灯全灭了")
    status, events = apply_command(cmd, stage, chars)
    assert len(events) == 1
    assert events[0].type == "world_event"
    assert events[0].actor == "世界"
    assert events[0].content == "灯全灭了"
    assert stage.events[-1] is events[0]
    assert "灯全灭了" in status


def test_apply_tell_appends_private_note_only():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("tell 苏小姐: 你有钥匙")
    status, events = apply_command(cmd, stage, chars)
    assert chars["苏小姐"].private_notes == ["你有钥匙"]
    assert events == []  # 私聊不进公共剧情记录
    assert "苏小姐" in status


def test_apply_set_changes_field():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("set 苏小姐 goal=隐瞒真相")
    status, events = apply_command(cmd, stage, chars)
    assert chars["苏小姐"].goal == "隐瞒真相"
    assert events == []
    assert "goal" in status


def test_apply_unknown_character_returns_error():
    stage, chars = make_stage_and_chars()
    cmd = parse_command("tell 张三: 你好")
    status, events = apply_command(cmd, stage, chars)
    assert events == []
    assert "张三" in status
```

- [ ] **Step 2: 运行测试确认失败**

Run: `py -3.12 -m pytest tests/test_director.py -q`
Expected: FAIL —— `ImportError: cannot import name 'apply_command'`

- [ ] **Step 3: 在 `engine/director.py` 末尾追加 `apply_command`**

```python
from engine.events import Event
from engine.stage import Stage
from engine.character import Character


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

    return "无法识别的命令", []
```

注意:`from engine.character import Character` 等 import 放到文件顶部已有 import 区(避免重复导入);此处展示为追加内容,执行时把这三行 import 合并到文件头部。

- [ ] **Step 4: 运行测试确认通过**

Run: `py -3.12 -m pytest tests/test_director.py -q`
Expected: PASS(11 passed)

- [ ] **Step 5: Commit**

```bash
git add engine/director.py tests/test_director.py
git commit -m "feat: apply director interventions (event/tell/set)"
```

---

### Task 10: 存档 Archive(.md + .jsonl)

**Files:**
- Create: `engine/archive.py`
- Test: `tests/test_archive.py`

- [ ] **Step 1: 写失败测试 `tests/test_archive.py`**

```python
import json
from datetime import datetime

from engine.archive import Archive
from engine.stage import Stage


def build_stage():
    stage = Stage("暴雨古宅")
    stage.start_round()
    stage.add("narration", "旁白", "雷声轰鸣")
    stage.add("speech", "林探长", "都别动")
    stage.start_round()
    stage.add("speech", "苏小姐", "我害怕")
    return stage


def test_archive_paths_use_timestamp(tmp_path):
    fixed = datetime(2026, 6, 5, 14, 30, 0)
    arc = Archive(tmp_path, "暴雨古宅", now=fixed)
    assert arc.md_path.name == "20260605-143000.md"
    assert arc.jsonl_path.name == "20260605-143000.jsonl"


def test_log_appends_jsonl_lines(tmp_path):
    stage = build_stage()
    arc = Archive(tmp_path, "暴雨古宅", now=datetime(2026, 6, 5, 14, 30, 0))
    for e in stage.events:
        arc.log(e)
    lines = arc.jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    first = json.loads(lines[0])
    assert first == {
        "round": 1,
        "type": "narration",
        "actor": "旁白",
        "content": "雷声轰鸣",
    }


def test_write_markdown_is_readable(tmp_path):
    stage = build_stage()
    arc = Archive(tmp_path, "暴雨古宅", now=datetime(2026, 6, 5, 14, 30, 0))
    arc.write_markdown(stage)
    md = arc.md_path.read_text(encoding="utf-8")
    assert "# 暴雨古宅" in md
    assert "暴雨古宅" in md
    assert "## 第 1 回合" in md
    assert "## 第 2 回合" in md
    assert "林探长:都别动" in md
    assert "〔雷声轰鸣〕" in md
```

- [ ] **Step 2: 运行测试确认失败**

Run: `py -3.12 -m pytest tests/test_archive.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.archive'`

- [ ] **Step 3: 写 `engine/archive.py`**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `py -3.12 -m pytest tests/test_archive.py -q`
Expected: PASS(3 passed)

- [ ] **Step 5: 全量回归**

Run: `py -3.12 -m pytest -q`
Expected: PASS(全部测试通过,约 35 个)

- [ ] **Step 6: Commit**

```bash
git add engine/archive.py tests/test_archive.py
git commit -m "feat: add Archive writing jsonl event stream and readable markdown"
```

---

### Task 11: 主循环 main.py + 示例故事

**Files:**
- Create: `config/雨夜古宅.yaml`
- Create: `main.py`

- [ ] **Step 1: 写示例故事 `config/雨夜古宅.yaml`**

```yaml
title: 雨夜古宅
scene: 三个陌生人被暴雨困在一座断电的古宅里,大门反锁,只有烛光摇曳。
max_rounds: 10
characters:
  - name: 林探长
    persona: 退休侦探,多疑、逻辑强,直觉这不是意外
    goal: 查清古宅里发生过什么
    voice: 冷静,爱用反问
  - name: 苏小姐
    persona: 衣着考究的年轻女子,神色慌张,似乎在隐藏什么
    goal: 不让别人发现自己来这里的真正目的
    voice: 温柔但闪烁其词
  - name: 老周
    persona: 古宅看门人,沉默寡言,知道许多旧事
    goal: 守住宅子的秘密,但又忍不住暗示
    voice: 缓慢,半截话不说完
```

- [ ] **Step 2: 写 `main.py`**

```python
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

    while stage.round < cfg.max_rounds:
        for event in play_round(stage, narrator, cfg.characters, llm):
            print_event(event)
            archive.log(event)

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
```

- [ ] **Step 3: 语法/导入冒烟检查(不调真实 LLM)**

Run: `py -3.12 -c "import main; print('import ok')"`
Expected: 输出 `import ok`(确认所有 import 与语法正确)

- [ ] **Step 4: 全量回归仍通过**

Run: `py -3.12 -m pytest -q`
Expected: PASS(全部通过)

- [ ] **Step 5: Commit**

```bash
git add config/雨夜古宅.yaml main.py
git commit -m "feat: add main loop with director prompt and example story"
```

---

### Task 12: README + 真实联调说明

**Files:**
- Create: `README.md`

- [ ] **Step 1: 写 `README.md`**

````markdown
# StorySim 剧情推演引擎

几个有独立人设的角色自动一回合接一回合把故事演出来;你作为「导演 / 上帝视角」,
在回合之间注入事件、私下给角色塞设定、修改角色状态,把剧情掰向你想看的方向。

## 安装

```bash
py -3.12 -m pip install -r requirements.txt
cp .env.example .env   # 填入你的 DeepSeek key
```

`.env`:

```
LLM_API_KEY=<deepseek_key>
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_NAME=deepseek-chat
```

## 运行

```bash
py -3.12 main.py                      # 跑默认故事 config/雨夜古宅.yaml
py -3.12 main.py config/你的故事.yaml  # 跑自定义故事
```

每回合结束弹出 `导演>` 提示符:

| 输入 | 作用 |
| --- | --- |
| 回车 | 继续下一回合 |
| `event: 灯突然全灭了` | 注入世界事件 |
| `tell 苏小姐: 你藏着一把钥匙` | 私下给某角色塞设定(只进其私有记忆) |
| `set 苏小姐 goal=隐瞒真相` | 修改某角色字段(goal/persona/voice) |
| `save` | 立即存档 |
| `quit` | 结束 |

## 输出

- 终端实时彩色播放。
- `runs/<时间戳>.md`:像小说一样可读的故事。
- `runs/<时间戳>.jsonl`:结构化事件流,便于回放 / 分析。

## 写自己的故事

复制 `config/雨夜古宅.yaml`,改 `title` / `scene` / `characters`(每个角色含
`name` / `persona` / `goal` / `voice`)/ `max_rounds` 即可。

## 测试

```bash
py -3.12 -m pytest -q
```

所有确定性逻辑(Stage、上下文拼装、导演命令、回合编排、存档)均通过注入 `FakeLLM`
单测,不依赖真实 LLM。
````

- [ ] **Step 2: 真实联调(需有效 .env,手动一次)**

Run: `py -3.12 main.py`
Expected: 旁白先开场,三个角色依次说话;`导演>` 处回车继续,`quit` 结束;
`runs/` 下生成 `.md` 与 `.jsonl`,内容与终端一致。
(此步依赖真实 DeepSeek key,作为人工验收;CI/自动执行可跳过。)

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with usage and director commands"
```

---

## 备注

- **上下文窗口策略(spec §6):** 首版无脑喂全部历史 —— 全程 `k=None`(`transcript()` 默认即全量)。
  摘要逻辑 YAGNI,等真跑长后再加;`recent(k)` / `transcript(k)` 已预留 K 参数,届时改 `main.py`
  传一个 K 即可,无需改 agent。
- **未做(spec §10,本期明确不做):** 历史摘要 / 记忆压缩、动态行动顺序、Web 界面、中途增删角色。
- **角色 act 只产 "speech":** spec §4.2 列了 speech/action 两种,首版统一产 "speech"(可含动作描述),
  保持简单;`action` 类型已被 `transcript` / `render_event` 支持,导演或后续扩展可产出。
