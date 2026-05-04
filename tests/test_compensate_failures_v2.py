"""补充测试 compensate/compensate_failures.py — 覆盖 ImportError fallback 函数"""

from unittest.mock import MagicMock

import pytest


class TestSanitizeFallbacks:
    """覆盖 compensate_failures.py 的 sanitize 导入失败 fallback"""

    def test_sanitize_filename_fallback(self):
        """sanitize_filename fallback 返回 stem"""
        from dochris.compensate.compensate_failures import sanitize_filename

        result = sanitize_filename("test.pdf")
        assert result == "test"

    def test_sanitize_pdf_content_fallback(self):
        """sanitize_pdf_content fallback 原样返回"""
        from dochris.compensate.compensate_failures import sanitize_pdf_content

        result = sanitize_pdf_content("原始内容")
        assert result == "原始内容"

    def test_sanitize_prompt_fallback(self):
        """sanitize_prompt fallback 原样返回"""
        from dochris.compensate.compensate_failures import sanitize_prompt

        result = sanitize_prompt("测试提示词")
        assert result == "测试提示词"

    def test_should_skip_file_fallback(self):
        """should_skip_file fallback 返回 False"""
        from dochris.compensate.compensate_failures import should_skip_file

        result = should_skip_file("anything.pdf")
        assert result == (False, None)


class TestCompileWithModelFallback:
    """覆盖 compile_with_model_fallback"""

    @pytest.mark.asyncio
    async def test_model_fallback_no_text(self):
        """无文本时返回 None"""
        from dochris.compensate.compensate_failures import compile_with_model_fallback

        result = await compile_with_model_fallback("", "title", MagicMock(), ["model1"], 0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_model_fallback_no_models(self):
        """无模型时返回 None"""
        from dochris.compensate.compensate_failures import compile_with_model_fallback

        result = await compile_with_model_fallback("some text", "title", MagicMock(), [], 0.1)
        assert result is None
