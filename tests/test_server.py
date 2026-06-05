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


def test_round_at_max_returns_done_without_advancing():
    client = make_client(["x"] * 10)
    r = client.post("/api/story", json={**STORY, "max_rounds": 1})
    sid = r.json()["session_id"]
    read_sse(client, sid)  # 第 1 回合,到达上限
    frames = read_sse(client, sid)  # 再点应直接 done,不演
    assert [f["kind"] for f in frames] == ["done"]
    assert frames[0]["round"] == 1
    assert client.get(f"/api/story/{sid}/state").json()["round"] == 1


def test_failed_round_rolls_back_round():
    client = make_client([])  # 空响应 -> narrator 取响应即抛错
    sid = _create(client)
    frames = read_sse(client, sid)
    kinds = [f["kind"] for f in frames]
    assert "error" in kinds
    assert frames[-1] == {"kind": "done", "round": 0}  # 空转回合未消耗轮数
    assert client.get(f"/api/story/{sid}/state").json()["round"] == 0


def test_exit_command_then_round_skips_character():
    client = make_client(["旁白", "甲说"] + ["x"] * 10)
    sid = _create(client)  # STORY 有 甲、乙
    out = client.post(
        f"/api/story/{sid}/command", json={"kind": "exit", "target": "乙"}
    ).json()
    assert "乙" in out["status"]
    frames = read_sse(client, sid)
    actors = [f["event"]["actor"] for f in frames if f["kind"] == "event"]
    assert "甲" in actors
    assert "乙" not in actors  # 乙退场后不再发言


def test_finale_round_streams_closing_epilogue():
    client = make_client(["开场", "甲说", "乙说", "尘埃落定"])  # 2 角色 + 大结局
    r = client.post("/api/story", json={**STORY, "max_rounds": 1})
    sid = r.json()["session_id"]
    frames = read_sse(client, sid)
    events = [f["event"] for f in frames if f["kind"] == "event"]
    assert [e["type"] for e in events] == [
        "narration", "speech", "speech", "narration",
    ]
    assert events[-1]["actor"] == "旁白"
    assert events[-1]["content"] == "尘埃落定"


def test_settings_can_reset_k_to_null():
    client = make_client(["x"] * 10)
    r = client.post("/api/story", json={**STORY, "k": 5})
    sid = r.json()["session_id"]
    out = client.patch(f"/api/story/{sid}/settings", json={"k": None}).json()
    assert out["k"] is None


def test_index_html_is_well_formed():
    client = make_client([])
    html = client.get("/").text
    # 缺了 </script> 会让浏览器永不执行内联脚本(向导按钮全失效)
    for tag in ("<script>", "</script>", "</body>", "</html>"):
        assert tag in html, f"index.html 缺少 {tag}"


def test_delete_session():
    client = make_client(["x"] * 10)
    sid = _create(client)
    assert client.delete(f"/api/story/{sid}").json() == {"ok": True}
    assert client.get(f"/api/story/{sid}/state").status_code == 404
