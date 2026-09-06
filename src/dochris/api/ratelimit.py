"""轻量内存限流（SEC-02）。

面向 public 部署的最小限流能力：滑动窗口计数，按客户端 IP 限速。
默认关闭；设置 ``DOCHRIS_RATE_LIMIT_PER_MINUTE``（如 "120"）后启用，
超过阈值的请求返回 429。

只适合单进程部署；多副本部署请在反向代理层限流。
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class SlidingWindowLimiter:
    """按 key 的滑动窗口计数器。"""

    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        self.max_requests = max(1, max_requests)
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """记录一次命中并判断是否放行。过期条目按 key 清理；活跃 key 常驻（数量有界：真实来源 IP 集合）。"""
        current = time.monotonic() if now is None else now
        window_start = current - self.window_seconds
        hits = self._hits.get(key)
        if hits is None:
            hits = deque()
            self._hits[key] = hits
        while hits and hits[0] <= window_start:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(current)
        return True


def rate_limit_per_minute() -> int:
    """读取限流配置；未设置或非法时返回 0（关闭）。"""
    raw = os.environ.get("DOCHRIS_RATE_LIMIT_PER_MINUTE", "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
        return value if value > 0 else 0
    except ValueError:
        logger.warning("无效的 DOCHRIS_RATE_LIMIT_PER_MINUTE=%r，限流保持关闭", raw)
        return 0
