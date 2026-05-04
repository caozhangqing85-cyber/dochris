"""
测试 recompile_missing_concepts.py 模块
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def mock_workspace(tmp_path):
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "manifests").mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    return workspace


@pytest.fixture
def sample_missing_concepts(mock_workspace):
    manifests = [
        {
            "id": "SRC-0001",
            "status": "compiled",
            "compiled_summary": {},
            "title": "文档1",
            "file_path": "raw/test1.pdf",
            "type": "article",
        },
    ]
    for m in manifests:
        f = mock_workspace / "manifests" / "sources" / f"{m['id']}.json"
        f.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return manifests


class TestFindMissingConceptsData:
    @patch("dochris.admin.recompile_missing_concepts.KB_PATH", create=True)
    def test_find_missing_concepts_data(self, mock_kb, mock_workspace):
        from dochris.admin.recompile_missing_concepts import find_missing_concepts_data

        mock_kb.__truediv__ = Mock(return_value=mock_workspace / "manifests" / "sources")
        logger = MagicMock()
        result = find_missing_concepts_data(logger)
        assert isinstance(result, list)


class TestSortByPriority:
    def test_sort_by_priority(self):
        from dochris.admin.recompile_missing_concepts import sort_by_priority

        manifests = [
            {"type": "video", "id": "1"},
            {"type": "article", "id": "2"},
            {"type": "pdf", "id": "3"},
            {"type": "ebook", "id": "4"},
        ]
        result = sort_by_priority(manifests)
        assert result[0]["type"] == "article"


class TestCompileStats:
    def test_compile_stats_initialization(self):
        from dochris.admin.recompile_missing_concepts import CompileStats

        stats = CompileStats()
        assert stats.total_success == 0
        assert stats.total_failed == 0


class TestRecompileMissingConceptsMain:
    @patch("dochris.admin.recompile_missing_concepts.KB_PATH", create=True)
    def test_verify_results(self, mock_kb, mock_workspace):
        from dochris.admin.recompile_missing_concepts import verify_results

        mock_kb.__truediv__ = Mock(return_value=mock_workspace / "manifests" / "sources")
        logger = MagicMock()
        result = verify_results(logger)
        assert isinstance(result, dict)
