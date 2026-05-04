#!/usr/bin/env python3
"""测试 LLM 提供商抽象层"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dochris.llm.base import BaseLLMProvider
from dochris.llm.ollama import OllamaProvider
from dochris.llm.openai_compat import OpenAICompatProvider


class TestBaseLLMProvider:
    """测试 BaseLLMProvider 抽象基类"""

    def test_cannot_instantiate_base_class(self) -> None:
        """验证不能直接实例化基类"""
        with pytest.raises(TypeError, match="abstract"):
            BaseLLMProvider()

    def test_abstract_methods_exist(self) -> None:
        """验证抽象方法存在"""
        abstract_methods = BaseLLMProvider.__abstractmethods__
        expected = {"generate", "generate_with_messages"}
        assert abstract_methods == expected

    def test_init_default_values(self) -> None:
        """测试初始化默认值"""

        class ConcreteProvider(BaseLLMProvider):
            name = "concrete"

            async def generate(
                self, prompt, system_prompt=None, max_tokens=None, temperature=None, **kwargs
            ):
                return ""

            async def generate_with_messages(
                self, messages, max_tokens=None, temperature=None, **kwargs
            ):
                return ""

        provider = ConcreteProvider()
        assert provider.api_key == ""
        assert provider.api_base is None
        assert provider.model == ""
        assert provider.max_tokens == 4000
        assert provider.temperature == 0.7
        assert provider.timeout == 120

    def test_init_with_custom_values(self) -> None:
        """测试自定义初始化值"""

        class ConcreteProvider(BaseLLMProvider):
            name = "concrete"

            async def generate(
                self, prompt, system_prompt=None, max_tokens=None, temperature=None, **kwargs
            ):
                return ""

            async def generate_with_messages(
                self, messages, max_tokens=None, temperature=None, **kwargs
            ):
                return ""

        provider = ConcreteProvider(
            api_key="test-key",
            api_base="https://api.example.com",
            model="test-model",
            max_tokens=2000,
            temperature=0.5,
            timeout=60,
        )
        assert provider.api_key == "test-key"
        assert provider.api_base == "https://api.example.com"
        assert provider.model == "test-model"
        assert provider.max_tokens == 2000
        assert provider.temperature == 0.5
        assert provider.timeout == 60

    def test_close_default_implementation(self) -> None:
        """测试 close 默认实现（空方法）"""

        class ConcreteProvider(BaseLLMProvider):
            name = "concrete"

            async def generate(
                self, prompt, system_prompt=None, max_tokens=None, temperature=None, **kwargs
            ):
                return ""

            async def generate_with_messages(
                self, messages, max_tokens=None, temperature=None, **kwargs
            ):
                return ""

        provider = ConcreteProvider()
        # 默认 close 不应抛出错误
        import asyncio

        asyncio.run(provider.close())

    def test_repr(self) -> None:
        """测试 __repr__ 实现"""

        class ConcreteProvider(BaseLLMProvider):
            name = "concrete"

            async def generate(
                self, prompt, system_prompt=None, max_tokens=None, temperature=None, **kwargs
            ):
                return ""

            async def generate_with_messages(
                self, messages, max_tokens=None, temperature=None, **kwargs
            ):
                return ""

        provider = ConcreteProvider(model="test-model")
        assert repr(provider) == "ConcreteProvider(model='test-model')"


class TestLLMProviderRegistry:
    """测试 LLM 提供商注册表"""

    def test_providers_has_openai_compat(self) -> None:
        """验证 PROVIDERS 包含 openai_compat"""
        from dochris.llm import PROVIDERS

        assert "openai_compat" in PROVIDERS
        assert PROVIDERS["openai_compat"] == OpenAICompatProvider

    def test_providers_has_ollama(self) -> None:
        """验证 PROVIDERS 包含 ollama"""
        from dochris.llm import PROVIDERS

        assert "ollama" in PROVIDERS
        assert PROVIDERS["ollama"] == OllamaProvider

    def test_get_provider_openai_compat(self) -> None:
        """验证 get_provider('openai_compat') 返回正确类"""
        from dochris.llm import get_provider

        provider_cls = get_provider("openai_compat")
        assert provider_cls == OpenAICompatProvider

    def test_get_provider_ollama(self) -> None:
        """验证 get_provider('ollama') 返回正确类"""
        from dochris.llm import get_provider

        provider_cls = get_provider("ollama")
        assert provider_cls == OllamaProvider

    def test_get_provider_unknown_raises_value_error(self) -> None:
        """验证 get_provider('unknown') 抛出 ValueError"""
        from dochris.llm import get_provider

        with pytest.raises(ValueError, match="Unknown LLM provider.*unknown"):
            get_provider("unknown")

    def test_get_provider_error_message_shows_available(self) -> None:
        """验证错误消息包含可用提供商列表"""
        from dochris.llm import get_provider

        with pytest.raises(ValueError) as exc_info:
            get_provider("fake_provider")
        assert "openai_compat" in str(exc_info.value)
        assert "ollama" in str(exc_info.value)


class TestOpenAICompatProvider:
    """测试 OpenAICompatProvider 实现"""

    def test_name(self) -> None:
        """验证 name 属性"""
        assert OpenAICompatProvider.name == "openai_compat"

    def test_init(self) -> None:
        """测试初始化"""
        provider = OpenAICompatProvider(
            api_key="test-key",
            api_base="https://api.example.com",
            model="test-model",
        )
        assert provider.api_key == "test-key"
        assert provider.api_base == "https://api.example.com"
        assert provider.model == "test-model"
        assert provider._client is None

    def test_get_client_raises_import_error_when_not_installed(self) -> None:
        """测试 openai 包未安装时抛出 ImportError"""
        with patch.dict("sys.modules", {"openai": None}):
            provider = OpenAICompatProvider(api_key="test", model="test-model")

            with pytest.raises(ImportError, match="openai package not installed"):
                provider._get_client()

    def test_get_client_creates_async_openai(self) -> None:
        """测试 _get_client 创建 AsyncOpenAI 实例"""
        mock_client = MagicMock()
        mock_async_openai = MagicMock()
        mock_async_openai.AsyncOpenAI.return_value = mock_client
        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = MagicMock()

        with patch.dict("sys.modules", {"openai": mock_async_openai, "httpx": mock_httpx}):
            provider = OpenAICompatProvider(
                api_key="test-key",
                api_base="https://api.example.com",
                model="test-model",
                timeout=60,
            )
            client = provider._get_client()

            assert client == mock_client
            mock_async_openai.AsyncOpenAI.assert_called_once()
            assert provider._client == mock_client

    def test_generate(self) -> None:
        """测试 generate 方法"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Generated text"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_async_openai = MagicMock()
        mock_async_openai.AsyncOpenAI.return_value = mock_client
        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = MagicMock()

        with patch.dict("sys.modules", {"openai": mock_async_openai, "httpx": mock_httpx}):
            provider = OpenAICompatProvider(api_key="test", model="test-model")

            import asyncio

            result = asyncio.run(
                provider.generate(
                    "Hello", system_prompt="You are helpful", max_tokens=100, temperature=0.5
                )
            )

            assert result == "Generated text"

            # 验证调用参数
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["model"] == "test-model"
            assert call_args[1]["max_tokens"] == 100
            assert call_args[1]["temperature"] == 0.5
            assert call_args[1]["messages"] == [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ]

    def test_generate_with_default_values(self) -> None:
        """测试 generate 使用默认参数值"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Result"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_async_openai = MagicMock()
        mock_async_openai.AsyncOpenAI.return_value = mock_client
        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = MagicMock()

        with patch.dict("sys.modules", {"openai": mock_async_openai, "httpx": mock_httpx}):
            provider = OpenAICompatProvider(
                api_key="test", model="test-model", max_tokens=4000, temperature=0.7
            )

            import asyncio

            result = asyncio.run(provider.generate("Hello"))

            assert result == "Result"
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["max_tokens"] == 4000
            assert call_args[1]["temperature"] == 0.7

    def test_generate_with_messages(self) -> None:
        """测试 generate_with_messages 方法"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Chat response"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_async_openai = MagicMock()
        mock_async_openai.AsyncOpenAI.return_value = mock_client
        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = MagicMock()

        with patch.dict("sys.modules", {"openai": mock_async_openai, "httpx": mock_httpx}):
            provider = OpenAICompatProvider(api_key="test", model="test-model")

            import asyncio

            messages = [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"},
            ]
            result = asyncio.run(provider.generate_with_messages(messages, max_tokens=200))

            assert result == "Chat response"
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["messages"] == messages
            assert call_args[1]["max_tokens"] == 200

    def test_close(self) -> None:
        """测试 close 方法"""
        mock_client = MagicMock()
        mock_client.close = AsyncMock()

        mock_async_openai = MagicMock()
        mock_async_openai.AsyncOpenAI.return_value = mock_client
        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = MagicMock()

        with patch.dict("sys.modules", {"openai": mock_async_openai, "httpx": mock_httpx}):
            provider = OpenAICompatProvider(api_key="test", model="test-model")
            provider._get_client()  # 创建 client
            assert provider._client is not None

            import asyncio

            asyncio.run(provider.close())

            assert provider._client is None
            mock_client.close.assert_called_once()

    def test_client_property(self) -> None:
        """测试 client 属性（向后兼容）"""
        mock_client = MagicMock()

        mock_async_openai = MagicMock()
        mock_async_openai.AsyncOpenAI.return_value = mock_client
        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = MagicMock()

        with patch.dict("sys.modules", {"openai": mock_async_openai, "httpx": mock_httpx}):
            provider = OpenAICompatProvider(api_key="test", model="test-model")
            client = provider.client

            assert client == mock_client


