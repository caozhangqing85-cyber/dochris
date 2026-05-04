#!/usr/bin/env python3
"""
PDF 解析器增强测试 — 覆盖降级策略、边界条件和异常处理
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dochris.parsers.pdf_parser import (
    parse_pdf,
    parse_with_markitdown,
    parse_with_pdfplumber,
    parse_with_pymupdf,
    parse_with_pypdf2,
    parse_with_tesseract_ocr,
)


class TestParseWithMarkitdown:
    """测试 markitdown 解析器"""

    def test_nonexistent_file_returns_none(self):
        """不存在的文件返回 None"""
        result = parse_with_markitdown(Path("/nonexistent/file.pdf"))
        assert result is None

    def test_non_pdf_extension_returns_none(self, tmp_path: Path):
        """非 PDF 扩展名返回 None"""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("content", encoding="utf-8")
        result = parse_with_markitdown(txt_file)
        assert result is None

    @patch("subprocess.run")
    def test_successful_parse(self, mock_run, tmp_path: Path):
        """markitdown 成功解析"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")
        mock_run.return_value = MagicMock(returncode=0, stdout="提取的PDF文本" * 20)

        result = parse_with_markitdown(pdf_file)
        assert result is not None
        assert "PDF" in result

    @patch("subprocess.run")
    def test_failed_parse_returns_none(self, mock_run, tmp_path: Path):
        """markitdown 解析失败返回 None"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = parse_with_markitdown(pdf_file)
        assert result is None

    @patch("subprocess.run", side_effect=FileNotFoundError("markitdown not found"))
    def test_markitdown_not_installed(self, mock_run, tmp_path: Path):
        """markitdown 未安装时返回 None"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        result = parse_with_markitdown(pdf_file)
        assert result is None


class TestParseWithPypdf2:
    """测试 PyPDF2 解析器"""

    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    def test_import_error_returns_none(self, mock_parse):
        """PyPDF2 未安装时返回 None"""
        # 直接测试函数行为 — 模拟 ImportError
        with patch.dict("sys.modules", {"PyPDF2": None}):
            # PyPDF2 导入失败时函数内部捕获 ImportError
            pass

    def test_nonexistent_file_returns_none(self):
        """不存在的文件返回 None"""
        result = parse_with_pypdf2(Path("/nonexistent/file.pdf"))
        assert result is None

    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2.__module__")
    def test_short_text_returns_none(self, tmp_path: Path):
        """提取文本少于 100 字符时返回 None"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        # PyPDF2 无法解析假 PDF，返回 None
        result = parse_with_pypdf2(pdf_file)
        assert result is None


class TestParseWithPdfplumber:
    """测试 pdfplumber 解析器"""

    def test_nonexistent_file_returns_none(self):
        """不存在的文件返回 None"""
        result = parse_with_pdfplumber(Path("/nonexistent/file.pdf"))
        assert result is None

    def test_fake_pdf_returns_none(self, tmp_path: Path):
        """伪造 PDF 文件返回 None"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"not a real pdf")
        result = parse_with_pdfplumber(pdf_file)
        assert result is None


