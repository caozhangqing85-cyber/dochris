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
            return int(
                min(
                    config["base_delay"] * (2**attempt),
                    60,  # 最大 60 秒
                )
            )
        else:
            return int(config["base_delay"])

    @classmethod
    async def retry(cls, func: Any, *args: Any, max_attempts: int = 10, **kwargs: Any) -> Any:
        """
        重试包装器

        Usage:
            result = await RetryManager.retry(llm_call, text, title)
        """
        last_error: Exception | None = None

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

        if last_error is not None:
            raise last_error
        raise RuntimeError("Retry failed with no error captured")

    @classmethod
    async def llm_retry_with_filter(
        cls,
        func: Any,
        *args: Any,
        max_retries: int = 8,
        on_content_filter: Any = None,
        **kwargs: Any,
    ) -> Any | None:
        """
        LLM 调用专用重试（支持 content filter 检测）

        与基础 retry() 的区别：
        - content filter 错误返回 None（不抛异常）
        - 针对不同错误类型使用不同的延迟策略
        - 专为 LLM API 调用设计

        Args:
            func: 要重试的异步函数
            *args: 函数位置参数
            max_retries: 最大重试次数
            on_content_filter: content filter 时返回的值（默认 None）
            **kwargs: 函数关键字参数

        Returns:
            函数返回值，content filter 时返回 on_content_filter

        Raises:
            最后一次错误（当所有重试都失败时）

        重试策略:
            - 429 错误: 指数退避（30s, 60s, 120s...）
            - 连接/超时错误: 指数退避（20s, 40s, 80s...）
            - 内容过滤: 不重试，返回 on_content_filter
            - 其他错误: 指数退避（10s, 20s, 40s...）
        """
        MAX_RETRY_WAIT = 60

        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_str = str(e)

                # 内容过滤：不重试（最高优先级检查）
                if "contentfilter" in error_str.lower() or "content filter" in error_str.lower():
                    logger.warning(f"Content filter triggered: {e}")
                    return on_content_filter

                # 429/限流错误：指数退避重试
                if "429" in error_str or "rate" in error_str.lower():
                    wait = min(30 * (2**attempt), MAX_RETRY_WAIT)
                    logger.warning(
                        f"429/rate limit error (attempt {attempt + 1}), waiting {wait}s..."
                    )
                    await asyncio.sleep(wait)

                # 连接错误/超时：延迟重试
                elif (
                    "connection" in error_str.lower()
                    or "timeout" in error_str.lower()
                    or "timed out" in error_str.lower()
                ):
                    wait = min(20 * (2**attempt), MAX_RETRY_WAIT)
                    logger.warning(
                        f"Connection/timeout error (attempt {attempt + 1}), waiting {wait}s..."
                    )
                    await asyncio.sleep(wait)

                # 其他错误：重试
                elif attempt < max_retries - 1:
                    wait = min(10 * (2**attempt), MAX_RETRY_WAIT)
                    logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
                    logger.info(f"Waiting {wait}s before retry...")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"LLM call failed after {max_retries} attempts: {e}")
                    return None

        return None
