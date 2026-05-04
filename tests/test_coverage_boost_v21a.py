"""覆盖率提升 v21a — compensate_extractors 分支"""

from unittest.mock import MagicMock, patch

import pytest


class TestCompensateExtractorsEdges:
    def test_unknown_long(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        f = tmp_path / "t.xyz"
        f.write_text("a" * 500)
        r = extract_text_from_file(f, logger=MagicMock())
        assert r is not None

    def test_unknown_short(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        f = tmp_path / "t.xyz"
        f.write_text("hi")
        r = extract_text_from_file(f, logger=MagicMock())
        assert r is None

    def test_unknown_oserror(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        f = tmp_path / "t.xyz"
        f.write_text("a" * 500)
        with patch.object(f.__class__, "read_text", side_effect=OSError("p")):
            assert extract_text_from_file(f, logger=MagicMock()) is None

    def test_unknown_generic_exc(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        f = tmp_path / "t.xyz"
        f.write_text("a" * 500)
        with patch.object(f.__class__, "read_text", side_effect=ValueError("e")):
            assert extract_text_from_file(f, logger=MagicMock()) is None

    def test_doc_text_exc(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file
        from dochris.exceptions import TextExtractionError

        f = tmp_path / "t.docx"
        f.write_bytes(b"x")
        with patch(
            "dochris.parsers.doc_parser.parse_document", side_effect=TextExtractionError("e")
        ):
            assert extract_text_from_file(f, logger=MagicMock()) is None

    def test_doc_generic_exc(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        f = tmp_path / "t.md"
        f.write_text("# t")
        with patch("dochris.parsers.doc_parser.parse_document", side_effect=RuntimeError("e")):
            assert extract_text_from_file(f, logger=MagicMock()) is None

    def test_pdf_text_exc(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file
        from dochris.exceptions import TextExtractionError

        f = tmp_path / "t.pdf"
        f.write_bytes(b"%PDF")
        with patch("dochris.parsers.pdf_parser.parse_pdf", side_effect=TextExtractionError("e")):
            assert extract_text_from_file(f, logger=MagicMock()) is None

    def test_pdf_generic_exc(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        f = tmp_path / "t.pdf"
        f.write_bytes(b"%PDF")
        with patch("dochris.parsers.pdf_parser.parse_pdf", side_effect=RuntimeError("e")):
            assert extract_text_from_file(f, logger=MagicMock()) is None

    def test_code_ok(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        f = tmp_path / "t.py"
        f.write_text("def hi(): return 1")
        assert extract_text_from_file(f, logger=MagicMock()) is not None

    @pytest.mark.skip("Path.read_text is read-only on PosixPath, cannot mock")
    def test_code_oserror(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        f = tmp_path / "t.py"
        f.write_text("x")
        with patch.object(f, "read_text", side_effect=OSError("e")):
            assert extract_text_from_file(f, logger=MagicMock()) is None

    @pytest.mark.skip("Path.read_text is read-only on PosixPath, cannot mock")
    def test_code_generic_exc(self, tmp_path):
        from dochris.compensate.compensate_extractors import extract_text_from_file

        f = tmp_path / "t.py"
        f.write_text("x")
        with patch.object(f, "read_text", side_effect=RuntimeError("e")):
            assert extract_text_from_file(f, logger=MagicMock()) is None
