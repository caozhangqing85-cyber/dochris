#!/usr/bin/env python3
"""
测试重试管理器
"""

import sys
import unittest
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestRetryManager(unittest.TestCase):
    """测试重试管理器"""

    def test_get_error_type(self):
        """测试错误类型识别"""
        from dochris.core.retry_manager import RetryManager

        # 429 错误
        error_429 = Exception("429 Too Many Requests")
        self.assertEqual(RetryManager.get_error_type(error_429), "rate_limit_429")

        # 超时错误
        error_timeout = Exception("Request timeout")
        self.assertEqual(RetryManager.get_error_type(error_timeout), "timeout")

        # 其他错误
        error_other = Exception("Unknown error")
        self.assertEqual(RetryManager.get_error_type(error_other), "other")

    def test_should_retry(self):
        """测试是否应该重试"""
        from dochris.core.retry_manager import RetryManager

        error_429 = Exception("429 Too Many Requests")

        # 第一次应该重试
        self.assertTrue(RetryManager.should_retry(error_429, 0))

        # 超过最大重试次数
        max_retries = RetryManager.RETRY_CONFIG["rate_limit_429"]["max_retries"]
        self.assertFalse(RetryManager.should_retry(error_429, max_retries))

    def test_get_retry_delay(self):
        """测试重试延迟计算"""
        from dochris.core.retry_manager import RetryManager

        # 测试指数退避
        delay_0 = RetryManager.get_retry_delay(0)
        delay_1 = RetryManager.get_retry_delay(1)

        self.assertGreater(delay_1, delay_0)
        self.assertLessEqual(delay_0, 60)  # 最大 60 秒


class TestRetryAsync(unittest.TestCase):
    """测试异步重试"""

    async def test_retry_success(self):
        """测试重试成功"""
        from dochris.core.retry_manager import RetryManager

        call_count = [0]

        async def failing_function():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("429 rate limit")
            return "success"

        result = await RetryManager.retry(failing_function, max_attempts=3)
        self.assertEqual(result, "success")
        self.assertEqual(call_count[0], 2)

    async def test_retry_exhausted(self):
        """测试重试耗尽"""
        from dochris.core.retry_manager import RetryManager

        async def always_failing():
            raise Exception("Always fails")

        with self.assertRaises(Exception):
            await RetryManager.retry(always_failing, max_attempts=2)


if __name__ == "__main__":
    unittest.main()
