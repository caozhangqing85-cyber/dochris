"""
测试 batch_promote.py 模块
"""

import json
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_workspace(tmp_path):
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "manifests").mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    return workspace


@pytest.fixture
def sample_compiled_manifests(mock_workspace):
    manifests = [
        {
            "id": "SRC-0001",
            "status": "compiled",
            "title": "高质量文档",
            "quality_score": 95,
        },
        {
            "id": "SRC-0002",
            "status": "compiled",
            "title": "低质量文档",
            "quality_score": 70,
        },
    ]
    for m in manifests:
        f = mock_workspace / "manifests" / "sources" / f"{m['id']}.json"
        f.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return manifests


class TestBatchPromoteToWiki:
    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.admin.batch_promote.promote_to_wiki")
    @patch("dochris.admin.batch_promote.append_log")
    def test_batch_promote_to_wiki(
        self, mock_log, mock_promote, mock_get, mock_workspace, sample_compiled_manifests
    ):
        from dochris.admin.batch_promote import batch_promote_to_wiki

        mock_get.return_value = sample_compiled_manifests
        mock_promote.return_value = True
        result = batch_promote_to_wiki(mock_workspace, min_score=85)
        assert result["success"] > 0

    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.admin.batch_promote.promote_to_wiki")
    def test_batch_promote_to_wiki_dry_run(
        self, mock_promote, mock_get, mock_workspace, sample_compiled_manifests
    ):
        from dochris.admin.batch_promote import batch_promote_to_wiki

        mock_get.return_value = sample_compiled_manifests
        result = batch_promote_to_wiki(mock_workspace, min_score=85, dry_run=True)
        assert result["total"] > 0


class TestBatchPromoteToCurated:
    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.admin.batch_promote.promote_to_curated")
    @patch("dochris.admin.batch_promote.append_log")
    def test_batch_promote_to_curated(self, mock_log, mock_promote, mock_get, mock_workspace):
        from dochris.admin.batch_promote import batch_promote_to_curated

        manifests = [{"id": "SRC-0001", "status": "promoted_to_wiki", "quality_score": 95}]
        mock_get.return_value = manifests
        mock_promote.return_value = True
        result = batch_promote_to_curated(mock_workspace, min_score=90)
        assert result["total"] > 0


class TestBatchPromoteToObsidian:
    @patch("dochris.admin.batch_promote.get_all_manifests")
    @patch("dochris.vault.bridge.promote_to_obsidian")
    @patch("dochris.admin.batch_promote.append_log")
    def test_batch_promote_to_obsidian(self, mock_log, mock_promote, mock_get, mock_workspace):
        from dochris.admin.batch_promote import batch_promote_to_obsidian

        manifests = [{"id": "SRC-0001", "status": "promoted", "quality_score": 98}]
        mock_get.return_value = manifests
        mock_promote.return_value = True
        result = batch_promote_to_obsidian(mock_workspace, min_score=95)
        assert result["total"] > 0


class TestBatchPromoteMain:
    @patch("sys.argv", ["batch_promote.py", "/tmp/kb", "wiki", "--min-score", "85"])
    def test_main_wiki_target(self):
        from dochris.admin.batch_promote import main

        with patch(
            "dochris.admin.batch_promote.batch_promote_to_wiki", return_value={"success": 1}
        ):
            main()

    @patch("sys.argv", ["batch_promote.py", "/tmp/kb", "curated"])
    def test_main_curated_target(self):
        from dochris.admin.batch_promote import main

        with patch(
            "dochris.admin.batch_promote.batch_promote_to_curated", return_value={"success": 1}
        ):
            main()

    @patch("sys.argv", ["batch_promote.py", "/tmp/kb", "obsidian"])
    def test_main_obsidian_target(self):
        from dochris.admin.batch_promote import main

        with patch(
            "dochris.admin.batch_promote.batch_promote_to_obsidian", return_value={"success": 1}
        ):
            main()