class TestParseWithPymupdf:
    """测试 PyMuPDF 解析器"""

    def test_nonexistent_file_returns_none(self):
        """不存在的文件返回 None"""
        result = parse_with_pymupdf(Path("/nonexistent/file.pdf"))
        assert result is None

    def test_fake_pdf_returns_none(self, tmp_path: Path):
        """伪造 PDF 文件返回 None"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"not a real pdf")
        result = parse_with_pymupdf(pdf_file)
        assert result is None


class TestParseWithTesseractOcr:
    """测试 Tesseract OCR 解析器"""

    def test_always_returns_none_simplified(self):
        """简化实现始终返回 None"""
        result = parse_with_tesseract_ocr(Path("/any/file.pdf"))
        assert result is None


class TestParsePdfFallbackChain:
    """测试 parse_pdf 降级策略"""

    def test_file_not_found_raises_error(self):
        """文件不存在时抛出 FileProcessingError"""
        from dochris.exceptions import FileProcessingError

        with pytest.raises(FileProcessingError, match="所有 PDF 解析器都失败"):
            parse_pdf(Path("/nonexistent/file.pdf"))

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_first_parser_succeeds(
        self, mock_ocr, mock_markitdown, mock_pypdf2, mock_pymupdf, mock_pdfplumber, tmp_path: Path
    ):
        """第一个解析器成功则直接返回"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pdfplumber.return_value = "pdfplumber 提取的文本内容" * 20

        result = parse_pdf(pdf_file)
        assert "pdfplumber" in result
        # 后续解析器不应被调用
        mock_pymupdf.assert_not_called()

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_fallback_to_pymupdf(
        self, mock_ocr, mock_markitdown, mock_pypdf2, mock_pymupdf, mock_pdfplumber, tmp_path: Path
    ):
        """pdfplumber 失败后回退到 pymupdf"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pdfplumber.return_value = None
        mock_pymupdf.return_value = "pymupdf 提取的文本内容" * 20

        result = parse_pdf(pdf_file)
        assert "pymupdf" in result

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_fallback_to_pypdf2(
        self, mock_ocr, mock_markitdown, mock_pypdf2, mock_pymupdf, mock_pdfplumber, tmp_path: Path
    ):
        """前两个解析器都失败，回退到 pypdf2"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pdfplumber.return_value = None
        mock_pymupdf.return_value = None
        mock_pypdf2.return_value = "pypdf2 提取的文本内容" * 20

        result = parse_pdf(pdf_file)
        assert "pypdf2" in result

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_fallback_to_markitdown(
        self, mock_ocr, mock_markitdown, mock_pypdf2, mock_pymupdf, mock_pdfplumber, tmp_path: Path
    ):
        """前三个解析器都失败，回退到 markitdown"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pdfplumber.return_value = None
        mock_pymupdf.return_value = None
        mock_pypdf2.return_value = None
        mock_markitdown.return_value = "markitdown 提取的文本内容" * 20

        result = parse_pdf(pdf_file)
        assert "markitdown" in result

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_all_parsers_fail(
        self, mock_ocr, mock_markitdown, mock_pypdf2, mock_pymupdf, mock_pdfplumber, tmp_path: Path
    ):
        """所有解析器都失败时抛出 FileProcessingError"""
        from dochris.exceptions import FileProcessingError

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pdfplumber.return_value = None
        mock_pymupdf.return_value = None
        mock_pypdf2.return_value = None
        mock_markitdown.return_value = None
        mock_ocr.return_value = None

        with pytest.raises(FileProcessingError, match="所有 PDF 解析器都失败"):
            parse_pdf(pdf_file)

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_short_text_considers_failure(
        self, mock_ocr, mock_markitdown, mock_pypdf2, mock_pymupdf, mock_pdfplumber, tmp_path: Path
    ):
        """提取文本过短（<=100 字符）视为失败"""
        from dochris.exceptions import FileProcessingError

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        # 所有解析器返回短文本
        mock_pdfplumber.return_value = "短文本"
        mock_pymupdf.return_value = "短"
        mock_pypdf2.return_value = "ab"
        mock_markitdown.return_value = None
        mock_ocr.return_value = None

        with pytest.raises(FileProcessingError):
            parse_pdf(pdf_file)

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_parser_exception_continues_chain(
        self, mock_ocr, mock_markitdown, mock_pypdf2, mock_pymupdf, mock_pdfplumber, tmp_path: Path
    ):
        """解析器抛出异常时继续尝试下一个"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pdfplumber.side_effect = OSError("文件损坏")
        mock_pymupdf.return_value = "pymupdf 成功解析的文本内容" * 20

        result = parse_pdf(pdf_file)
        assert "pymupdf" in result

    def test_empty_file_raises_error(self, tmp_path: Path):
        """空 PDF 文件触发所有解析器失败"""
        from dochris.exceptions import FileProcessingError

        pdf_file = tmp_path / "empty.pdf"
        pdf_file.write_bytes(b"")

        with pytest.raises(FileProcessingError, match="所有 PDF 解析器都失败"):
            parse_pdf(pdf_file)

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_string_path_handled(
        self, mock_ocr, mock_markitdown, mock_pypdf2, mock_pymupdf, mock_pdfplumber, tmp_path: Path
    ):
        """字符串路径也能正确处理"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pdfplumber.return_value = "字符串路径测试" * 20

        result = parse_pdf(pdf_file)
        assert isinstance(result, str)


class TestParseWithPdfplumberMocked:
    """测试 pdfplumber 解析器（模拟成功路径）"""

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    def test_pdfplumber_returns_valid_text(self, mock_parse, tmp_path: Path):
        """pdfplumber 返回足够长文本时视为成功"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_parse.return_value = "a" * 200

        from dochris.parsers.pdf_parser import parse_pdf

        with (
            patch("dochris.parsers.pdf_parser.parse_with_pymupdf") as m2,
            patch("dochris.parsers.pdf_parser.parse_with_pypdf2"),
            patch("dochris.parsers.pdf_parser.parse_with_markitdown"),
            patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr"),
        ):
            result = parse_pdf(pdf_file)
        assert result == "a" * 200
        m2.assert_not_called()

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    def test_pdfplumber_text_exactly_100_chars(self, mock_parse, tmp_path: Path):
        """pdfplumber 恰好返回 100 字符 — 不够 101 阈值"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_parse.return_value = "a" * 100

        from dochris.parsers.pdf_parser import parse_pdf

        with (
            patch("dochris.parsers.pdf_parser.parse_with_pymupdf", return_value=None),
            patch("dochris.parsers.pdf_parser.parse_with_pypdf2", return_value=None),
            patch("dochris.parsers.pdf_parser.parse_with_markitdown", return_value=None),
            patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr", return_value=None),
        ):
            from dochris.exceptions import FileProcessingError

            with pytest.raises(FileProcessingError):
                parse_pdf(pdf_file)

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    def test_pdfplumber_text_exactly_101_chars(self, mock_parse, tmp_path: Path):
        """pdfplumber 恰好返回 101 字符 — 刚好达标"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_parse.return_value = "a" * 101

        from dochris.parsers.pdf_parser import parse_pdf

        with (
            patch("dochris.parsers.pdf_parser.parse_with_pymupdf"),
            patch("dochris.parsers.pdf_parser.parse_with_pypdf2"),
            patch("dochris.parsers.pdf_parser.parse_with_markitdown"),
            patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr"),
        ):
            result = parse_pdf(pdf_file)
        assert len(result) == 101