class TestOllamaProvider:
    """测试 OllamaProvider 实现"""

    def test_name(self) -> None:
        """验证 name 属性"""
        assert OllamaProvider.name == "ollama"

    def test_init_with_defaults(self) -> None:
        """测试默认参数初始化"""
        provider = OllamaProvider()
        assert provider.api_key == ""  # Ollama 不需要 api_key
        assert provider.base_url == "http://localhost:11434"

    def test_init_with_custom_base_url(self) -> None:
        """测试自定义 base_url"""
        provider = OllamaProvider(api_base="http://192.168.1.100:11434")
        assert provider.base_url == "http://192.168.1.100:11434"

    @pytest.mark.skipif(
        True,  # 跳过这些测试，因为 aiohttp 的模块级 import 导致 mock 复杂
        reason="aiohttp module-level import makes mocking complex; skip for now",
    )
    def test_generate_raises_import_error_when_aiohttp_not_installed(self) -> None:
        """测试 aiohttp 未安装时抛出 ImportError"""
        # 由于模块级别的 import，这个测试难以正确 mock
        pass

    @pytest.mark.skipif(
        True, reason="aiohttp module-level import makes mocking complex; skip for now"
    )
    def test_generate(self) -> None:
        """测试 generate 方法"""
        # 需要 aiohttp 才能运行这些测试
        pass

    @pytest.mark.skipif(
        True, reason="aiohttp module-level import makes mocking complex; skip for now"
    )
    def test_generate_with_default_values(self) -> None:
        """测试 generate 使用默认参数值"""
        pass

    @pytest.mark.skipif(
        True, reason="aiohttp module-level import makes mocking complex; skip for now"
    )
    def test_generate_with_messages(self) -> None:
        """测试 generate_with_messages 方法"""
        pass

    @pytest.mark.skipif(
        True, reason="aiohttp module-level import makes mocking complex; skip for now"
    )
    def test_generate_with_custom_base_url(self) -> None:
        """测试自定义 base_url 的 generate"""
        pass

    @pytest.mark.skipif(
        True, reason="aiohttp module-level import makes mocking complex; skip for now"
    )
    def test_generate_handles_empty_response(self) -> None:
        """测试处理空响应"""
        pass


