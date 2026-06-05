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
