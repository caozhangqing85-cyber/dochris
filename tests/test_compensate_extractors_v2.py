"""补充测试 compensate_extractors.py — 覆盖更多提取分支"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_settings(tmp_path, monkeypatch):
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "logs").mkdir()
    monkeypatch.setenv("WORKSPACE", str(workspace))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MAX_CONTENT_CHARS", "20000")
    monkeypatch.setenv("MIN_TEXT_LENGTH", "100")
    return workspace


class TestExtractTextFromFileDocTypes:
    """覆盖 doc_parser 分支"""

    def test_extract_docx_file(self, tmp_path, mock_settings):
        """docx 文件提取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"PK\x03\x04")  # zip header

        logger = MagicMock()
        with patch("dochris.parsers.doc_parser.parse_document", return_value="文档内容"):
            result = extract_text_from_file(docx_file, logger)

        assert result == "文档内容"

    def test_extract_docx_file_parser_error(self, tmp_path, mock_settings):
        """docx 提取失败返回 None"""
        from dochris.compensate.compensate_extractors import extract_text_from_file
        from dochris.exceptions import TextExtractionError

        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"PK\x03\x04")

        logger = MagicMock()
        with patch(
            "dochris.parsers.doc_parser.parse_document", side_effect=TextExtractionError("fail")
        ):
            result = extract_text_from_file(docx_file, logger)

        assert result is None
        logger.warning.assert_called()

    def test_extract_pptx_file(self, tmp_path, mock_settings):
        """pptx 文件提取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        pptx_file = tmp_path / "test.pptx"
        pptx_file.write_bytes(b"PK\x03\x04")

        logger = MagicMock()
        with patch("dochris.parsers.doc_parser.parse_document", return_value="PPT 内容"):
            result = extract_text_from_file(pptx_file, logger)

        assert result == "PPT 内容"

    def test_extract_html_file(self, tmp_path, mock_settings):
        """html 文件提取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body>Hello</body></html>", encoding="utf-8")

        logger = MagicMock()
        with patch("dochris.parsers.doc_parser.parse_document", return_value="Hello"):
            result = extract_text_from_file(html_file, logger)

        assert result == "Hello"


class TestExtractTextFromFileCodeTypes:
    """覆盖代码文件分支"""

    def test_extract_typescript_file(self, tmp_path, mock_settings):
        """TypeScript 文件直接读取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        ts_file = tmp_path / "test.ts"
        ts_file.write_text("const x: number = 1;", encoding="utf-8")

        logger = MagicMock()
        result = extract_text_from_file(ts_file, logger)

        assert result is not None
        assert "const x" in result

    def test_extract_json_file(self, tmp_path, mock_settings):
        """JSON 文件直接读取"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}', encoding="utf-8")

        logger = MagicMock()
        result = extract_text_from_file(json_file, logger)

        assert result is not None
        assert "key" in result


