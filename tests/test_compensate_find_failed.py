"""补充测试 compensate/compensate_failures.py — 覆盖 find_failed_manifests + compile_with_model_fallback"""

from unittest.mock import MagicMock, patch

import pytest


class TestFindFailedManifests:
    """覆盖 find_failed_manifests 所有分支"""

    def _make_manifest(self, mid, file_type, ext, error_msg):
        return {
            "id": mid,
            "type": file_type,
            "file_path": f"raw/test{ext}",
            "error_message": error_msg,
        }

    def test_ebook_filter(self, tmp_path):
        """筛选 ebook 类型"""
        from dochris.compensate import compensate_failures

        manifests = [
            self._make_manifest("SRC-001", "ebook", ".mobi", "no_text"),
            self._make_manifest("SRC-002", "ebook", ".epub", "no_text"),
            self._make_manifest("SRC-003", "pdf", ".pdf", "no_text"),
        ]

        # 创建实际文件
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "test.mobi").write_bytes(b"mobi")
        (raw_dir / "test.epub").write_bytes(b"epub")
        (raw_dir / "test.pdf").write_bytes(b"pdf")

        with patch.object(compensate_failures, "KB_PATH", tmp_path):
            with patch.object(compensate_failures, "get_all_manifests", return_value=manifests):
                result = compensate_failures.find_failed_manifests("ebook", MagicMock())

        ids = [m["id"] for m in result]
        assert "SRC-001" in ids
        assert "SRC-002" not in ids  # .epub not in (.mobi, .azw3)
        assert "SRC-003" not in ids  # not ebook type

    def test_pdf_filter(self, tmp_path):
        """筛选 pdf 类型"""
        from dochris.compensate import compensate_failures

        manifests = [
            self._make_manifest("SRC-001", "pdf", ".pdf", "no_text"),
            self._make_manifest("SRC-002", "pdf", ".pdf", "llm_failed"),
        ]

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "test.pdf").write_bytes(b"pdf")

        with patch.object(compensate_failures, "KB_PATH", tmp_path):
            with patch.object(compensate_failures, "get_all_manifests", return_value=manifests):
                result = compensate_failures.find_failed_manifests("pdf", MagicMock())

        ids = [m["id"] for m in result]
        assert "SRC-001" in ids
        assert "SRC-002" not in ids

    def test_llm_filter(self, tmp_path):
        """筛选 llm_failed 类型"""
        from dochris.compensate import compensate_failures

        manifests = [
            self._make_manifest("SRC-001", "pdf", ".pdf", "llm_failed"),
            self._make_manifest("SRC-002", "pdf", ".pdf", "no_text"),
        ]

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "test.pdf").write_bytes(b"pdf")

        with patch.object(compensate_failures, "KB_PATH", tmp_path):
            with patch.object(compensate_failures, "get_all_manifests", return_value=manifests):
                result = compensate_failures.find_failed_manifests("llm", MagicMock())

        ids = [m["id"] for m in result]
        assert "SRC-001" in ids
        assert "SRC-002" not in ids

    def test_other_filter(self, tmp_path):
        """筛选 other 类型"""
        from dochris.compensate import compensate_failures

        manifests = [
            self._make_manifest("SRC-001", "other", ".mhtml", "no_text"),
            self._make_manifest("SRC-002", "other", ".exe", "no_text"),
        ]

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "test.mhtml").write_text("mhtml", encoding="utf-8")
        (raw_dir / "test.exe").write_bytes(b"exe")

        with patch.object(compensate_failures, "KB_PATH", tmp_path):
            with patch.object(compensate_failures, "get_all_manifests", return_value=manifests):
                result = compensate_failures.find_failed_manifests("other", MagicMock())

        ids = [m["id"] for m in result]
        assert "SRC-001" in ids
        assert "SRC-002" not in ids

    def test_all_filter(self, tmp_path):
        """筛选所有可补偿类型"""
        from dochris.compensate import compensate_failures

        manifests = [
            self._make_manifest("SRC-001", "pdf", ".pdf", "no_text"),
            self._make_manifest("SRC-002", "pdf", ".pdf", "llm_failed"),
            self._make_manifest("SRC-003", "other", ".mhtml", "no_text"),
        ]

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "test.pdf").write_bytes(b"pdf")
        (raw_dir / "test.mhtml").write_text("mhtml", encoding="utf-8")

        with patch.object(compensate_failures, "KB_PATH", tmp_path):
            with patch.object(compensate_failures, "get_all_manifests", return_value=manifests):
                result = compensate_failures.find_failed_manifests("all", MagicMock())

        ids = [m["id"] for m in result]
        assert "SRC-001" in ids
        assert "SRC-002" in ids
        assert "SRC-003" in ids

    def test_empty_results(self, tmp_path):
        """无失败 manifest"""
        from dochris.compensate import compensate_failures

        with patch.object(compensate_failures, "KB_PATH", tmp_path):
            with patch.object(compensate_failures, "get_all_manifests", return_value=[]):
                result = compensate_failures.find_failed_manifests("all", MagicMock())

        assert result == []


class TestCompileWithModelFallbackNoKey:
    """覆盖 compile_with_model_fallback 无 API Key"""

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        """无 API Key 返回 None"""
        from dochris.compensate.compensate_failures import compile_with_model_fallback

        mock_settings = MagicMock()
        mock_settings.api_key = ""

        with patch(
            "dochris.compensate.compensate_failures.get_settings", return_value=mock_settings
        ):
            result = await compile_with_model_fallback(
                "text", "title", MagicMock(), ["model1"], 0.1
            )

        assert result is None
