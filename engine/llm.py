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