class TestExtractTextFromFileDefaultBranch:
    """覆盖默认读取分支"""

    def test_default_branch_long_text(self, tmp_path, mock_settings):
        """默认分支读取长文本（>100字符）"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a" * 200, encoding="utf-8")

        logger = MagicMock()
        result = extract_text_from_file(csv_file, logger)

        assert result is not None

    def test_default_branch_short_text(self, tmp_path, mock_settings):
        """默认分支短文本（<100字符）返回 None"""
        from dochris.compensate.compensate_extractors import extract_text_from_file

        csv_file = tmp_path / "test.csv"
        csv_file.write_text("short", encoding="utf-8")

        logger = MagicMock()
        result = extract_text_from_file(csv_file, logger)

        assert result is None


class TestExtractEbookTextSuccess:
    """覆盖 ebook-convert 成功分支"""

    @patch("dochris.compensate.compensate_extractors.subprocess.run")
    def test_ebook_convert_success(self, mock_run, tmp_path, mock_settings):
        """ebook-convert 成功返回文本"""
        from dochris.compensate.compensate_extractors import extract_ebook_text

        mobi_file = tmp_path / "test.mobi"
        mobi_file.write_bytes(b"MOBI")

        # 第一次调用：ebook-convert 成功
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # 临时文件写入内容
        with patch(
            "dochris.compensate.compensate_extractors.tempfile.NamedTemporaryFile"
        ) as mock_tmp:
            mock_tmp_file = MagicMock()
            mock_tmp_file.name = str(tmp_path / "output.txt")
            mock_tmp_file.__enter__ = MagicMock(return_value=mock_tmp_file)
            mock_tmp_file.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value = mock_tmp_file

            # 写出内容到临时文件
            output_file = tmp_path / "output.txt"
            output_file.write_text("Ebook content extracted " * 10, encoding="utf-8")

            logger = MagicMock()
            result = extract_ebook_text(mobi_file, logger)

        assert result is not None
        assert "Ebook content" in result

    @patch("dochris.compensate.compensate_extractors.subprocess.run")
    def test_ebook_convert_empty_result(self, mock_run, tmp_path, mock_settings):
        """ebook-convert 返回空文本"""
        from dochris.compensate.compensate_extractors import extract_ebook_text

        mobi_file = tmp_path / "test.mobi"
        mobi_file.write_bytes(b"MOBI")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        with patch(
            "dochris.compensate.compensate_extractors.tempfile.NamedTemporaryFile"
        ) as mock_tmp:
            mock_tmp_file = MagicMock()
            mock_tmp_file.name = str(tmp_path / "empty.txt")
            mock_tmp_file.__enter__ = MagicMock(return_value=mock_tmp_file)
            mock_tmp_file.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value = mock_tmp_file

            output_file = tmp_path / "empty.txt"
            output_file.write_text("   ", encoding="utf-8")

            logger = MagicMock()
            result = extract_ebook_text(mobi_file, logger)

        assert result is None

    @patch("dochris.compensate.compensate_extractors.subprocess.run")
    def test_ebook_convert_failure(self, mock_run, tmp_path, mock_settings):
        """ebook-convert 命令失败"""
        from dochris.compensate.compensate_extractors import extract_ebook_text

        mobi_file = tmp_path / "test.mobi"
        mobi_file.write_bytes(b"MOBI")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        mock_run.return_value = mock_result

        with patch(
            "dochris.compensate.compensate_extractors.tempfile.NamedTemporaryFile"
        ) as mock_tmp:
            mock_tmp_file = MagicMock()
            mock_tmp_file.name = str(tmp_path / "output.txt")
            mock_tmp_file.__enter__ = MagicMock(return_value=mock_tmp_file)
            mock_tmp_file.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value = mock_tmp_file

            output_file = tmp_path / "output.txt"
            output_file.write_text("", encoding="utf-8")

            logger = MagicMock()
            result = extract_ebook_text(mobi_file, logger)

        assert result is None


class TestExtractTextCompensatedOtherType:
    """覆盖 other 类型的 markitdown 补偿分支"""

    @patch("dochris.compensate.compensate_extractors.subprocess.run")
    def test_other_type_markitdown_success(self, mock_run, tmp_path, mock_settings):
        """other 类型 markitdown 补偿成功"""
        from dochris.compensate.compensate_extractors import extract_text_compensated

        mhtml_file = tmp_path / "test.mhtml"
        mhtml_file.write_bytes(b"MHTML")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Extracted content " * 20  # > MIN_AUDIO_TEXT_LENGTH
        mock_run.return_value = mock_result

        manifest = {"id": "SRC-0001", "type": "other", "file_path": "test.mhtml"}

        # 模拟 extract_text_from_file 返回 None（原始提取失败）
        with patch(
            "dochris.compensate.compensate_extractors.extract_text_from_file", return_value=None
        ):
            logger = MagicMock()
            text, method = extract_text_compensated(mhtml_file, manifest, logger)

        assert method == "markitdown"
        assert text is not None

    @patch("dochris.compensate.compensate_extractors.subprocess.run")
    def test_other_type_markitdown_failure(self, mock_run, tmp_path, mock_settings):
        """other 类型 markitdown 补偿失败"""
        from dochris.compensate.compensate_extractors import extract_text_compensated

        mhtml_file = tmp_path / "test.mhtml"
        mhtml_file.write_bytes(b"MHTML")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        manifest = {"id": "SRC-0001", "type": "other", "file_path": "test.mhtml"}

        with patch(
            "dochris.compensate.compensate_extractors.extract_text_from_file", return_value=None
        ):
            logger = MagicMock()
            text, method = extract_text_compensated(mhtml_file, manifest, logger)

        assert method == "failed"
        assert text is None
