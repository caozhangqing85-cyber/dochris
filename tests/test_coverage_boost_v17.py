"""覆盖率提升 v17 — compensate/compensate_failures.py + compensate/compensate_extractors.py + llm_client + phase2 + quality_gate"""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# compensate/compensate_failures.py
# ============================================================
class TestExtractTextFromFile:
    def test_code_file(self, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        code = tmp_path / "test.py"
        code.write_text("print('hello world')", encoding="utf-8")
        logger = MagicMock()
        result = extract_text_from_file(code, logger)
        assert result == "print('hello world')"

    def test_code_file_js(self, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        js = tmp_path / "app.js"
        js.write_text("console.log('hi')", encoding="utf-8")
        logger = MagicMock()
        result = extract_text_from_file(js, logger)
        assert "console.log" in result

    def test_default_file_read(self, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        txt = tmp_path / "data.xyz"
        txt.write_text("x" * 200, encoding="utf-8")
        logger = MagicMock()
        result = extract_text_from_file(txt, logger)
        assert len(result) > 100

    def test_default_file_too_short(self, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        txt = tmp_path / "short.xyz"
        txt.write_text("hi", encoding="utf-8")
        logger = MagicMock()
        result = extract_text_from_file(txt, logger)
        assert result is None

    @patch("dochris.parsers.pdf_parser.parse_pdf")
    def test_pdf_success(self, mock_parse, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"fake pdf")
        mock_parse.return_value = "PDF content here"
        logger = MagicMock()
        result = extract_text_from_file(pdf, logger)
        assert "PDF content" in result

    @patch("dochris.parsers.pdf_parser.parse_pdf")
    def test_pdf_failure(self, mock_parse, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"bad pdf")
        mock_parse.side_effect = Exception("parse error")
        logger = MagicMock()
        result = extract_text_from_file(pdf, logger)
        assert result is None

    @patch("dochris.parsers.doc_parser.parse_document")
    def test_docx_success(self, mock_parse, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        doc = tmp_path / "test.docx"
        doc.write_bytes(b"fake docx")
        mock_parse.return_value = "Document content"
        logger = MagicMock()
        result = extract_text_from_file(doc, logger)
        assert "Document content" in result

    @patch("dochris.parsers.doc_parser.parse_document")
    def test_docx_failure(self, mock_parse, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        doc = tmp_path / "bad.docx"
        doc.write_bytes(b"bad")
        mock_parse.side_effect = Exception("doc error")
        logger = MagicMock()
        result = extract_text_from_file(doc, logger)
        assert result is None

    def test_code_read_error(self, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        py = tmp_path / "unreadable.py"
        py.write_text("content", encoding="utf-8")
        logger = MagicMock()
        with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            result = extract_text_from_file(py, logger)
        assert result is None

    def test_default_read_error(self, tmp_path):
        from dochris.compensate.compensate_failures import extract_text_from_file

        xyz = tmp_path / "data.xyz"
        xyz.write_text("x" * 200, encoding="utf-8")
        logger = MagicMock()
        with patch.object(Path, "read_text", side_effect=OSError("fail")):
            result = extract_text_from_file(xyz, logger)
        assert result is None


class TestGenerateSummaryWithLLM:
    @pytest.mark.asyncio
    async def test_no_api_key(self):
        from dochris.compensate.compensate_failures import generate_summary_with_llm

        mock_settings = MagicMock()
        mock_settings.api_key = None
        logger = MagicMock()

        with patch("dochris.compensate.compensate_failures.get_settings", return_value=mock_settings):
            result = await generate_summary_with_llm("text", "title", logger)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_success(self):
        from dochris.compensate.compensate_failures import generate_summary_with_llm

        mock_settings = MagicMock()
        mock_settings.api_key = "test-key"
        mock_settings.api_base = "http://test"
        mock_settings.model = "test-model"
        logger = MagicMock()

        mock_client = MagicMock()
        mock_client.generate_summary = AsyncMock(return_value={"summary": "test"})

        with patch("dochris.settings.get_settings", return_value=mock_settings), \
             patch("dochris.core.llm_client.LLMClient", return_value=mock_client):
            result = await generate_summary_with_llm("text", "title", logger)
        assert result == {"summary": "test"}

    @pytest.mark.asyncio
    async def test_llm_exception(self):
        from dochris.compensate.compensate_failures import generate_summary_with_llm

        mock_settings = MagicMock()
        mock_settings.api_key = "test-key"
        mock_settings.api_base = "http://test"
        mock_settings.model = "test-model"
        logger = MagicMock()

        mock_client = MagicMock()
        mock_client.generate_summary = AsyncMock(side_effect=Exception("LLM error"))

        with patch("dochris.settings.get_settings", return_value=mock_settings), \
             patch("dochris.core.llm_client.LLMClient", return_value=mock_client):
            result = await generate_summary_with_llm("text", "title", logger)
        assert result is None


class TestCompileWithModelFallback:
    @pytest.mark.asyncio
    async def test_no_api_key(self):
        from dochris.compensate.compensate_failures import compile_with_model_fallback

        mock_settings = MagicMock()
        mock_settings.api_key = None
        logger = MagicMock()

        with patch("dochris.compensate.compensate_failures.get_settings", return_value=mock_settings):
            result = await compile_with_model_fallback("text", "title", logger, ["m1", "m2"], 0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_first_model_succeeds(self):
        from dochris.compensate.compensate_failures import compile_with_model_fallback

        mock_settings = MagicMock()
        mock_settings.api_key = "test-key"
        mock_settings.api_base = "http://test"
        logger = MagicMock()

        mock_client = MagicMock()
        mock_client.generate_summary = AsyncMock(return_value={"summary": "ok"})

        with patch("dochris.settings.get_settings", return_value=mock_settings), \
             patch("dochris.core.llm_client.LLMClient", return_value=mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await compile_with_model_fallback("text", "title", logger, ["model-a"], 0.1)
        assert result == {"summary": "ok"}

    @pytest.mark.asyncio
    async def test_fallback_to_second_model(self):
        from dochris.compensate.compensate_failures import compile_with_model_fallback

        mock_settings = MagicMock()
        mock_settings.api_key = "test-key"
        mock_settings.api_base = "http://test"
        logger = MagicMock()

        call_count = 0

        def make_client(**kwargs):
            nonlocal call_count
            call_count += 1
            c = MagicMock()
            if call_count == 1:
                c.generate_summary = AsyncMock(side_effect=RuntimeError("fail"))
            else:
                c.generate_summary = AsyncMock(return_value={"summary": "fallback"})
            return c

        with patch("dochris.settings.get_settings", return_value=mock_settings), \
             patch("dochris.core.llm_client.LLMClient", side_effect=make_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await compile_with_model_fallback(
                "text", "title", logger, ["model-a", "model-b"], 0.1
            )
        assert result == {"summary": "fallback"}

    @pytest.mark.asyncio
    async def test_all_models_fail(self):
        from dochris.compensate.compensate_failures import compile_with_model_fallback

        mock_settings = MagicMock()
        mock_settings.api_key = "test-key"
        mock_settings.api_base = "http://test"
        logger = MagicMock()

        mock_client = MagicMock()
        mock_client.generate_summary = AsyncMock(side_effect=RuntimeError("all fail"))

        with patch("dochris.settings.get_settings", return_value=mock_settings), \
             patch("dochris.core.llm_client.LLMClient", return_value=mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await compile_with_model_fallback(
                "text", "title", logger, ["m1", "m2"], 0.1
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_model_returns_none(self):
        from dochris.compensate.compensate_failures import compile_with_model_fallback

        mock_settings = MagicMock()
        mock_settings.api_key = "test-key"
        mock_settings.api_base = "http://test"
        logger = MagicMock()

        mock_client = MagicMock()
        mock_client.generate_summary = AsyncMock(return_value=None)

        with patch("dochris.settings.get_settings", return_value=mock_settings), \
             patch("dochris.core.llm_client.LLMClient", return_value=mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await compile_with_model_fallback(
                "text", "title", logger, ["m1"], 0.1
            )
        assert result is None


class TestFindFailedManifests:
    def _make_cf(self):
        from dochris.compensate import compensate_failures as cf
        return cf

    def test_filter_ebook(self, tmp_path):
        cf = self._make_cf()
        # Create the .mobi file so the extension check passes
        ebook_dir = tmp_path / "raw" / "ebooks"
        ebook_dir.mkdir(parents=True)
        (ebook_dir / "test.mobi").write_bytes(b"fake mobi")

        manifests = [
            {"id": "SRC-0001", "type": "ebook", "file_path": "raw/ebooks/test.mobi",
             "error_message": "no_text", "title": "Test"},
            {"id": "SRC-0002", "type": "pdf", "file_path": "raw/pdfs/test.pdf",
             "error_message": "no_text", "title": "PDF"},
        ]
        logger = MagicMock()
        with patch.object(cf, "KB_PATH", tmp_path), \
             patch("dochris.compensate.compensate_failures.get_all_manifests", return_value=manifests):
            result = cf.find_failed_manifests("ebook", logger)
        assert len(result) == 1
        assert result[0]["id"] == "SRC-0001"

    def test_filter_pdf(self, tmp_path):
        cf = self._make_cf()
        # Create the pdf files
        pdf_dir = tmp_path / "raw" / "pdfs"
        pdf_dir.mkdir(parents=True)
        (pdf_dir / "test.pdf").write_bytes(b"fake pdf")
        (pdf_dir / "test2.pdf").write_bytes(b"fake pdf 2")

        manifests = [
            {"id": "SRC-0001", "type": "pdf", "file_path": "raw/pdfs/test.pdf",
             "error_message": "no_text", "title": "Test"},
            {"id": "SRC-0002", "type": "pdf", "file_path": "raw/pdfs/test2.pdf",
             "error_message": "llm_failed", "title": "Test2"},
        ]
        logger = MagicMock()
        with patch.object(cf, "KB_PATH", tmp_path), \
             patch("dochris.compensate.compensate_failures.get_all_manifests", return_value=manifests):
            result = cf.find_failed_manifests("pdf", logger)
        assert len(result) == 1

    def test_filter_llm(self, tmp_path):
        cf = self._make_cf()
        manifests = [
            {"id": "SRC-0001", "type": "pdf", "file_path": "raw/pdfs/test.pdf",
             "error_message": "llm_failed: timeout", "title": "Test"},
        ]
        logger = MagicMock()
        with patch.object(cf, "KB_PATH", tmp_path), \
             patch("dochris.compensate.compensate_failures.get_all_manifests", return_value=manifests):
            result = cf.find_failed_manifests("llm", logger)
        assert len(result) == 1

    def test_filter_other(self, tmp_path):
        cf = self._make_cf()
        manifests = [
            {"id": "SRC-0001", "type": "other", "file_path": "raw/other/test.mhtml",
             "error_message": "no_text", "title": "Test"},
        ]
        other_dir = tmp_path / "raw" / "other"
        other_dir.mkdir(parents=True)
        (other_dir / "test.mhtml").write_text("content", encoding="utf-8")

        logger = MagicMock()
        with patch.object(cf, "KB_PATH", tmp_path), \
             patch("dochris.compensate.compensate_failures.get_all_manifests", return_value=manifests):
            result = cf.find_failed_manifests("other", logger)
        assert len(result) == 1

    def test_filter_all(self, tmp_path):
        cf = self._make_cf()
        manifests = [
            {"id": "SRC-0001", "type": "pdf", "file_path": "raw/pdfs/test.pdf",
             "error_message": "no_text", "title": "Test"},
            {"id": "SRC-0002", "type": "pdf", "file_path": "raw/pdfs/test2.pdf",
             "error_message": "llm_failed", "title": "Test2"},
        ]
        logger = MagicMock()
        with patch.object(cf, "KB_PATH", tmp_path), \
             patch("dochris.compensate.compensate_failures.get_all_manifests", return_value=manifests):
            result = cf.find_failed_manifests("all", logger)
        assert len(result) == 2

    def test_filter_empty(self, tmp_path):
        cf = self._make_cf()
        logger = MagicMock()
        with patch.object(cf, "KB_PATH", tmp_path), \
             patch("dochris.compensate.compensate_failures.get_all_manifests", return_value=[]):
            result = cf.find_failed_manifests("all", logger)
        assert result == []


class TestRunCompensate:
    @pytest.mark.asyncio
    async def test_no_manifests(self, tmp_path):
        from dochris.compensate import compensate_failures as cf

        logger = MagicMock()
        with patch.object(cf, "KB_PATH", tmp_path), \
             patch("dochris.compensate.compensate_failures.find_failed_manifests", return_value=[]):
            await cf.run_compensate(logger, "all")

    @pytest.mark.asyncio
    async def test_no_api_key(self, tmp_path, monkeypatch):
        from dochris.compensate import compensate_failures as cf

        logger = MagicMock()
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        mock_settings = MagicMock()
        mock_settings.api_key = None

        with patch.object(cf, "KB_PATH", tmp_path), \
             patch("dochris.compensate.compensate_failures.find_failed_manifests",
                   return_value=[{"id": "S1", "type": "pdf"}]), \
             patch("dochris.compensate.compensate_failures.get_settings", return_value=mock_settings):
            await cf.run_compensate(logger, "all")


class TestRetryLLMFailed:
    @pytest.mark.asyncio
    async def test_file_not_found(self, tmp_path):
        from dochris.compensate.compensate_failures import retry_llm_failed

        manifest = {"id": "SRC-0001", "file_path": "raw/nonexistent.pdf", "title": "Missing"}
        logger = MagicMock()
        with patch("dochris.compensate.compensate_failures.KB_PATH", tmp_path):
            src_id, ok, status, comp = await retry_llm_failed(
                manifest, None, logger, 0.1, ["model-a"]
            )
        assert ok is False
        assert status == "file_not_found"

    @pytest.mark.asyncio
    async def test_no_text(self, tmp_path):
        from dochris.compensate.compensate_failures import retry_llm_failed

        raw = tmp_path / "raw"
        raw.mkdir()
        f = raw / "test.txt"
        f.write_text("hi", encoding="utf-8")

        manifest = {"id": "SRC-0001", "file_path": "raw/test.txt", "title": "Test"}
        logger = MagicMock()

        with patch("dochris.compensate.compensate_failures.KB_PATH", tmp_path), \
             patch("dochris.compensate.compensate_failures.MIN_AUDIO_TEXT_LENGTH", 100):
            src_id, ok, status, comp = await retry_llm_failed(
                manifest, None, logger, 0.1, ["m1"]
            )
        assert ok is False
        assert status == "no_text"


class TestCompensateSingle:
    @pytest.mark.asyncio
    async def test_file_not_found(self, tmp_path):
        from dochris.compensate.compensate_failures import compensate_single

        manifest = {"id": "SRC-0001", "file_path": "raw/nonexistent.pdf", "title": "Missing", "type": "pdf"}
        logger = MagicMock()
        sem = MagicMock()
        sem.__aenter__ = AsyncMock(return_value=None)
        sem.__aexit__ = AsyncMock(return_value=None)

        with patch("dochris.compensate.compensate_failures.KB_PATH", tmp_path):
            src_id, ok, status, comp = await compensate_single(
                manifest, logger, sem, 0.1, ["m1"], "all"
            )
        assert ok is False
        assert status == "file_not_found"


# ============================================================
# compensate/compensate_extractors.py — partial coverage
# ============================================================
class TestCompensateExtractors:
    def test_extract_text_compensated_nonexistent(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_compensated

        logger = MagicMock()
        result, method = extract_text_compensated(tmp_path / "nonexistent.xyz", {"type": "other"}, logger)
        assert result is None or result == ""


# ============================================================
# core/llm_client.py — init, close, cleanup, rate_limit, delegates
# ============================================================
class TestLLMClientInit:
    """测试 LLMClient 初始化和基本方法"""

    def test_init_openai_compat(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(
                api_key="test-key",
                base_url="https://api.test.com",
                model="glm-5.1",
                provider="openai_compat",
            )
            assert client.model == "glm-5.1"
            assert client.temperature == 0.1
            assert client.no_think is False

    def test_init_default_provider(self):
        """provider=None 默认使用 openai_compat"""
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            assert client.model == "glm-5.1"

    def test_init_qwen3_model(self):
        """qwen3 模型自动启用 no_think"""
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test", model="qwen3-32b")
            assert client.no_think is True

    def test_init_non_openai_compat(self):
        """非 openai_compat provider 创建兼容 client"""
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock(spec=[])  # no .client attribute
            mock_get.return_value = MagicMock(return_value=mock_provider)

            with patch("dochris.core.llm_client.AsyncOpenAI") as mock_ao:
                mock_ao.return_value = MagicMock()
                with patch("httpx.AsyncClient"):
                    with patch("httpx.Limits"):
                        client = LLMClient(
                            api_key="k",
                            base_url="http://test",
                            provider="ollama",
                        )
                        assert client.model == "glm-5.1"

    def test_apply_no_think_true(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test", model="qwen3-test")
            messages = [{"role": "system", "content": "test"}]
            result = client._apply_no_think(messages)
            assert "/no_think" in result[0]["content"]

    def test_apply_no_think_false(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            messages = [{"role": "system", "content": "test"}]
            result = client._apply_no_think(messages)
            assert "/no_think" not in result[0]["content"]

    @pytest.mark.asyncio
    async def test_close(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.close = AsyncMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            client.client = MagicMock()
            client.client.close = AsyncMock()

            await client.close()
            mock_provider.close.assert_called_once()
            client.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.close = AsyncMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            client.client = MagicMock()
            client.client.close = AsyncMock()

            async with client as c:
                assert c is client

    @pytest.mark.asyncio
    async def test_rate_limit_no_wait(self):
        """不需要等待时的 rate_limit"""
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test", request_delay=0.0)
            await client._rate_limit()

    @pytest.mark.asyncio
    async def test_rate_limit_with_wait(self):
        """需要等待时的 rate_limit"""
        from dochris.core.llm_client import LLMClient
        import time

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test", request_delay=10.0)
            client.last_request_time = time.time()

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await client._rate_limit()
                mock_sleep.assert_called_once()

    def test_extract_json_nested(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            result = client._extract_json_from_text('prefix {"a": {"b": 2}} suffix')
            assert result == {"a": {"b": 2}}

    def test_extract_json_no_json(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            result = client._extract_json_from_text("no json here")
            assert result is None

    def test_summary_generator_property(self):
        """延迟导入 SummaryGenerator"""
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            sg = client._summary_generator
            assert sg is not None
            assert client._summary_generator is sg

    def test_hierarchical_summarizer_property(self):
        """延迟导入 HierarchicalSummarizer"""
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            hs = client._hierarchical_summarizer
            assert hs is not None
            assert client._hierarchical_summarizer is hs

    @pytest.mark.asyncio
    async def test_generate_summary_delegates(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            mock_sg = MagicMock()
            mock_sg.generate_summary = AsyncMock(return_value={"one_line": "test"})
            client._summary_generator_instance = mock_sg

            result = await client.generate_summary("text", "title")
            assert result == {"one_line": "test"}

    @pytest.mark.asyncio
    async def test_generate_summary_smart_delegates(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            mock_sg = MagicMock()
            mock_sg.generate_summary_smart = AsyncMock(return_value={"one_line": "smart"})
            client._summary_generator_instance = mock_sg

            result = await client.generate_summary_smart("text", "title")
            assert result == {"one_line": "smart"}

    @pytest.mark.asyncio
    async def test_generate_map_reduce_delegates(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            mock_hs = MagicMock()
            mock_hs.generate_map_reduce_summary = AsyncMock(return_value={"one_line": "mr"})
            client._hierarchical_summarizer_instance = mock_hs

            result = await client.generate_map_reduce_summary("text", "title")
            assert result == {"one_line": "mr"}

    @pytest.mark.asyncio
    async def test_generate_hierarchical_delegates(self):
        from dochris.core.llm_client import LLMClient

        with patch("dochris.llm.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.client = MagicMock()
            mock_get.return_value = MagicMock(return_value=mock_provider)

            client = LLMClient(api_key="k", base_url="http://test")
            mock_hs = MagicMock()
            mock_hs.generate_hierarchical_summary = AsyncMock(return_value={"one_line": "hi"})
            client._hierarchical_summarizer_instance = mock_hs

            result = await client.generate_hierarchical_summary("text", "title")
            assert result == {"one_line": "hi"}


class TestCleanupClients:
    """测试 cleanup_all_clients 函数"""

    def test_cleanup_empty(self):
        from dochris.core.llm_client import cleanup_all_clients, _client_instances

        _client_instances.clear()
        cleanup_all_clients()

    def test_cleanup_with_clients(self):
        from dochris.core.llm_client import cleanup_all_clients, _client_instances

        _client_instances.clear()

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        _client_instances.append(mock_client)

        cleanup_all_clients()
        assert len(_client_instances) == 0

    def test_cleanup_runtime_error(self):
        """事件循环冲突时的清理"""
        from dochris.core.llm_client import cleanup_all_clients, _client_instances

        _client_instances.clear()

        mock_client = MagicMock()
        _client_instances.append(mock_client)

        with patch("asyncio.run", side_effect=RuntimeError("loop running")):
            cleanup_all_clients()

        assert len(_client_instances) == 0


# ============================================================
# phases/phase2_compilation.py — dry_run + non-tty batch
# ============================================================
class TestPhase2DryRun:
    """测试 phase2_compilation 的 dry_run 模式"""

    @pytest.mark.asyncio
    async def test_compile_all_dry_run(self, tmp_path):
        from dochris.phases.phase2_compilation import compile_all

        manifests = [
            {"id": "SRC-0001", "title": "Test Doc", "size_bytes": 150000},
            {"id": "SRC-0002", "title": "Small Doc", "size_bytes": 30000},
            {"id": "SRC-0003", "title": "Tiny Doc", "size_bytes": 1000},
        ]

        with patch("dochris.phases.phase2_compilation.get_default_workspace", return_value=tmp_path), \
             patch("dochris.phases.phase2_compilation.get_all_manifests", return_value=manifests), \
             patch("dochris.phases.phase2_compilation.get_logs_dir", return_value=tmp_path / "logs"):
            await compile_all(dry_run=True)

    @pytest.mark.asyncio
    async def test_compile_all_no_manifests(self, tmp_path):
        from dochris.phases.phase2_compilation import compile_all

        with patch("dochris.phases.phase2_compilation.get_default_workspace", return_value=tmp_path), \
             patch("dochris.phases.phase2_compilation.get_all_manifests", return_value=[]), \
             patch("dochris.phases.phase2_compilation.get_logs_dir", return_value=tmp_path / "logs"):
            await compile_all()

    @pytest.mark.asyncio
    async def test_compile_all_with_limit(self, tmp_path):
        from dochris.phases.phase2_compilation import compile_all

        manifests = [
            {"id": "SRC-0001", "title": "Doc1", "size_bytes": 1000},
            {"id": "SRC-0002", "title": "Doc2", "size_bytes": 1000},
        ]

        with patch("dochris.phases.phase2_compilation.get_default_workspace", return_value=tmp_path), \
             patch("dochris.phases.phase2_compilation.get_all_manifests", return_value=manifests), \
             patch("dochris.phases.phase2_compilation.get_logs_dir", return_value=tmp_path / "logs"):
            await compile_all(dry_run=True, limit=1)


# ============================================================
# quality/quality_gate.py — CLI main + scan_wiki report
# ============================================================
class TestQualityGateCLI:
    """测试 quality_gate.py 的 CLI 入口"""

    def test_main_no_args(self):
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["quality_gate.py"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_scan_wiki(self, tmp_path):
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "scan-wiki"]), \
             patch("dochris.quality.quality_gate.scan_wiki", return_value={
                 "wiki_summaries": 5,
                 "wiki_concepts": 3,
                 "wiki_total": 8,
                 "pollution": {"polluted": False, "details": "干净"},
                 "manifest_status_counts": {"compiled": 5, "pending": 2},
             }):
            main()

    def test_main_report(self, tmp_path):
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "report"]), \
             patch("dochris.quality.quality_gate.generate_report", return_value={"total": 10}):
            main()

    def test_main_unknown_command(self, tmp_path):
        from dochris.quality.quality_gate import main

        with patch("sys.argv", ["quality_gate.py", str(tmp_path), "unknown"]), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


# ============================================================
# compensate/compensate_extractors.py — 更多覆盖
# ============================================================
class TestExtractTextFromFileExtra:
    """补充 compensate_extractors.py 的覆盖"""

    def test_pdf_extraction_failure(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file
        from dochris.exceptions import TextExtractionError

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf")
        logger = MagicMock()

        with patch("dochris.parsers.pdf_parser.parse_pdf", side_effect=TextExtractionError("fail")):
            result = extract_text_from_file(pdf_file, logger)
            assert result is None

    def test_pdf_unexpected_error(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf")
        logger = MagicMock()

        with patch("dochris.parsers.pdf_parser.parse_pdf", side_effect=RuntimeError("unexpected")):
            result = extract_text_from_file(pdf_file, logger)
            assert result is None

    def test_document_extraction_failure(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file
        from dochris.exceptions import TextExtractionError

        doc_file = tmp_path / "test.md"
        doc_file.write_text("x" * 200, encoding="utf-8")
        logger = MagicMock()

        with patch("dochris.parsers.doc_parser.parse_document", side_effect=TextExtractionError("fail")):
            result = extract_text_from_file(doc_file, logger)
            assert result is None

    def test_document_unexpected_error(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        doc_file = tmp_path / "test.txt"
        doc_file.write_text("x" * 200, encoding="utf-8")
        logger = MagicMock()

        with patch("dochris.parsers.doc_parser.parse_document", side_effect=RuntimeError("unexpected")):
            result = extract_text_from_file(doc_file, logger)
            assert result is None

    def test_code_file_unicode_error(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        code_file = tmp_path / "test.py"
        code_file.write_text("valid", encoding="utf-8")
        logger = MagicMock()

        with patch.object(Path, "read_text", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "bad")):
            result = extract_text_from_file(code_file, logger)
            assert result is None

    def test_default_fallback_short_text(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        misc_file = tmp_path / "test.xyz"
        misc_file.write_text("short", encoding="utf-8")
        logger = MagicMock()

        result = extract_text_from_file(misc_file, logger)
        assert result is None

    def test_default_fallback_read_error(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        misc_file = tmp_path / "test.xyz"
        logger = MagicMock()

        with patch.object(Path, "read_text", side_effect=OSError("error")):
            result = extract_text_from_file(misc_file, logger)
            assert result is None


class TestExtractEbookExtra:
    """补充 ebook 提取覆盖"""

    def test_convert_empty_result(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_ebook_text

        ebook = tmp_path / "test.epub"
        ebook.write_bytes(b"fake epub")
        logger = MagicMock()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            with patch.object(Path, "read_text", return_value="  "):
                result = extract_ebook_text(ebook, logger)
                assert result is None

    def test_convert_timeout(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_ebook_text

        ebook = tmp_path / "test.azw3"
        ebook.write_bytes(b"fake azw3")
        logger = MagicMock()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
            result = extract_ebook_text(ebook, logger)
            assert result is None

    def test_convert_os_error(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_ebook_text

        ebook = tmp_path / "test.mobi"
        ebook.write_bytes(b"fake mobi")
        logger = MagicMock()

        with patch("subprocess.run", side_effect=FileNotFoundError("no cmd")):
            result = extract_ebook_text(ebook, logger)
            assert result is None


class TestExtractPdfWithOcrExtra:
    """补充 PDF OCR 提取覆盖"""

    def test_fitz_not_installed(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_pdf_with_ocr

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF fake")
        logger = MagicMock()

        with patch.dict("sys.modules", {"fitz": None}):
            result = extract_pdf_with_ocr(pdf, logger)
            assert result is None


class TestExtractTextCompensatedExtra:
    """补充补偿文本提取覆盖"""

    def test_ebook_fallback(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_compensated

        file = tmp_path / "test.mobi"
        file.write_bytes(b"fake")
        logger = MagicMock()

        with patch("dochris.compensate.compensate_extractors.extract_text_from_file", return_value=None), \
             patch("dochris.compensate.compensate_extractors.extract_ebook_text", return_value="A" * 500):
            text, method = extract_text_compensated(file, {"type": "ebook"}, logger)
            assert method == "ebook_convert"

    def test_ocr_fallback(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_compensated

        file = tmp_path / "test.pdf"
        file.write_bytes(b"fake")
        logger = MagicMock()

        with patch("dochris.compensate.compensate_extractors.extract_text_from_file", return_value=None), \
             patch("dochris.compensate.compensate_extractors.extract_pdf_with_ocr", return_value="A" * 500):
            text, method = extract_text_compensated(file, {"type": "pdf"}, logger)
            assert method == "ocr"

    def test_markitdown_fallback(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_compensated

        file = tmp_path / "test.mhtml"
        file.write_bytes(b"fake")
        logger = MagicMock()

        with patch("dochris.compensate.compensate_extractors.extract_text_from_file", return_value=None), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="A" * 500)
            text, method = extract_text_compensated(file, {"type": "other"}, logger)
            assert method == "markitdown"

    def test_all_fail(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_compensated

        file = tmp_path / "test.xyz"
        file.write_bytes(b"fake")
        logger = MagicMock()

        with patch("dochris.compensate.compensate_extractors.extract_text_from_file", return_value=None):
            text, method = extract_text_compensated(file, {"type": "unknown"}, logger)
            assert text is None
            assert method == "failed"

    def test_markitdown_fallback_failure(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_compensated

        file = tmp_path / "test.pptx"
        file.write_bytes(b"fake")
        logger = MagicMock()

        with patch("dochris.compensate.compensate_extractors.extract_text_from_file", return_value=None), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
            text, method = extract_text_compensated(file, {"type": "other"}, logger)
            assert text is None
            assert method == "failed"
