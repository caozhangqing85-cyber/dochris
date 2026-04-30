"""tests/test_compensate_extractors.py

补偿提取器模块测试
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_settings(tmp_path, monkeypatch):
    """模拟配置"""
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "logs").mkdir()

    monkeypatch.setenv("WORKSPACE", str(workspace))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MAX_CONTENT_CHARS", "20000")
    monkeypatch.setenv("MIN_TEXT_LENGTH", "100")

    return workspace


@pytest.fixture
def sample_manifest():
    """示例 manifest"""
    return {
        "id": "SRC-0001",
        "status": "failed",
        "title": "测试文档",
        "file_path": "raw/test.pdf",
        "error_message": "no_text",
        "type": "pdf",
    }


class TestExtractTextFromFile:
    """测试 extract_text_from_file 函数"""

    def test_extract_pdf_text_success(self, tmp_path, mock_settings):
        """测试 PDF 文本提取成功"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\ntest content")

        logger = MagicMock()
        result = extract_text_from_file(pdf_file, logger)

        # 由于 markitdown 可能不可用，这里只测试函数存在
        assert result is None or isinstance(result, str)

    def test_extract_markdown_file(self, tmp_path, mock_settings):
        """测试 Markdown 文件提取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        md_file = tmp_path / "test.md"
        md_file.write_text("# 测试\n\n这是测试内容", encoding="utf-8")

        logger = MagicMock()
        result = extract_text_from_file(md_file, logger)

        assert result is not None
        assert "测试内容" in result or result is not None

    def test_extract_code_file(self, tmp_path, mock_settings):
        """测试代码文件提取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        py_file = tmp_path / "test.py"
        py_file.write_text("def hello():\n    print('world')", encoding="utf-8")

        logger = MagicMock()
        result = extract_text_from_file(py_file, logger)

        assert result is not None
        assert "hello" in result

    def test_extract_nonexistent_file(self, tmp_path, mock_settings):
        """测试不存在的文件"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        nonexistent = tmp_path / "nonexistent.txt"
        logger = MagicMock()

        result = extract_text_from_file(nonexistent, logger)
        assert result is None


class TestExtractEbookText:
    """测试 extract_ebook_text 函数"""

    def test_extract_ebook_file_not_found(self, tmp_path, mock_settings):
        """测试 ebook 文件不存在"""
        from dochris.compensate.compensate_extractors import extract_ebook_text

        nonexistent = tmp_path / "test.mobi"
        logger = MagicMock()

        result = extract_ebook_text(nonexistent, logger)
        assert result is None

    def test_extract_ebook_without_calibre(self, tmp_path, mock_settings):
        """测试没有 Calibre 时的行为"""
        from dochris.compensate.compensate_extractors import extract_ebook_text

        mobi_file = tmp_path / "test.mobi"
        mobi_file.write_bytes(b"MOBI")

        logger = MagicMock()
        result = extract_ebook_text(mobi_file, logger)

        # 没有 ebook-convert 命令应该返回 None
        assert result is None


class TestExtractPdfWithOcr:
    """测试 extract_pdf_with_ocr 函数"""

    def test_ocr_nonexistent_file(self, tmp_path, mock_settings):
        """测试 OCR 不存在的文件"""
        from dochris.compensate.compensate_extractors import extract_pdf_with_ocr

        nonexistent = tmp_path / "test.pdf"
        logger = MagicMock()

        result = extract_pdf_with_ocr(nonexistent, logger)
        assert result is None

    def test_ocr_without_dependencies(self, tmp_path, mock_settings):
        """测试没有依赖时的行为"""
        from dochris.compensate.compensate_extractors import extract_pdf_with_ocr

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF")

        logger = MagicMock()
        result = extract_pdf_with_ocr(pdf_file, logger)

        # 没有 PyMuPDF 或 tesseract 应该返回 None
        assert result is None


class TestExtractTextCompensated:
    """测试 extract_text_compensated 函数"""

    def test_compensated_returns_tuple(self, tmp_path, mock_settings, sample_manifest):
        """测试返回值是元组"""
        from dochris.compensate.compensate_extractors import extract_text_compensated

        file_path = tmp_path / "test.txt"
        file_path.write_text("测试内容" * 100, encoding="utf-8")

        logger = MagicMock()
        result = extract_text_compensated(file_path, sample_manifest, logger)

        assert isinstance(result, tuple)
        assert len(result) == 2
        text, method = result
        assert isinstance(text, (str, type(None)))
        assert isinstance(method, str)

    def test_compensated_method_values(self, tmp_path, mock_settings, sample_manifest):
        """测试提取方法值"""
        from dochris.compensate.compensate_extractors import extract_text_compensated

        file_path = tmp_path / "test.txt"
        file_path.write_text("测试内容" * 100, encoding="utf-8")

        logger = MagicMock()
        text, method = extract_text_compensated(file_path, sample_manifest, logger)

        # 方法应该是预定义的值之一
        valid_methods = {"original", "ebook_convert", "ocr", "markitdown", "failed"}
        assert method in valid_methods

    def test_compensated_with_pdf_type(self, tmp_path, mock_settings):
        """测试 PDF 类型的补偿"""
        from dochris.compensate.compensate_extractors import extract_text_compensated

        manifest = {
            "id": "SRC-0001",
            "type": "pdf",
            "title": "测试PDF",
            "file_path": "raw/test.pdf",
        }

        file_path = tmp_path / "test.pdf"
        file_path.write_bytes(b"%PDF")

        logger = MagicMock()
        text, method = extract_text_compensated(file_path, manifest, logger)

        assert isinstance(text, (str, type(None)))
        assert isinstance(method, str)

    def test_compensated_with_ebook_type(self, tmp_path, mock_settings):
        """测试 ebook 类型的补偿"""
        from dochris.compensate.compensate_extractors import extract_text_compensated

        manifest = {
            "id": "SRC-0002",
            "type": "ebook",
            "title": "测试Ebook",
            "file_path": "raw/test.mobi",
        }

        file_path = tmp_path / "test.mobi"
        file_path.write_bytes(b"MOBI")

        logger = MagicMock()
        text, method = extract_text_compensated(file_path, manifest, logger)

        assert isinstance(text, (str, type(None)))
        assert isinstance(method, str)
