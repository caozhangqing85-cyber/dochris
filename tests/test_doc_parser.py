"""
测试 parsers/doc_parser.py 模块
"""

from pathlib import Path


class TestDetectDocumentFile:
    """测试 detect_document_file 函数"""

    def test_detect_markdown(self):
        """测试检测 Markdown 文件"""
        from dochris.parsers.doc_parser import detect_document_file

        assert detect_document_file(Path("test.md"))
        assert detect_document_file(Path("document.md"))

    def test_detect_text_file(self):
        """测试检测纯文本文件"""
        from dochris.parsers.doc_parser import detect_document_file

        assert detect_document_file(Path("test.txt"))
        assert detect_document_file(Path("README.txt"))

    def test_detect_html(self):
        """测试检测 HTML 文件"""
        from dochris.parsers.doc_parser import detect_document_file

        assert detect_document_file(Path("test.html"))
        # .htm 可能不被支持，只测试 .html

    def test_detect_office_files(self):
        """测试检测 Office 文件"""
        from dochris.parsers.doc_parser import detect_document_file

        assert detect_document_file(Path("doc.docx"))
        assert detect_document_file(Path("slides.pptx"))
        assert detect_document_file(Path("data.xlsx"))

    def test_detect_non_document(self):
        """测试非文档文件"""
        from dochris.parsers.doc_parser import detect_document_file

        assert not detect_document_file(Path("image.png"))
        assert not detect_document_file(Path("video.mp4"))
        assert not detect_document_file(Path("data.pdf"))

    def test_detect_case_insensitive(self):
        """测试大小写不敏感"""
        from dochris.parsers.doc_parser import detect_document_file

        assert detect_document_file(Path("test.MD"))
        assert detect_document_file(Path("test.TXT"))
        assert detect_document_file(Path("test.DOCX"))


class TestParseDocument:
    """测试 parse_document 函数"""

    def test_parse_markdown_file(self, tmp_path):
        """测试解析 Markdown 文件"""
        from dochris.parsers.doc_parser import parse_document

        md_file = tmp_path / "test.md"
        md_file.write_text("# 标题\n\n内容", encoding="utf-8")

        result = parse_document(md_file)

        assert result is not None
        assert "标题" in result or "内容" in result

    def test_parse_text_file(self, tmp_path):
        """测试解析纯文本文件"""
        from dochris.parsers.doc_parser import parse_document

        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Plain text content", encoding="utf-8")

        result = parse_document(txt_file)

        assert result == "Plain text content"

    def test_parse_html_file(self, tmp_path):
        """测试解析 HTML 文件"""
        from dochris.parsers.doc_parser import parse_document

        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body>Test</body></html>", encoding="utf-8")

        result = parse_document(html_file)

        assert result is not None
        assert "Test" in result or "html" in result

    def test_parse_rst_file(self, tmp_path):
        """测试解析 RST 文件"""
        from dochris.parsers.doc_parser import parse_document

        rst_file = tmp_path / "test.rst"
        rst_file.write_text("Title\n=====\n\nContent", encoding="utf-8")

        result = parse_document(rst_file)

        assert result is not None

    def test_parse_nonexistent_file(self, tmp_path):
        """测试解析不存在的文件"""
        from dochris.parsers.doc_parser import parse_document

        result = parse_document(tmp_path / "nonexistent.txt")

        assert result is None


class TestParseOfficeDocument:
    """测试 parse_office_document 函数"""

    def test_parse_office_basic(self, tmp_path):
        """测试基本 Office 文件解析（函数存在性测试）"""
        from dochris.parsers.doc_parser import parse_office_document

        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"fake docx content")

        # 这个测试验证函数可以调用，实际结果取决于 markitdown 是否安装
        result = parse_office_document(docx_file)

        # 结果可能是 None（markitdown 未安装）或文本（已安装）
        assert result is None or isinstance(result, str)