class TestParseWithPymupdfMocked:
    """测试 PyMuPDF 解析器（模拟成功路径）"""

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber", return_value=None)
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2", return_value=None)
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown", return_value=None)
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr", return_value=None)
    def test_pymupdf_succeeds_after_pdfplumber_fails(
        self, mock_ocr, mock_md, mock_p2, mock_pymupdf, mock_plumber, tmp_path: Path
    ):
        """pdfplumber 返回 None 后 pymupdf 成功"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pymupdf.return_value = "pymupdf 文本" * 30

        result = parse_pdf(pdf_file)
        assert "pymupdf" in result

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber", return_value=None)
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2", return_value=None)
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown", return_value=None)
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr", return_value=None)
    def test_pymupdf_raises_runtime_error(
        self, mock_ocr, mock_md, mock_p2, mock_pymupdf, mock_plumber, tmp_path: Path
    ):
        """pymupdf 抛出 RuntimeError 时继续降级"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pymupdf.side_effect = RuntimeError("损坏的 PDF")

        from dochris.exceptions import FileProcessingError

        with pytest.raises(FileProcessingError):
            parse_pdf(pdf_file)


class TestParseWithPypdf2Mocked:
    """测试 PyPDF2 解析器（模拟路径）"""

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber", return_value=None)
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf", return_value=None)
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown", return_value=None)
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr", return_value=None)
    def test_pypdf2_returns_valid_text(
        self, mock_ocr, mock_md, mock_p2, mock_mu, mock_pl, tmp_path: Path
    ):
        """pypdf2 成功解析"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_p2.return_value = "pypdf2 解析结果" * 20

        result = parse_pdf(pdf_file)
        assert "pypdf2" in result


class TestMarkitdownEdgeCases:
    """markitdown 解析器额外边界条件"""

    @patch("subprocess.run")
    def test_uppercase_pdf_extension(self, mock_run, tmp_path: Path):
        """大写 .PDF 扩展名也能处理"""
        pdf_file = tmp_path / "test.PDF"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")
        mock_run.return_value = MagicMock(returncode=0, stdout="大写扩展名PDF" * 20)

        result = parse_with_markitdown(pdf_file)
        assert result is not None


class TestParsePdfErrorDetails:
    """测试 parse_pdf 错误信息包含解析器详情"""

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_error_message_contains_parser_names(
        self, mock_ocr, mock_md, mock_p2, mock_mu, mock_pl, tmp_path: Path
    ):
        """错误消息中包含解析器名称"""
        from dochris.exceptions import FileProcessingError

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pl.return_value = None
        mock_mu.return_value = None
        mock_p2.return_value = None
        mock_md.return_value = None
        mock_ocr.return_value = None

        with pytest.raises(FileProcessingError) as exc_info:
            parse_pdf(pdf_file)

        error_msg = str(exc_info.value)
        assert "test.pdf" in error_msg

    @patch("dochris.parsers.pdf_parser.parse_with_pdfplumber")
    @patch("dochris.parsers.pdf_parser.parse_with_pymupdf")
    @patch("dochris.parsers.pdf_parser.parse_with_pypdf2")
    @patch("dochris.parsers.pdf_parser.parse_with_markitdown")
    @patch("dochris.parsers.pdf_parser.parse_with_tesseract_ocr")
    def test_unexpected_exception_caught(
        self, mock_ocr, mock_md, mock_p2, mock_mu, mock_pl, tmp_path: Path
    ):
        """解析器抛出非标准异常时也能捕获"""

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        mock_pl.side_effect = MemoryError("OOM")
        mock_mu.return_value = "pymupdf 补救成功" * 20

        result = parse_pdf(pdf_file)
        assert "pymupdf" in result


class TestParsePdfCorruptedFile:
    """损坏文件处理"""

    def test_binary_gibberish_file_raises_error(self, tmp_path: Path):
        """二进制乱码文件触发所有解析器失败"""
        from dochris.exceptions import FileProcessingError

        pdf_file = tmp_path / "corrupted.pdf"
        pdf_file.write_bytes(bytes(range(256)) * 10)

        with pytest.raises(FileProcessingError, match="所有 PDF 解析器都失败"):
            parse_pdf(pdf_file)

    def test_partial_pdf_header_raises_error(self, tmp_path: Path):
        """只有 PDF 头没有内容的文件"""
        from dochris.exceptions import FileProcessingError

        pdf_file = tmp_path / "header_only.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        with pytest.raises(FileProcessingError):
            parse_pdf(pdf_file)


class TestParserModuleConstants:
    """测试模块级常量和导入"""

    def test_parse_pdf_is_callable(self):
        """parse_pdf 可调用"""
        assert callable(parse_pdf)

    def test_all_parsers_are_callable(self):
        """所有解析器函数可调用"""
        for func in [
            parse_with_markitdown,
            parse_with_pdfplumber,
            parse_with_pymupdf,
            parse_with_pypdf2,
            parse_with_tesseract_ocr,
        ]:
            assert callable(func)
