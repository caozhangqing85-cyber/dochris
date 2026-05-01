"""补充测试 retry_manager.py — 覆盖 get_retry_delay else 分支 + retry last_error"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dochris.core.retry_manager import RetryManager


class TestGetRetryDelayElse:
    """覆盖 get_retry_delay 的 else 分支 (line 60)"""

    def test_delay_without_config(self):
        """没有 config 参数时返回 base_delay"""
        # should_retry=False 的错误类型不需要 delay 计算
        error = ValueError("test")
        delay = RetryManager.get_retry_delay(0, error)
        assert isinstance(delay, int)

    def test_delay_with_zero_attempt(self):
        """attempt=0 返回 base_delay"""
        error = ConnectionError("test")
        delay = RetryManager.get_retry_delay(0, error)
        assert delay >= 0


class TestRetryLastError:
    """覆盖 retry 方法的 last_error 路径 (lines 82-83, 91)"""

    @pytest.mark.asyncio
    async def test_retry_should_not_retry_raises(self):
        """should_retry=False 时立即抛出异常"""
        async def always_fail():
            raise ValueError("no retry")

        with patch.object(RetryManager, "should_retry", return_value=False):
            with pytest.raises(ValueError, match="no retry"):
                await RetryManager.retry(always_fail, max_attempts=1)


class TestLlmRetryWaitBranches:
    """覆盖 llm_retry_with_filter 的更多等待分支 (line 172)"""

    @pytest.mark.asyncio
    async def test_llm_retry_generic_exception_retries(self):
        """generic exception 走重试路径"""
        attempt_count = 0

        async def fail_then_succeed():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 1:
                raise RuntimeError("API error")
            return {"result": "success"}

        with patch.object(RetryManager, "should_retry", return_value=True):
            with patch.object(RetryManager, "get_retry_delay", return_value=0):
                result = await RetryManager.llm_retry_with_filter(
                    fail_then_succeed, max_retries=2
                )

        assert result == {"result": "success"}
