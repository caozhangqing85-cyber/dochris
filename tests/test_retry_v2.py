"""补充测试 retry_manager.py — 覆盖 retry 异常重试 + llm_retry_with_filter 返回 None"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dochris.core.retry_manager import RetryManager


class TestRetryBranches:
    """覆盖 retry 方法的异常重试分支"""

    @pytest.mark.asyncio
    async def test_retry_raises_after_max_attempts(self):
        """重试全部失败后抛出异常"""
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("connection lost")

        with patch.object(RetryManager, "should_retry", return_value=True):
            with patch.object(RetryManager, "get_retry_delay", return_value=0):
                with pytest.raises(ConnectionError, match="connection lost"):
                    await RetryManager.retry(failing_func, max_attempts=2)

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self):
        """第二次重试成功"""
        call_count = 0

        async def eventual_success():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("timeout")
            return "success"

        with patch.object(RetryManager, "should_retry", return_value=True):
            with patch.object(RetryManager, "get_retry_delay", return_value=0):
                result = await RetryManager.retry(eventual_success, max_attempts=3)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_llm_retry_returns_none_on_max_retries(self):
        """llm_retry_with_filter 达到最大重试返回 None"""
        async def always_fail():
            raise RuntimeError("API error")

        with patch("dochris.core.retry_manager.RetryManager.should_retry", return_value=True):
            with patch("dochris.core.retry_manager.RetryManager.get_retry_delay", return_value=0):
                result = await RetryManager.llm_retry_with_filter(
                    always_fail, max_retries=1
                )

        assert result is None
