"""覆盖率提升 v5 — batch_promote.py + cli_init.py"""

from unittest.mock import patch

import pytest


# ============================================================
# batch_promote.py — 覆盖 dry_run, limit, main CLI
# ============================================================
class TestBatchPromote:
    """测试批量 promote 的分支"""

    def _make_manifests(self, n=3, status="compiled"):
        return [
            {"id": f"src_{i:03d}", "status": status, "title": f"Doc {i}", "quality_score": 90}
            for i in range(n)
        ]

    def test_batch_wiki_dry_run(self, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_wiki

        manifests = self._make_manifests(5)
        with patch("dochris.admin.batch_promote.get_all_manifests", return_value=manifests):
            result = batch_promote_to_wiki(tmp_path, dry_run=True)
            assert result["total"] == 5
            assert result["success"] == 0

    def test_batch_wiki_with_limit(self, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_wiki

        manifests = self._make_manifests(10)
        with patch("dochris.admin.batch_promote.get_all_manifests", return_value=manifests):
            result = batch_promote_to_wiki(tmp_path, limit=3)
            assert result["total"] == 3

    def test_batch_wiki_min_score_filter(self, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_wiki

        manifests = [
            {"id": "s1", "status": "compiled", "title": "A", "quality_score": 90},
            {"id": "s2", "status": "compiled", "title": "B", "quality_score": 50},
            {"id": "s3", "status": "compiled", "title": "C", "quality_score": 95},
        ]
        with patch("dochris.admin.batch_promote.get_all_manifests", return_value=manifests):
            result = batch_promote_to_wiki(tmp_path, min_score=85)
            assert result["total"] == 2

    def test_batch_wiki_success_and_fail(self, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_wiki

        manifests = self._make_manifests(2)
        with patch("dochris.admin.batch_promote.get_all_manifests", return_value=manifests), \
             patch("dochris.admin.batch_promote.promote_to_wiki", side_effect=[True, False]), \
             patch("dochris.admin.batch_promote.append_log"):
            result = batch_promote_to_wiki(tmp_path)
            assert result["success"] == 1
            assert result["failed"] == 1

    def test_batch_curated_dry_run(self, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_curated

        manifests = self._make_manifests(3)
        with patch("dochris.admin.batch_promote.get_all_manifests", return_value=manifests):
            result = batch_promote_to_curated(tmp_path, dry_run=True)
            assert result["total"] == 3

    def test_batch_obsidian_dry_run(self, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_obsidian

        manifests = [
            {"id": f"src_{i:03d}", "status": "promoted", "title": f"Doc {i}", "quality_score": 95}
            for i in range(3)
        ]
        with patch("dochris.admin.batch_promote.get_all_manifests", return_value=manifests):
            result = batch_promote_to_obsidian(tmp_path, dry_run=True)
            assert result["total"] == 3

    def test_batch_obsidian_import_error(self, tmp_path):
        from dochris.admin.batch_promote import batch_promote_to_obsidian

        with patch.dict("sys.modules", {"dochris.vault.bridge": None}):
            import importlib

            import dochris.admin.batch_promote
            importlib.reload(dochris.admin.batch_promote)
            result = batch_promote_to_obsidian(tmp_path)
            assert result["total"] == 0


class TestBatchPromoteCLI:
    """测试 CLI main() 分支"""

    def test_no_args(self):
        from dochris.admin.batch_promote import main

        with pytest.raises(SystemExit):
            main()

    def test_unknown_target(self, tmp_path):
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["batch_promote.py", str(tmp_path), "unknown"]):
            with pytest.raises(SystemExit):
                main()

    def test_wiki_target(self, tmp_path):
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["batch_promote.py", str(tmp_path), "wiki", "--dry-run"]), \
             patch("dochris.admin.batch_promote.get_all_manifests", return_value=[]):
            main()  # dry-run 不会 sys.exit

    def test_curated_target(self, tmp_path):
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["batch_promote.py", str(tmp_path), "curated", "--dry-run"]), \
             patch("dochris.admin.batch_promote.get_all_manifests", return_value=[]):
            main()

    def test_obsidian_target(self, tmp_path):
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["batch_promote.py", str(tmp_path), "obsidian", "--dry-run"]), \
             patch("dochris.admin.batch_promote.get_all_manifests", return_value=[]):
            main()

    def test_min_score_arg(self, tmp_path):
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["batch_promote.py", str(tmp_path), "wiki", "--min-score", "90", "--dry-run"]), \
             patch("dochris.admin.batch_promote.get_all_manifests", return_value=[]):
            main()

    def test_limit_arg(self, tmp_path):
        from dochris.admin.batch_promote import main

        with patch("sys.argv", ["batch_promote.py", str(tmp_path), "wiki", "--limit", "5", "--dry-run"]), \
             patch("dochris.admin.batch_promote.get_all_manifests", return_value=[]):
            main()
