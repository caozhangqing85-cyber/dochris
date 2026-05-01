"""补充测试 summary_generator.py — 覆盖 json_repair 和 extract_json_from_text 路径"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dochris.core.summary_generator import SummaryGenerator


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.model = "test-model"
    client.max_tokens = 4000
    client.temperature = 0.7
    client.no_think = False
    client._rate_limit = AsyncMock()
    client._apply_no_think = MagicMock(side_effect=lambda msgs: msgs)
    client._extract_json_from_text = MagicMock(return_value=None)
    client.client = MagicMock()
    return client


@pytest.fixture
def generator(mock_llm_client):
    return SummaryGenerator(mock_llm_client)


def _make_response(content: str):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


class TestGenerateSummaryJsonRepair:
    """覆盖 JSON 解析失败 → json_repair → _extract_json_from_text 路径"""

    @pytest.mark.asyncio
    async def test_invalid_json_extract_from_text_fallback(self, generator, mock_llm_client):
        """json_repair 不可用时，使用 _extract_json_from_text 回退"""
        result_data = {"one_line": "extracted", "key_points": [], "detailed_summary": "", "concepts": []}
        mock_llm_client._extract_json_from_text.return_value = result_data

        resp = _make_response("not valid json at all")
        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=resp)

        # json_repair not importable
        with patch.dict("sys.modules", {"json_repair": None}):
            result = await generator.generate_summary("text", "title", max_retries=1)

        assert result is not None
        assert result["one_line"] == "extracted"
        mock_llm_client._extract_json_from_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_json_all_methods_fail(self, generator, mock_llm_client):
        """所有 JSON 解析方式都失败时抛出 ValueError，导致重试耗尽返回 None"""
        mock_llm_client._extract_json_from_text.return_value = None

        resp = _make_response("not json")
        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=resp)

        with patch.dict("sys.modules", {"json_repair": None}):
            result = await generator.generate_summary("text", "title", max_retries=1)

        assert result is None


class TestBuildMessagesFull:
    """覆盖 _build_messages 中通用模板的完整路径"""

    def test_default_template_includes_all_fields(self, generator, mock_llm_client):
        """通用模板包含所有必要字段说明"""
        mock_llm_client.no_think = False
        msgs = generator._build_messages("content text", "My Title")

        system_content = msgs[0]["content"]
        assert "one_line" in system_content
        assert "key_points" in system_content
        assert "detailed_summary" in system_content
        assert "concepts" in system_content

        user_content = msgs[1]["content"]
        assert "My Title" in user_content
        assert "content text" in user_content

    def test_qwen3_template_includes_all_fields(self, generator):
        """qwen3 模板包含所有字段"""
        msgs = generator._build_messages_qwen3("text content", "Qwen Title")

        system_content = msgs[0]["content"]
        assert "one_line" in system_content
        assert "key_points" in system_content
        assert "detailed_summary" in system_content
        assert "concepts" in system_content
        assert "知识工程师" in system_content

        user_content = msgs[1]["content"]
        assert "Qwen Title" in user_content
