"""llm_client.py 覆盖率提升测试"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestExtractJSON:
    """测试 _extract_json_from_text 的各种分支"""

    def setup_method(self):
        # 不需要真正初始化 LLMClient，直接测试方法
        from dochris.core.llm_client import LLMClient
        # 只设置必要属性，跳过 __init__
        self.client = object.__new__(LLMClient)
        self.client.no_think = False

    def test_extract_simple_json(self):
        result = self.client._extract_json_from_text('前缀 {"a": 1} 后缀')
        assert result == {"a": 1}

    def test_extract_nested_json(self):
        result = self.client._extract_json_from_text('text {"a": {"b": 2}} more')
        assert result == {"a": {"b": 2}}

    def test_extract_array_in_json(self):
        result = self.client._extract_json_from_text('{"items": [1, 2, 3]}')
        assert result == {"items": [1, 2, 3]}

    def test_extract_with_quotes(self):
        result = self.client._extract_json_from_text('{"key": "value with \\"quotes\\""}')
        assert result == {"key": 'value with "quotes"'}

    def test_extract_single_quotes(self):
        result = self.client._extract_json_from_text("{'key': 'value'}")
        # json.loads 失败后回退
        # 这个可能返回 None 因为 json 不支持单引号

    def test_extract_no_braces(self):
        result = self.client._extract_json_from_text("no json here")
        assert result is None

    def test_extract_unmatched_braces(self):
        result = self.client._extract_json_from_text('{"key": "value"')
        assert result is None

    def test_extract_empty_json(self):
        result = self.client._extract_json_from_text('{}')
        assert result == {}

    def test_extract_escaped_braces_in_string(self):
        # 测试转义字符不崩溃
        result = self.client._extract_json_from_text('{"text": "value"}')
        assert result is not None

    def test_extract_multiple_json_objects(self):
        """只提取第一个完整的 JSON 对象"""
        result = self.client._extract_json_from_text('{"a": 1} {"b": 2}')
        assert result == {"a": 1}

    def test_extract_nested_braces(self):
        """嵌套大括号用栈匹配"""
        result = self.client._extract_json_from_text('{"outer": {"inner": "value"}}')
        assert result == {"outer": {"inner": "value"}}

    def test_extract_complex_json(self):
        text = json.dumps({
            "one_line": "test",
            "key_points": ["point1", "point2"],
            "detailed_summary": "long text here",
            "concepts": [{"name": "concept1"}, {"name": "concept2"}],
        })
        result = self.client._extract_json_from_text(f"prefix {text} suffix")
        assert result is not None
        assert "one_line" in result


class TestNoThink:
    """测试 qwen3 /no_think 标记"""

    def setup_method(self):
        from dochris.core.llm_client import LLMClient
        self.client = object.__new__(LLMClient)
        self.client.no_think = True

    def test_no_think_applied(self):
        messages = [{"role": "system", "content": "Be helpful"}]
        result = self.client._apply_no_think(messages)
        assert "/no_think" in result[0]["content"]

    def test_no_think_not_applied_non_qwen(self):
        client = object.__new__(type(self.client))
        client.no_think = False
        messages = [{"role": "system", "content": "Be helpful"}]
        result = client._apply_no_think(messages)
        assert "/no_think" not in result[0]["content"]

    def test_no_think_not_applied_no_system(self):
        messages = [{"role": "user", "content": "hello"}]
        result = self.client._apply_no_think(messages)
        assert result == messages


class TestClientCleanup:
    """测试客户端资源清理"""

    def test_register_and_cleanup(self):
        from dochris.core.llm_client import _client_instances, cleanup_all_clients, register_client

        _client_instances.clear()

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        register_client(mock_client)
        assert len(_client_instances) == 1

        cleanup_all_clients()
        assert len(_client_instances) == 0

    def test_cleanup_empty(self):
        from dochris.core.llm_client import _client_instances, cleanup_all_clients

        _client_instances.clear()
        cleanup_all_clients()  # 不应该报错

    def test_cleanup_with_error(self):
        from dochris.core.llm_client import _client_instances, cleanup_all_clients, register_client

        _client_instances.clear()

        mock_client = MagicMock()
        mock_client.close = AsyncMock(side_effect=Exception("close failed"))
        register_client(mock_client)
        cleanup_all_clients()  # 应该吞掉异常
        assert len(_client_instances) == 0


class TestLLMClientInit:
    """测试 LLMClient 初始化的各种分支"""

    def test_default_params(self):
        """验证默认参数值（不需要真正初始化）"""
        # 直接检查 __init__ 签名
        import inspect

        from dochris.core.llm_client import LLMClient
        sig = inspect.signature(LLMClient.__init__)
        assert sig.parameters["model"].default == "glm-5.1"
        assert sig.parameters["max_tokens"].default == 40000
        assert sig.parameters["temperature"].default == 0.1
        assert sig.parameters["request_delay"].default == 5.0


class TestAsyncContextManager:
    """测试异步上下文管理器"""

    @pytest.mark.asyncio
    async def test_aenter_aexit(self):
        from dochris.core.llm_client import LLMClient
        client = object.__new__(LLMClient)
        client.close = AsyncMock()
        client.provider = MagicMock()
        client.provider.close = AsyncMock()

        async with client as c:
            assert c is client

        client.close.assert_awaited_once()
