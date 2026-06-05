"""按天计数的体验配额:每 IP、每浏览器、以及全站总量三道闸,单位是「回合」
(LLM 花钱的最小单位)。每个自然日自动清零。进程内内存计数,重启即重置——
对小流量(小红书引流)的玩票部署足够,单 worker 下计数才准确。

额度可用环境变量调:
    STORYSIM_PER_IP_DAILY     每个 IP 每天回合上限(默认 60,约 2-3 个完整故事)
    STORYSIM_PER_CLIENT_DAILY 每个浏览器每天回合上限(默认 60)
    STORYSIM_GLOBAL_DAILY     全站每天回合总上限(默认 2000,钱包保命)
"""
import os
from collections import defaultdict
from datetime import date


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class Quota:
    def __init__(
        self,
        per_ip: int | None = None,
        per_client: int | None = None,
        global_cap: int | None = None,
    ):
        self.per_ip = (
            per_ip if per_ip is not None else _env_int("STORYSIM_PER_IP_DAILY", 60)
        )
        self.per_client = (
            per_client
            if per_client is not None
            else _env_int("STORYSIM_PER_CLIENT_DAILY", 60)
        )
        self.global_cap = (
            global_cap
            if global_cap is not None
            else _env_int("STORYSIM_GLOBAL_DAILY", 2000)
        )
        self._day: str | None = None
        self._ip: dict[str, int] = defaultdict(int)
        self._client: dict[str, int] = defaultdict(int)
        self._global = 0

    def _roll(self, today: str) -> None:
        if today != self._day:
            self._day = today
            self._ip.clear()
            self._client.clear()
            self._global = 0

    def try_consume(self, ip: str, client: str, today: str | None = None) -> str | None:
        """放行则扣一次额度并返回 None;被拦则不扣、返回中文拒绝原因。"""
        today = today or date.today().isoformat()
        self._roll(today)
        if self._global >= self.global_cap:
            return "今天全站的体验额度被抢光啦,明天再来玩吧~"
        if self.per_ip and self._ip[ip] >= self.per_ip:
            return f"你今天玩得够多啦(每天上限 {self.per_ip} 回合),明天再来~"
        if self.per_client and client and self._client[client] >= self.per_client:
            return f"你今天玩得够多啦(每天上限 {self.per_client} 回合),明天再来~"
        self._ip[ip] += 1
        if client:
            self._client[client] += 1
        self._global += 1
        return None
