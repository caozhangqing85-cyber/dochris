"""补充测试 llm/ollama.py — 覆盖 generate with system_prompt"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOllamaGenerate:
    """覆盖 generate 方法 (lines 68-78)"""

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self):
        """带 system_prompt 的 generate 调用 generate_with_messages"""
        from dochris.llm.ollama import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434", model="test")

        with patch.object(provider, "generate_with_messages", new_callable=AsyncMock, return_value="response") as mock_gwm:
            with patch("dochris.llm.ollama.aiohttp", MagicMock()):  # 确保 aiohttp 可用
                result = await provider.generate("hello", system_prompt="你是一个助手")

        mock_gwm.assert_called_once()
        call_args = mock_gwm.call_args
        messages = call_args[0][0]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert result == "response"

    @pytest.mark.asyncio
    async def test_generate_without_system_prompt(self):
        """不带 system_prompt 的 generate"""
        from dochris.llm.ollama import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434", model="test")

        with patch.object(provider, "generate_with_messages", new_callable=AsyncMock, return_value="ok") as mock_gwm:
            with patch("dochris.llm.ollama.aiohttp", MagicMock()):
                result = await provider.generate("hello")

        messages = mock_gwm.call_args[0][0]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_generate_no_aiohttp(self):
        """aiohttp 未安装时抛出 ImportError"""
        from dochris.llm.ollama import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434", model="test")

        with patch("dochris.llm.ollama.aiohttp", None):
            with pytest.raises(ImportError, match="aiohttp"):
                await provider.generate("hello")
