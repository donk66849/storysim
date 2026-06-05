from web.limits import Quota


def test_blocks_after_per_ip_cap():
    q = Quota(per_ip=3, per_client=100, global_cap=100)
    assert all(q.try_consume("1.1.1.1", "c1", today="d") is None for _ in range(3))
    assert q.try_consume("1.1.1.1", "c1", today="d") is not None  # 第 4 次被拦


def test_per_client_cap_blocks_across_ips():
    q = Quota(per_ip=100, per_client=2, global_cap=100)
    q.try_consume("1.1.1.1", "c1", today="d")
    q.try_consume("2.2.2.2", "c1", today="d")  # 同浏览器换 IP
    assert q.try_consume("3.3.3.3", "c1", today="d") is not None


def test_global_cap_blocks_everyone():
    q = Quota(per_ip=100, per_client=100, global_cap=2)
    q.try_consume("a", "x", today="d")
    q.try_consume("b", "y", today="d")
    assert q.try_consume("c", "z", today="d") is not None


def test_counts_reset_next_day():
    q = Quota(per_ip=1, per_client=100, global_cap=100)
    q.try_consume("1.1.1.1", "c", today="2026-06-06")
    assert q.try_consume("1.1.1.1", "c", today="2026-06-06") is not None
    assert q.try_consume("1.1.1.1", "c", today="2026-06-07") is None  # 隔天重置


def test_empty_client_does_not_trip_client_cap():
    q = Quota(per_ip=100, per_client=1, global_cap=100)
    q.try_consume("1.1.1.1", "", today="d")
    assert q.try_consume("2.2.2.2", "", today="d") is None  # 空浏览器 id 不算浏览器限额


def test_blocked_request_does_not_consume():
    q = Quota(per_ip=1, per_client=100, global_cap=100)
    q.try_consume("1.1.1.1", "c", today="d")
    q.try_consume("1.1.1.1", "c", today="d")  # 被拦,不应再扣全局额度
    # 换个 IP 仍可玩(说明全局没被误扣到上限)
    assert q.try_consume("2.2.2.2", "c2", today="d") is None
