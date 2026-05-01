"""补充测试 admin/recompile.py — 覆盖 PDF no_text 排除 (line 93-94)"""

from unittest.mock import MagicMock, patch

import pytest


class TestRecompilePdfNoText:
    """覆盖 recompile 中 PDF no_text 排除分支 (line 93-94)"""

    def test_pdf_no_text_excluded_from_text_mode(self, tmp_path):
        """text 模式排除纯 no_text 的 PDF"""
        from dochris.admin.recompile import get_recoverable_failed_docs

        manifests = [
            {
                "id": "SRC-001",
                "type": "pdf",
                "status": "failed",
                "error_message": "no_text",
            },
            {
                "id": "SRC-002",
                "type": "pdf",
                "status": "failed",
                "error_message": "llm_failed",
            },
            {
                "id": "SRC-003",
                "type": "pdf",
                "status": "failed",
                "error_message": "timeout; no_text",
            },
        ]

        with patch(
            "dochris.admin.recompile.get_all_manifests", return_value=manifests
        ):
            result = get_recoverable_failed_docs(tmp_path, mode="text")

        ids = [m["id"] for m in result]
        assert "SRC-001" not in ids  # 纯 no_text PDF 被排除
        assert "SRC-002" in ids  # llm_failed 的 PDF 不排除
        assert "SRC-003" in ids  # timeout + no_text 不排除（含可恢复错误）
