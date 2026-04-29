#!/usr/bin/env python3
"""
重试管理
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class RetryManager:
    """重试管理器"""

    # 错误类型到重试配置的映射
    RETRY_CONFIG = {
        "rate_limit_429": {"max_retries": 5, "base_delay": 10, "exponential": True},
        "timeout": {"max_retries": 3, "base_delay": 5, "exponential": True},
        "other": {"max_retries": 2, "base_delay": 5, "exponential": True},
    }

    @classmethod
    def get_error_type(cls, error: Exception) -> str:
        """识别错误类型"""
        error_str = str(error).lower()

        if "429" in error_str or "rate" in error_str:
            return "rate_limit_429"
        elif "timeout" in error_str:
            return "timeout"
        else:
            return "other"

    @classmethod
    def should_retry(cls, error: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        error_type = cls.get_error_type(error)
        config = cls.RETRY_CONFIG[error_type]
        return attempt < config["max_retries"]

    @classmethod
    def get_retry_delay(cls, attempt: int, error: Exception | None = None) -> int:
        """获取重试延迟"""
        if error:
            error_type = cls.get_error_type(error)
            config = cls.RETRY_CONFIG[error_type]
        else:
            error_type = "other"
            config = cls.RETRY_CONFIG[error_type]

        if config["exponential"]:
            return min(
                config["base_delay"] * (2**attempt),
                60,  # 最大 60 秒
            )
        else:
            return config["base_delay"]

    @classmethod
    async def retry(cls, func, *args, max_attempts: int = 10, **kwargs) -> Any:
        """
        重试包装器

        Usage:
            result = await RetryManager.retry(llm_call, text, title)
        """
        last_error = None

        for attempt in range(max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except (RuntimeError, ValueError, OSError, TimeoutError, ConnectionError) as e:
                last_error = e

                if not cls.should_retry(e, attempt):
                    logger.error(f"Max retries exceeded: {e}")
                    raise

                delay = cls.get_retry_delay(attempt, e)
                logger.warning(f"Retry {attempt + 1} after {delay}s: {e}")
                await asyncio.sleep(delay)

        raise last_error
