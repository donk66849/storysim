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

## Web 界面(推荐)

```bash
py -3.12 -m pip install -r requirements.txt
py -3.12 -m uvicorn web.server:app          # 加 --reload 可热重载
```

浏览器打开 `http://127.0.0.1:8000`:

1. **创建向导** —— 填故事标题、场景背景,增删角色(人设 / 目标 / 说话风格),设总轮数;可一键「载入示例」。
2. **剧场** —— 点「继续下一回合」逐条看旁白与各角色流式演绎;右上设置齿轮随时改轮数 / 上下文窗口。
3. **导演面板** —— 表单式注入世界事件、私下叮嘱某角色、修改角色字段,或一键存档。

后端复用同一套引擎,故事同样落盘到 `runs/<时间戳>.md` 与 `.jsonl`。

## 上线部署

公开访问(如发到小红书引流)前已内置防护:**每日体验配额**(每 IP / 每浏览器 / 全站三道闸,单位=回合)、**输入封顶**(`max_rounds ≤ 30`、角色数与文本长度限制)、以及剧场里的**「提建议」按钮**(留言落到 `runs/feedback.jsonl`)。配额可用环境变量调,见 `.env.example`。

推荐路径(国内轻量服务器):

```bash
# 1. 代码放 /opt/storysim,建虚拟环境装依赖,.env 填 LLM key
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. systemd 守护(单 worker:会话在进程内存,多 worker 会丢会话)
sudo cp deploy/storysim.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now storysim

# 3. Caddy 反代 + 自动 HTTPS(改 Caddyfile 里的域名;flush_interval -1 让 SSE 实时下发)
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

容器化可用根目录 `Dockerfile`(同样单 worker)。**注意**:面向不特定公众正经运营,国内需 ICP 备案与生成式 AI 内容合规;玩票引流量级影响小但需知悉。

## 命令行运行

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
| `exit 老周` | 让某角色退场(死亡/离开),后续回合不再发言 |
| `enter 老周` | 让退场的角色重新登场 |
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
