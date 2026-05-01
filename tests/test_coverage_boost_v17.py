"""覆盖率提升 v17 — compensate/compensate_failures.py + compensate/compensate_extractors.py"""

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
