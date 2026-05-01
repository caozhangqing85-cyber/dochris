"""补充测试 batch_promote.py — 覆盖 limit 截断 + candidates > 20 输出"""

from unittest.mock import MagicMock, patch

import pytest


class TestBatchPromoteLimitAndOverflow:
    """覆盖 limit > 0 截断 (line 58/124) + candidates > 20 (line 67-68/208)"""

    def test_limit_truncates_candidates(self, tmp_path):
        """limit > 0 时截断候选列表"""
        from dochris.admin.batch_promote import batch_promote_to_wiki

        manifests = []
        for i in range(5):
            manifests.append({
                "id": f"SRC-{i+1:04d}",
                "status": "compiled",
                "title": f"测试文档{i+1}",
                "quality_score": 90,
            })

        with patch("dochris.admin.batch_promote.get_all_manifests", return_value=manifests):
            with patch("dochris.admin.batch_promote.promote_to_wiki") as mock_promote:
                mock_promote.return_value = True
                with patch("builtins.print"):
                    result = batch_promote_to_wiki(tmp_path, limit=2)

        # limit=2 截断到 2 个候选
        assert mock_promote.call_count == 2

    def test_candidates_overflow_20_dry_run(self, tmp_path):
        """超过 20 个候选且 dry_run 时打印省略信息"""
        from dochris.admin.batch_promote import batch_promote_to_wiki

        manifests = []
        for i in range(25):
            manifests.append({
                "id": f"SRC-{i+1:04d}",
                "status": "compiled",
                "title": f"测试文档{i+1}",
                "quality_score": 90,
            })

        with patch("dochris.admin.batch_promote.get_all_manifests", return_value=manifests):
            with patch("builtins.print") as mock_print:
                result = batch_promote_to_wiki(tmp_path, limit=0, dry_run=True)

        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "还有" in output
