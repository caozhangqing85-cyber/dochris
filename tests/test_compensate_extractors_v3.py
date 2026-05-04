"""补充测试 compensate/compensate_extractors.py — 覆盖 PDF/doc/code 提取 + OCR 路径"""

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestExtractTextFromFilePDF:
    """覆盖 PDF 提取分支 - 延迟导入需 patch 实际模块"""

    def test_pdf_extraction_success(self, tmp_path):
        """PDF 成功提取文本"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF fake")
        mock_logger = MagicMock()

        with patch("dochris.parsers.pdf_parser.parse_pdf", return_value="PDF content here"):
            result = extract_text_from_file(pdf, mock_logger)

        assert result == "PDF content here"

    def test_pdf_extraction_empty(self, tmp_path):
        """PDF 提取返回空"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF fake")
        mock_logger = MagicMock()

        with patch("dochris.parsers.pdf_parser.parse_pdf", return_value=""):
            result = extract_text_from_file(pdf, mock_logger)

        assert result is None

    def test_pdf_unexpected_exception(self, tmp_path):
        """PDF 提取抛出未预期异常"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF fake")
        mock_logger = MagicMock()

        with patch("dochris.parsers.pdf_parser.parse_pdf", side_effect=Exception("unexpected")):
            result = extract_text_from_file(pdf, mock_logger)

        assert result is None

    def test_pdf_text_extraction_error(self, tmp_path):
        """PDF 提取抛出 TextExtractionError"""
        from dochris.compensate.compensate_extractors import extract_text_from_file
        from dochris.exceptions import TextExtractionError

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF fake")
        mock_logger = MagicMock()

        with patch("dochris.parsers.pdf_parser.parse_pdf", side_effect=TextExtractionError("fail")):
            result = extract_text_from_file(pdf, mock_logger)

        assert result is None


class TestExtractTextFromFileDoc:
    """覆盖文档提取分支"""

    def test_docx_extraction_success(self, tmp_path):
        """docx 成功提取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        doc = tmp_path / "test.docx"
        doc.write_bytes(b"fake docx")
        mock_logger = MagicMock()

        with patch("dochris.parsers.doc_parser.parse_document", return_value="doc content"):
            result = extract_text_from_file(doc, mock_logger)

        assert result == "doc content"

    def test_html_extraction_text_extraction_error(self, tmp_path):
        """HTML 提取抛出 TextExtractionError"""
        from dochris.compensate.compensate_extractors import extract_text_from_file
        from dochris.exceptions import TextExtractionError

        html = tmp_path / "test.html"
        html.write_text("<html>test</html>", encoding="utf-8")
        mock_logger = MagicMock()

        with patch(
            "dochris.parsers.doc_parser.parse_document", side_effect=TextExtractionError("fail")
        ):
            result = extract_text_from_file(html, mock_logger)

        assert result is None

    def test_docx_unexpected_exception(self, tmp_path):
        """docx 提取抛出未预期异常"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        doc = tmp_path / "test.docx"
        doc.write_bytes(b"fake")
        mock_logger = MagicMock()

        with patch("dochris.parsers.doc_parser.parse_document", side_effect=Exception("boom")):
            result = extract_text_from_file(doc, mock_logger)

        assert result is None


class TestExtractTextFromFileCode:
    """覆盖代码文件分支"""

    def test_code_file_read_success(self, tmp_path):
        """代码文件成功读取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        ts_file = tmp_path / "test.ts"
        ts_file.write_text("const x = 1;", encoding="utf-8")
        mock_logger = MagicMock()

        result = extract_text_from_file(ts_file, mock_logger)
        assert "const x = 1" in result

    def test_json_file_read_success(self, tmp_path):
        """JSON 文件成功读取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}', encoding="utf-8")
        mock_logger = MagicMock()

        result = extract_text_from_file(json_file, mock_logger)
        assert "key" in result

    def test_code_file_read_oserror(self, tmp_path):
        """代码文件读取失败"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        code_file = tmp_path / "test.py"
        code_file.write_text("print('hi')", encoding="utf-8")
        mock_logger = MagicMock()

        with patch.object(Path, "read_text", side_effect=OSError("no access")):
            result = extract_text_from_file(code_file, mock_logger)

        assert result is None


class TestExtractTextFromFileDefault:
    """覆盖默认分支"""

    def test_default_long_text(self, tmp_path):
        """默认分支：长文本被截断"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        txt = tmp_path / "test.rtf"
        txt.write_text("a" * 200, encoding="utf-8")
        mock_logger = MagicMock()

        result = extract_text_from_file(txt, mock_logger)
        assert result is not None

    def test_default_short_text_returns_none(self, tmp_path):
        """默认分支：短文本返回 None"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        txt = tmp_path / "test.log"
        txt.write_text("short", encoding="utf-8")
        mock_logger = MagicMock()

        result = extract_text_from_file(txt, mock_logger)
        assert result is None


class TestOCRPaths:
    """覆盖 extract_pdf_with_ocr 相关分支"""

    def test_ocr_no_text_layer_no_tesseract(self, tmp_path):
        """PDF 无文字层，tesseract 不可用"""
        from dochris.compensate.compensate_extractors import extract_pdf_with_ocr

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF fake")
        mock_logger = MagicMock()

        mock_fitz = MagicMock()
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.page_count = 1
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            with patch("subprocess.run", side_effect=FileNotFoundError("no tesseract")):
                result = extract_pdf_with_ocr(pdf, mock_logger)

        assert result is None

    def test_ocr_has_text_layer_skips(self, tmp_path):
        """PDF 有文字层时跳过 OCR"""
        from dochris.compensate.compensate_extractors import extract_pdf_with_ocr

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF fake")
        mock_logger = MagicMock()

        mock_fitz = MagicMock()
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "existing text"
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.page_count = 1
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            result = extract_pdf_with_ocr(pdf, mock_logger)

        assert result is None

    def test_ocr_pymupdf_check_fails(self, tmp_path):
        """PyMuPDF 检查失败时继续尝试 tesseract"""
        from dochris.compensate.compensate_extractors import extract_pdf_with_ocr

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF fake")
        mock_logger = MagicMock()

        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = RuntimeError("corrupt")

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            with patch("subprocess.run", side_effect=FileNotFoundError("no tesseract")):
                result = extract_pdf_with_ocr(pdf, mock_logger)

        assert result is None
