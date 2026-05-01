"""测试 parsers: code_parser + doc_parser"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from dochris.parsers.code_parser import (
    _detect_language,
    _extract_docstrings_and_comments,
    detect_code_file,
    extract_from_code,
)
from dochris.parsers.doc_parser import (
    detect_document_file,
    parse_document,
)

# ---- code_parser ----


class TestDetectCodeFile:
    def test_python(self):
        assert detect_code_file(Path("test.py")) is True

    def test_javascript(self):
        assert detect_code_file(Path("app.js")) is True

    def test_typescript(self):
        assert detect_code_file(Path("app.ts")) is True

    def test_java(self):
        assert detect_code_file(Path("Main.java")) is True

    def test_cpp(self):
        assert detect_code_file(Path("main.cpp")) is True

    def test_go(self):
        assert detect_code_file(Path("main.go")) is True

    def test_rust(self):
        assert detect_code_file(Path("main.rs")) is True

    def test_non_code(self):
        assert detect_code_file(Path("readme.md")) is False

    def test_case_insensitive(self):
        assert detect_code_file(Path("TEST.PY")) is True

    def test_all_extensions(self):
        exts = [".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs",
                ".rb", ".cs", ".kt", ".swift", ".lua", ".zig", ".php", ".m", ".mm"]
        for ext in exts:
            assert detect_code_file(Path(f"f{ext}")) is True


class TestDetectLanguage:
    def test_python(self):
        assert _detect_language(Path("f.py")) == "python"

    def test_javascript(self):
        assert _detect_language(Path("f.js")) == "javascript"

    def test_typescript(self):
        assert _detect_language(Path("f.ts")) == "typescript"

    def test_unknown(self):
        assert _detect_language(Path("f.xyz")) == "unknown"

    def test_go(self):
        assert _detect_language(Path("f.go")) == "go"

    def test_rust(self):
        assert _detect_language(Path("f.rs")) == "rust"


class TestExtractDocstringsAndComments:
    def test_python_comments(self):
        code = "# comment\nx = 1\n# another"
        result = _extract_docstrings_and_comments(code, "python")
        assert "# comment" in result
        assert "# another" in result

    def test_js_comments(self):
        code = "// js comment\nvar x = 1;\n/* block */"
        result = _extract_docstrings_and_comments(code, "javascript")
        assert "// js comment" in result

    def test_empty_content(self):
        assert _extract_docstrings_and_comments("", "python") == ""


class TestExtractFromCode:
    def test_valid_python_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write('def hello():\n    """Greet"""\n    pass\n\nclass Foo:\n    pass\n')
            f.flush()
            result = extract_from_code(Path(f.name))
        os.unlink(f.name)
        assert result is not None
        assert "hello" in result["functions"]
        assert "Foo" in result["classes"]
        assert result["language"] == "python"

    def test_nonexistent_file(self):
        result = extract_from_code(Path("/nonexistent/file.py"))
        assert result is None

    def test_no_functions_or_classes(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write("x = 1\ny = 2\n")
            f.flush()
            result = extract_from_code(Path(f.name))
        os.unlink(f.name)
        assert result is not None
        assert result["functions"] == []
        assert result["classes"] == []


# ---- doc_parser ----


class TestDetectDocumentFile:
    def test_md(self):
        assert detect_document_file(Path("f.md")) is True

    def test_txt(self):
        assert detect_document_file(Path("f.txt")) is True

    def test_rst(self):
        assert detect_document_file(Path("f.rst")) is True

    def test_html(self):
        assert detect_document_file(Path("f.html")) is True

    def test_docx(self):
        assert detect_document_file(Path("f.docx")) is True

    def test_non_doc(self):
        assert detect_document_file(Path("f.py")) is False

    def test_case_insensitive(self):
        assert detect_document_file(Path("F.MD")) is True


class TestParseDocument:
    def test_read_text_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("hello world")
            f.flush()
            result = parse_document(Path(f.name))
        os.unlink(f.name)
        assert result == "hello world"

    def test_read_md_file(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
            f.write("# Title\ncontent")
            f.flush()
            result = parse_document(Path(f.name))
        os.unlink(f.name)
        assert "Title" in result

    def test_nonexistent_file(self):
        result = parse_document(Path("/nonexistent/file.txt"))
        assert result is None

    def test_html_file(self):
        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False, encoding="utf-8") as f:
            f.write("<html><body>hi</body></html>")
            f.flush()
            result = parse_document(Path(f.name))
        os.unlink(f.name)
        assert result is not None
        assert "hi" in result

    def test_htm_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".htm", mode="w", delete=False, encoding="utf-8") as f:
            f.write("content")
            f.flush()
            result = parse_document(Path(f.name))
        os.unlink(f.name)
        assert result == "content"

    def test_docx_calls_office_parser(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"PK\x03\x04fake")
            f.flush()
            with patch("dochris.parsers.doc_parser.parse_office_document", return_value="office text") as mock:
                result = parse_document(Path(f.name))
        os.unlink(f.name)
        assert result == "office text"
        mock.assert_called_once()

    def test_unknown_ext_tries_text_read(self):
        with tempfile.NamedTemporaryFile(suffix=".log", mode="w", delete=False, encoding="utf-8") as f:
            f.write("log line 1\nlog line 2")
            f.flush()
            result = parse_document(Path(f.name))
        os.unlink(f.name)
        assert result is not None
        assert "log line 1" in result


class TestParseOfficeDocument:
    def test_markitdown_not_installed(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"fake")
            f.flush()
            # patch the import inside the function
            with patch.dict("sys.modules", {"markitdown": None}):
                # Force re-import to use the patched module
                import importlib

                import dochris.parsers.doc_parser as dp_mod
                importlib.reload(dp_mod)
                result = dp_mod.parse_office_document(Path(f.name))
        os.unlink(f.name)
        assert result is None

    def test_markitdown_returns_long_text(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"fake")
            f.flush()
            mock_md_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.text_content = "A" * 100
            mock_md_instance.convert.return_value = mock_result

            mock_markitdown_mod = MagicMock()
            mock_markitdown_mod.MarkItDown.return_value = mock_md_instance

            with patch.dict("sys.modules", {"markitdown": mock_markitdown_mod}):
                import importlib

                import dochris.parsers.doc_parser as dp_mod
                importlib.reload(dp_mod)
                result = dp_mod.parse_office_document(Path(f.name))
        os.unlink(f.name)
        assert result is not None

    def test_markitdown_short_text(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"fake")
            f.flush()
            mock_md_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.text_content = "short"
            mock_md_instance.convert.return_value = mock_result

            mock_markitdown_mod = MagicMock()
            mock_markitdown_mod.MarkItDown.return_value = mock_md_instance

            with patch.dict("sys.modules", {"markitdown": mock_markitdown_mod}):
                import importlib

                import dochris.parsers.doc_parser as dp_mod
                importlib.reload(dp_mod)
                result = dp_mod.parse_office_document(Path(f.name))
        os.unlink(f.name)
        assert result is None

    def test_markitdown_exception(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"fake")
            f.flush()
            mock_md_instance = MagicMock()
            mock_md_instance.convert.side_effect = RuntimeError("parse error")

            mock_markitdown_mod = MagicMock()
            mock_markitdown_mod.MarkItDown.return_value = mock_md_instance

            with patch.dict("sys.modules", {"markitdown": mock_markitdown_mod}):
                import importlib

                import dochris.parsers.doc_parser as dp_mod
                importlib.reload(dp_mod)
                result = dp_mod.parse_office_document(Path(f.name))
        os.unlink(f.name)
        assert result is None
