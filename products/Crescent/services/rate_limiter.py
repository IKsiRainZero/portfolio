"""滑动窗口速率限制器 — 共享状态模块 (Phase 3: Flask-free)

使用 IP + 路由作为键，线程安全有锁保护。
设计参照 OWASP ASVS 4.0 V11.1.2: 对特定 IP 的请求频率进行限制。

ASGI 中间件 (main.py) 和 api_config 路由共用此模块的状态。
"""

from __future__ import annotations
import time
import threading

# 默认限流配置 (路由前缀 → (max_requests, window_seconds))
_DEFAULT_LIMITS = {
    "/api/agent/chat":    (30, 60),
    "/api/ai/tutor":      (20, 60),
    "/api/ai/rag-query":  (20, 60),
    "/api/config":        (10, 60),
}

# { route_prefix: {"ip+route": [timestamps...]} }
_state = {}
_lock = threading.Lock()

# 日调用计数器
_daily_counter = {}
_counter_lock = threading.Lock()


def _today():
    return time.strftime("%Y-%m-%d")


def _cleanup():
    now = time.time()
    for route, buckets in list(_state.items()):
        limits = _DEFAULT_LIMITS.get(route, (30, 60))
        window = limits[1]
        expired = now - window
        for key in list(buckets.keys()):
            buckets[key] = [t for t in buckets[key] if t > expired]
            if not buckets[key]:
                del buckets[key]


def _match_route(path: str) -> str | None:
    """根据 path 匹配最具体的限流配置"""
    if path in _DEFAULT_LIMITS:
        return path
    for prefix in sorted(_DEFAULT_LIMITS.keys(), key=len, reverse=True):
        if path.startswith(prefix):
            return prefix
    return None


def check_rate_limit(client_ip: str, path: str) -> tuple[bool, int]:
    """检查速率限制。返回 (allowed: bool, retry_after_seconds: int)。"""
    prefix = _match_route(path)
    if not prefix:
        return True, 0

    limit, window = _DEFAULT_LIMITS[prefix]
    key = f"{client_ip}:{prefix}"
    now = time.time()
    window_start = now - window

    with _lock:
        if prefix not in _state:
            _state[prefix] = {}
        bucket = _state[prefix]
        bucket[key] = [t for t in bucket.get(key, []) if t > window_start]
        if len(bucket[key]) >= limit:
            retry_after = int(window - (now - bucket[key][0]) + 1)
            return False, retry_after
        bucket[key].append(now)
        with _counter_lock:
            today = _today()
            _daily_counter[today] = _daily_counter.get(today, 0) + 1

    if hash(key) % 100 == 0:
        _cleanup()

    return True, 0


def get_daily_call_count() -> int:
    """返回当日 API 调用总数"""
    with _counter_lock:
        return _daily_counter.get(_today(), 0)


def set_rate_limit(route_prefix: str, max_requests: int, window_seconds: int = 60):
    """运行时修改限流配置"""
    if max_requests <= 0:
        max_requests = 999999
    _DEFAULT_LIMITS[route_prefix] = (max_requests, window_seconds)


def apply_user_rate_limits():
    """从 user_settings.json 读取限流配置并应用"""
    try:
        from services.user_settings import get_setting
        rpm = get_setting("rate_limit_per_minute", 30)
        unlimited = get_setting("rate_limit_unlimited", False)
        max_req = 999999 if unlimited else rpm
        for route in ["/api/agent/chat", "/api/ai/tutor", "/api/ai/rag-query"]:
            _DEFAULT_LIMITS[route] = (max_req, 60)
    except Exception:
        pass
