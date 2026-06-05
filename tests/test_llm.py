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
