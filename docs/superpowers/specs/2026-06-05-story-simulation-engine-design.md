# 剧情推演引擎(StorySim)设计文档

- 日期:2026-06-05
- 状态:已通过头脑风暴评审,待实现
- LLM:DeepSeek(OpenAI 兼容接口)

## 1. 目标

一个 Python 命令行的**剧情推演引擎**:几个有独立人设的角色,自动一回合接一回合地把故事演出来;
使用者作为「导演 / 上帝视角」,可以在回合之间注入事件、私下给角色塞设定、修改角色状态,
把剧情掰向自己想看的方向。先做命令行 / 脚本版,验证玩法,之后再考虑加界面。

非目标(明确不做):
- 不做大规模群体(成千上万 agent)。角色是少量的(典型 2~6 个)。
- 不上向量库 / 记忆图谱(Zep 等)。「记忆」就是共享剧情记录本身。
- 不用多 agent 框架(CrewAI / AutoGen / LangGraph)。手写轻量编排。

## 2. 总体方案

**路线 B:一个角色 = 一个 agent。** 每个角色拥有自己的 system prompt(人设)与自己的视角,
每回合各自生成台词 / 动作;一个轻量的「舞台(Stage)」对象保存共享剧情记录。
导演的干预 = 在回合之间往舞台里插入事件 / 修改角色。
增加一个「旁白(Narrator)」agent,在每回合开头描述场景氛围。

## 3. 模块划分

```
storysim/
├── config/             # 故事配置(编剧的地方)
│   └── 雨夜古宅.yaml
├── engine/
│   ├── llm.py          # DeepSeek 调用封装(读 .env),可注入 / 可 mock
│   ├── character.py    # 角色 agent:持有人设,act() 产出台词 / 动作
│   ├── narrator.py     # 旁白 agent:每回合开头描述场景氛围
│   ├── stage.py        # 舞台:共享剧情记录 + 上下文拼装
│   └── director.py     # 回合间接收导演命令并施加干预
├── runs/               # 每次运行存档(.md 可读 + .jsonl 结构化)
├── main.py             # 主循环
└── .env                # DeepSeek key
```

依赖:`openai`、`python-dotenv`、`pyyaml`,外加 `rich`(终端彩色输出,可选)。
**无数据库、无多 agent 框架。** Python 3.11+。

## 4. 数据结构

### 4.1 故事配置(YAML)

```yaml
title: 雨夜古宅
scene: 三个陌生人被暴雨困在一座断电的古宅里,大门反锁。
max_rounds: 20
characters:
  - name: 林探长
    persona: 退休侦探,多疑、逻辑强,直觉这不是意外
    goal: 查清古宅里发生过什么
    voice: 冷静,爱用反问
  - name: 苏小姐
    persona: ...
    goal: ...
    voice: ...
```

### 4.2 事件(剧情记录的最小单位)

存放在 Stage 中的共享列表里,**这串事件即「记忆」**:

```python
{
  "round": 3,
  "type": "narration | speech | action | world_event | director",
  "actor": "林探长",     # narration / world_event 时可为 "旁白" / "世界"
  "content": "..."
}
```

### 4.3 角色私有上下文

角色之间主要共享同一份公共剧情记录。唯一「私有」的是导演通过 `tell` 私下塞入的设定,
以一个简短的 private notes 列表附加进该角色的 prompt。

## 5. 一回合的流程

1. **旁白**:Narrator 根据当前剧情描述本回合开场的场景 / 氛围 → 记一条 `narration` 事件。
2. **每个角色按固定顺序依次行动**:
   - 拼上下文 = 全局场景 + 自己的人设(persona / goal / voice) + 最近 K 条剧情 + 自己的 private notes
   - 调 DeepSeek → 输出本回合台词 / 动作
   - **立刻写回 Stage**,使同回合后面的角色能看到前面角色刚说的话(实现「对戏」)
3. **回合结束 → 弹出导演提示符**,使用者可输入:
   - `回车` —— 继续下一回合
   - `event: <文本>` —— 注入世界事件(如 `event: 灯突然全灭了`),记为 `world_event`
   - `tell <角色>: <文本>` —— 私下给某角色塞设定,只进该角色 private notes
   - `set <角色> <字段>=<值>` —— 修改某角色状态 / 目标(如 `set 苏小姐 goal=隐瞒真相`)
   - `save` —— 立即存档
   - `quit` —— 结束
4. 循环直到 `max_rounds` 或使用者 `quit`。

## 6. 上下文窗口策略

先无脑把全部历史喂回每个角色;当历史长到阈值,再改为「只喂最近 K 条 + 一句旧情摘要」。
**首版不实现摘要逻辑**,等真正跑长后再加(YAGNI)。

## 7. 输出与存档

- 终端实时彩色打印(角色名 + 台词;旁白与世界事件用不同样式)。
- 落盘 `runs/<时间戳>.md`:像小说一样可读的故事文本。
- 落盘 `runs/<时间戳>.jsonl`:结构化事件流,便于以后回放 / 分析。

## 8. 可测试性

`llm.py` 设计为可注入(依赖倒置):真实实现走 DeepSeek,测试时注入假 LLM。
这样 Stage(事件记录、上下文拼装)、director 命令解析、回合编排等**确定性逻辑均可单测**,
不依赖真实 LLM 调用。

## 9. LLM 接入

复用 OpenAI 兼容接口,配置来自 `.env`:

```
LLM_API_KEY=<deepseek_key>
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_NAME=deepseek-chat
```

## 10. 后续可扩展(本期不做)

- 长剧情的历史摘要 / 记忆压缩。
- 角色行动顺序由旁白 / 导演动态决定,而非固定顺序。
- Web 界面(对话气泡、时间线、按钮注入事件)。
- 中途增删角色。
