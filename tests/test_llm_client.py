#!/usr/bin/env python3
"""
测试 LLM 客户端（mock API）
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestLLMClient(unittest.TestCase):
    """测试 LLM 客户端"""

    def test_client_init(self):
        """测试客户端初始化"""
        from dochris.core.llm_client import LLMClient

        client = LLMClient(
            api_key="test_key",
            base_url="https://api.test.com",
            model="test_model"
        )

        self.assertEqual(client.model, "test_model")
        # LLMClient 没有公开 api_key 属性，只检查 model

    def test_build_messages(self):
        """测试消息构建"""
        from dochris.core.llm_client import LLMClient

        client = LLMClient(api_key="test", base_url="https://test.com")
        messages = client._build_messages("test content", "Test Title")

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")

    def test_extract_json_from_text(self):
        """测试 JSON 提取"""
        from dochris.core.llm_client import LLMClient

        client = LLMClient(api_key="test", base_url="https://test.com")

        # 有效 JSON
        text_with_json = "Some text {\"key\": \"value\"} more text"
        result = client._extract_json_from_text(text_with_json)
        self.assertEqual(result, {"key": "value"})

        # 无效 JSON
        text_no_json = "No JSON here"
        result = client._extract_json_from_text(text_no_json)
        self.assertIsNone(result)


class TestLLMClientAsync(unittest.TestCase):
    """测试 LLM 客户端异步功能"""

    @patch('dochris.core.llm_client.AsyncOpenAI')
    async def test_generate_summary_mock(self, mock_openai):
        """测试摘要生成（mock）"""
        # Mock API 响应
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = '{"one_line": "test", "key_points": ["point1"]}'
        mock_choice.message.content = mock_message.content
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client

        from dochris.core.llm_client import LLMClient

        client = LLMClient(api_key="test", base_url="https://test.com")
        client.client = mock_client

        result = await client.generate_summary("test content", "Test Title")

        self.assertIsNotNone(result)
        self.assertEqual(result["one_line"], "test")

    def test_rate_limit(self):
        """测试速率限制"""
        from dochris.core.llm_client import LLMClient

        client = LLMClient(api_key="test", base_url="https://test.com", request_delay=0.1)

        # 设置上次请求时间
        client.last_request_time = 0

        # 速率限制应该在第一次调用时生效
        # 这里只测试接口存在
        self.assertTrue(callable(client._rate_limit))


if __name__ == "__main__":
    unittest.main()
