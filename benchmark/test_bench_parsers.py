"""文件解析性能基准测试"""
from pathlib import Path

import pytest


class TestParserPerformance:
    def test_parse_markdown_small(self, benchmark, tmp_path: Path) -> None:
        """解析小 Markdown 文件"""
        from dochris.parsers.doc_parser import parse_document

        f = tmp_path / "test.md"
        f.write_text("# Title\n\nSome content" * 100)
        result = benchmark(parse_document, f)
        assert result is not None

    def test_parse_markdown_large(self, benchmark, tmp_path: Path) -> None:
        """解析大 Markdown 文件（100KB）"""
        from dochris.parsers.doc_parser import parse_document

        f = tmp_path / "large.md"
        f.write_text("# Title\n\n" + "Paragraph with some content.\n" * 2000)
        result = benchmark(parse_document, f)
        assert result is not None

    def test_detect_document_file(self, benchmark, tmp_path: Path) -> None:
        """文件类型检测"""
        from dochris.parsers.doc_parser import detect_document_file

        f = tmp_path / "test.md"
        f.write_text("test")
        benchmark(detect_document_file, f)

    def test_file_category_lookup(self, benchmark) -> None:
        """文件分类查找"""
        from dochris.settings import get_file_category

        extensions = [".pdf", ".txt", ".mp3", ".py", ".md", ".json", ".csv"]

        def lookup_all() -> None:
            for ext in extensions:
                get_file_category(ext)

        benchmark(lookup_all)
