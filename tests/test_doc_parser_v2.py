"""补充测试 parsers/doc_parser.py — 覆盖错误分支"""

from unittest.mock import MagicMock, patch


class TestDocParserErrorBranches:
    """覆盖 doc_parser 的错误处理分支"""

    def test_markitdown_short_content_after_cleanup(self, tmp_path):
        """markitdown 清理后内容过短返回 None（line 87-88）"""
        from dochris.parsers.doc_parser import parse_office_document

        doc_file = tmp_path / "test.docx"
        doc_file.write_bytes(b"PK\x03\x04")

        mock_md = MagicMock()
        # 包含 base64 图片，清理后内容很短
        mock_md.convert.return_value = MagicMock(
            text_content="![](data:image/png;base64,AAAA) short"
        )

        with patch.dict(
            "sys.modules", {"markitdown": MagicMock(MarkItDown=MagicMock(return_value=mock_md))}
        ):
            result = parse_office_document(doc_file)

        assert result is None

    def test_markitdown_unexpected_exception(self, tmp_path):
        """markitdown 未预期异常返回 None（line 99-102）"""
        from dochris.parsers.doc_parser import parse_office_document

        doc_file = tmp_path / "test.docx"
        doc_file.write_bytes(b"PK\x03\x04")

        mock_md = MagicMock()
        mock_md.convert.side_effect = MemoryError("unexpected")

        with patch("markitdown.MarkItDown", return_value=mock_md):
            result = parse_office_document(doc_file)

        assert result is None

    def test_other_format_read_error(self, tmp_path):
        """其他格式文件读取错误返回 None（line 57-58）"""
        from dochris.parsers.doc_parser import parse_document

        bad_file = tmp_path / "test.xyz"
        bad_file.write_bytes(b"\xff\xfe")

        with patch(
            "pathlib.Path.read_text", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")
        ):
            result = parse_document(bad_file)

        assert result is None