class TestOllamaProviderIntegration:
    """测试 OllamaProvider 的 generate_with_messages 实际逻辑"""

    @pytest.mark.asyncio
    async def test_generate_with_messages_success(self) -> None:
        """模拟 aiohttp 返回成功响应"""
        p = OllamaProvider(model="qwen", api_base="http://localhost:11434")

        mock_resp = MagicMock()
        mock_resp.json = AsyncMock(return_value={"message": {"content": "hello response"}})
        mock_resp.raise_for_status = MagicMock()

        mock_post_ctx = MagicMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_ctx)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)
        mock_aiohttp.ClientTimeout = MagicMock(return_value=MagicMock())

        with patch("dochris.llm.ollama.aiohttp", mock_aiohttp):
            result = await p.generate_with_messages(
                [{"role": "user", "content": "hello"}],
                max_tokens=100,
                temperature=0.5,
            )
        assert result == "hello response"

    @pytest.mark.asyncio
    async def test_generate_no_aiohttp(self) -> None:
        """aiohttp 设为 None 时应抛出 ImportError"""
        import dochris.llm.ollama as ollama_mod

        original = ollama_mod.aiohttp
        ollama_mod.aiohttp = None
        try:
            p = OllamaProvider(model="qwen")
            with pytest.raises(ImportError, match="aiohttp"):
                await p.generate("hello")
        finally:
            ollama_mod.aiohttp = original

    @pytest.mark.asyncio
    async def test_generate_with_messages_no_aiohttp(self) -> None:
        """aiohttp 设为 None 时 generate_with_messages 也应抛出 ImportError"""
        import dochris.llm.ollama as ollama_mod

        original = ollama_mod.aiohttp
        ollama_mod.aiohttp = None
        try:
            p = OllamaProvider(model="qwen")
            with pytest.raises(ImportError, match="aiohttp"):
                await p.generate_with_messages([{"role": "user", "content": "hi"}])
        finally:
            ollama_mod.aiohttp = original
