# StorySim Web 前端 — 设计文档

日期:2026-06-05

## 目标

给现有的 StorySim 剧情推演引擎(纯 Python CLI)加一个浏览器界面,让用户能够:

1. 通过向导创建故事:标题、场景背景、若干角色(name/persona/goal/voice)。
2. 在「剧场」里逐回合演绎,逐条看到旁白与各角色台词流式冒出。
3. 用导演面板(表单/按钮,非命令语法)注入世界事件、私下叮嘱角色、修改角色字段、存档。
4. 在设置里调整轮数(max_rounds)与上下文窗口(k)。

约束:**引擎代码(`engine/*`)零改动**,只在其外加一层 Web 桥接。界面全中文,沉浸式暗色剧场风。前端单文件零构建(原生 HTML/JS/CSS,无 npm/打包)。

## 架构

两层,引擎复用不动:

```
浏览器 (web/static/index.html, 原生 JS/CSS)
        │  HTTP + SSE
web/server.py (FastAPI)
        │  持有内存会话:{ Stage, 角色 map, Narrator, LLM, Archive, k, max_rounds }
        └──────────> 复用现有 engine/*(load_config 之外的逻辑全部复用)
```

引擎是同步阻塞的(每次 `llm.complete` 阻塞)。「跑一回合」用 **后台线程 + 线程安全队列**:在线程里调用 `play_round(..., on_event=push)`,`push` 把每条 `Event` 放进 `queue.Queue`;SSE 生成器在主请求里阻塞地从队列取事件、逐条 `yield` 给前端,取到哨兵值(回合结束)后关闭流。这样既复用引擎的 `on_event` 逐条回调,又把阻塞的 LLM 调用挪出事件循环。

## 后端接口(web/server.py)

会话存在进程内 `dict[str, Session]`,key 为 `session_id`(用 `uuid4` 生成)。本地单人工具,无需持久化会话。

| 方法 | 路径 | 请求体 | 响应 |
| --- | --- | --- | --- |
| `GET` | `/` | — | 返回 `index.html` |
| `POST` | `/api/story` | `{title, scene, characters:[{name,persona,goal,voice}], max_rounds, k}` | `{session_id, title, scene, characters, round, max_rounds, k}` |
| `GET` | `/api/story/{id}/round` (SSE) | — | 逐条 `event` 帧;遇错推 `error` 帧;回合结束推 `done` 帧(含新 round 值) |
| `POST` | `/api/story/{id}/command` | `{kind, target?, field?, value?}` | `{status, events:[...]}`(events 为新增公共事件,如 world_event) |
| `POST` | `/api/story/{id}/save` | — | `{md_path, jsonl_path}` |
| `GET` | `/api/story/{id}/state` | — | `{title, scene, characters, round, max_rounds, k, events:[...]}` |
| `PATCH` | `/api/story/{id}/settings` | `{max_rounds?, k?}` | 更新后的 `{max_rounds, k}` |

事件序列化:复用 `Event.to_dict()`(round/type/actor/content)。

SSE 帧格式:`data: {json}\n\n`,json 含 `{kind: "event"|"error"|"done", ...}`。`event` 帧带 `event` 字段(`to_dict()`);`error` 帧带 `message`;`done` 帧带 `round`。

### 导演命令映射

前端表单 → `POST /command` 的 `{kind, target, field, value}`,直接喂给现有 `DirectorCommand` + `apply_command`:

- 注入世界事件:`{kind:"event", value}` → 新增 world_event 公共事件,返回它。
- 私下叮嘱:`{kind:"tell", target, value}` → 追加角色 private_notes,无公共事件。
- 修改角色:`{kind:"set", target, field, value}`(field ∈ goal/persona/voice)→ 改字段,无公共事件。
- 存档走单独的 `/save` 接口(不经 command)。

服务端用 `apply_command(DirectorCommand(...), stage, char_map)` 复用现有逻辑,**不经过 `parse_command`**(避免重新拼字符串再解析,前端已是结构化输入)。

### LLM 注入

`make_llm_from_env()` 在生产创建会话时调用。为可测,工厂做成模块级可替换钩子:`web.server._make_llm`(默认 = `make_llm_from_env`),测试用 `FakeLLM` 覆盖。会话创建失败(缺 key)时返回 500 + 中文错误,前端提示。

### 配置加载

向导提交的是完整故事数据,**不读 YAML**。但保留一个 `GET /api/preset` 返回内置「雨夜古宅」数据(从 `config/雨夜古宅.yaml` 经 `load_config` 读出并转 dict),供前端「载入示例」按钮一键填充向导。

## 前端(web/static/index.html,单文件)

原生 JS,三屏切换(用 `hidden` 切换 section,不用路由库)。所有样式内联在 `<style>`,暗色剧场主题(深底、暖色高亮、衬线感标题)。

### 屏 1:创建向导

- 故事标题(input)、场景(textarea)。
- 角色卡片列表:每张含 name/persona/goal/voice 四个输入;「+ 添加角色」「删除」按钮;默认给 1 张空卡。
- 设置块:总轮数 max_rounds(number,默认 20)、上下文窗口 k(number,默认空=全部,带说明文案)。
- 「载入示例(雨夜古宅)」按钮 → 拉 `/api/preset` 填充。
- 「开演」按钮 → `POST /api/story` → 进剧场。前端做基本校验(标题/场景非空、至少 1 个有名字的角色)。

### 屏 2:剧场

- 顶栏:故事标题、「第 X / Y 回合」进度、设置齿轮(打开设置浮层,改 max_rounds/k → PATCH)。
- 故事流:按事件类型分色渲染。
  - `narration`(旁白):`〔…〕` 斜体暗色。
  - `speech`(台词):`角色名:内容`,角色名高亮。
  - `world_event`:`【世界】…` 醒目黄。
  - `director`:`【导演】…` 紫。
  - `error`:红字提示条。
- 「▶ 继续下一回合」按钮:点击 → 打开 SSE `/round`,逐条 append 到故事流,期间按钮转 spinner 禁用;收到 `done` 更新回合数、重新启用;若 round ≥ max_rounds,按钮变「剧终」并显示下载区。
- 「✎ 导演」按钮:展开导演面板。

### 屏 2 内:导演面板(表单)

三个折叠/并列表单块:

1. **注入世界事件**:textarea + 「注入」→ command(event)。返回的 world_event 立即 append 到故事流。
2. **私下叮嘱**:角色下拉(取自会话角色)+ textarea + 「叮嘱」→ command(tell)。成功显示一条本地 toast(不入故事流,因为是私有记忆)。
3. **修改角色**:角色下拉 + 字段下拉(goal/persona/voice)+ value 输入 + 「修改」→ command(set)。成功 toast。

外加「存档」按钮 → `/save` → toast 显示路径。

### 屏 3:剧终 / 下载

到 max_rounds 后,剧场底部出现「剧终」区:展示 .md / .jsonl 路径,提供「再演下去(+10 回合)」按钮(PATCH max_rounds 后继续)。

## 错误处理

- LLM 缺 key / 超时:round 的 SSE 推 `error` 帧,前端红字、停 spinner,会话不崩,可改设置/重试。
- 命令找不到角色 / 非法字段:command 接口回 `apply_command` 的中文状态文本,前端 toast 显示。
- 未知 session_id:接口返回 404 + 中文提示。
- 前端刷新:页面加载时若 URL 带 `?s=session_id`,拉 `/state` 恢复故事流(尽力而为;进程重启则会话丢失,提示重新创建)。

## 测试(tests/test_server.py)

用 FastAPI `TestClient` + 注入 `FakeLLM`(覆盖 `web.server._make_llm`):

1. `POST /api/story` 建会话,断言返回 session_id 与回显字段。
2. `GET /round`(SSE)跑一回合:断言事件序列 = 1 旁白 + N 角色台词(N=角色数),最后 `done` 帧 round=1。
3. `POST /command` event:断言返回新 world_event;tell/set:断言状态文本与角色字段变化(set 后 `GET /state` 验证)。
4. `GET /state` 恢复:断言含全部已产生事件。
5. `PATCH /settings`:断言 max_rounds/k 更新。
6. 未知 session → 404。

引擎现有单测(`tests/test_*.py`)不动。

## 新增 / 改动文件

- 新增 `web/__init__.py`、`web/server.py`、`web/static/index.html`、`tests/test_server.py`。
- 改 `requirements.txt`:加 `fastapi>=0.110`、`uvicorn[standard]>=0.27`、`httpx>=0.27`(TestClient 依赖)。
- 改 `README.md`:加「Web 界面」段,启动命令 `py -3.12 -m uvicorn web.server:app --reload`,浏览器开 `http://127.0.0.1:8000`。

## 非目标(YAGNI)

- 不做多用户 / 鉴权 / 数据库持久化(本地单人工具)。
- 不做角色立绘 / TTS / 多媒体。
- 不做 YAML 在线编辑器(向导即编辑入口)。
- 不做前端构建链(明确要求单文件零构建)。
