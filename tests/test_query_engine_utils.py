"""补充测试 query_engine.py 和 query_utils.py — 覆盖纯函数"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestPrintResult:
    """覆盖 query_engine.print_result"""

    def test_print_result_with_all_sections(self):
        """打印包含所有部分的结果"""
        from dochris.phases.query_engine import print_result

        result = {
            "query": "测试查询",
            "mode": "combined",
            "time_seconds": 0.5,
            "concepts": [
                {
                    "name": "机器学习",
                    "score": 0.9,
                    "source": "obsidian",
                    "manifest_id": "SRC-0001",
                    "definition": "一种人工智能方法",
                }
            ],
            "summaries": [
                {
                    "title": "测试摘要",
                    "score": 0.8,
                    "manifest_id": "SRC-0002",
                    "one_line": "这是一句话摘要",
                }
            ],
            "vector_results": [
                {"source": "wiki", "score": 0.95, "text": "向量搜索结果文本"},
            ],
            "answer": "这是AI回答",
            "search_sources": ["vector", "keyword"],
        }

        with patch("builtins.print") as mock_print:
            print_result(result)

        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "测试查询" in output
        assert "机器学习" in output
        assert "AI 回答" in output

    def test_print_result_empty(self):
        """打印空结果"""
        from dochris.phases.query_engine import print_result

        result = {
            "query": "空查询",
            "mode": "concept",
            "time_seconds": 0.1,
            "concepts": [],
            "summaries": [],
            "vector_results": [],
            "answer": None,
        }

        with patch("builtins.print") as mock_print:
            print_result(result)

        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "空查询" in output


class TestExtractConcept:
    """覆盖 query_utils._extract_concept"""

    def test_extract_concept_with_definition(self):
        """提取概念定义"""
        from dochris.phases.query_utils import _extract_concept

        text = "# 机器学习\n\n## 定义\n\n机器学习是一种AI方法\n它使用数据训练模型\n\n## 参考\n\n其他内容"
        result = _extract_concept(Path("机器学习.md"), text)

        assert result["name"] == "机器学习"
        assert "AI方法" in result["definition"]
        assert "其他内容" not in result["definition"]

    def test_extract_concept_no_definition_header(self):
        """没有定义标题"""
        from dochris.phases.query_utils import _extract_concept

        text = "# 概念\n\n一些描述文字\n\n## 参考\n\n更多内容"
        result = _extract_concept(Path("概念.md"), text)

        assert result["name"] == "概念"


class TestExtractSummary:
    """覆盖 query_utils._extract_summary"""

    def test_extract_summary_full(self):
        """提取完整摘要"""
        from dochris.phases.query_utils import _extract_summary

        text = "# 标题\n\n## 一句话摘要\n\n这是摘要内容\n\n## 要点\n\n- 要点一\n- 要点二\n\n## 详情\n\n更多内容"
        result = _extract_summary(Path("test.md"), text)

        assert result["one_line"] == "这是摘要内容"
        assert len(result["key_points"]) == 2
        assert "要点一" in result["key_points"]

    def test_extract_summary_no_sections(self):
        """没有摘要和要点部分"""
        from dochris.phases.query_utils import _extract_summary

        text = "# 标题\n\n只有普通内容"
        result = _extract_summary(Path("test.md"), text)

        assert result["one_line"] == ""
        assert result["key_points"] == []


class TestBuildManifestIndex:
    """覆盖 query_utils._build_manifest_index"""

    def test_build_index_empty_dir(self, tmp_path):
        """空目录返回空索引"""
        from dochris.phases import query_utils

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        with patch.object(query_utils, "MANIFESTS_PATH", manifests_dir):
            result = query_utils._build_manifest_index()

        assert result == {}

    def test_build_index_with_manifests(self, tmp_path):
        """有 manifest 文件时建立索引"""
        from dochris.phases import query_utils

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        manifest = {
            "id": "SRC-0001",
            "file_path": "raw/test.pdf",
            "title": "测试文档",
        }
        (manifests_dir / "SRC-0001.json").write_text(json.dumps(manifest), encoding="utf-8")

        with patch.object(query_utils, "MANIFESTS_PATH", manifests_dir):
            result = query_utils._build_manifest_index()

        assert "raw/test.pdf" in result
        assert result["raw/test.pdf"] == "SRC-0001"

    def test_build_index_bad_json(self, tmp_path):
        """损坏的 JSON 被跳过"""
        from dochris.phases import query_utils

        manifests_dir = tmp_path / "manifests" / "sources"
        manifests_dir.mkdir(parents=True)

        (manifests_dir / "SRC-0002.json").write_text("bad json", encoding="utf-8")

        with patch.object(query_utils, "MANIFESTS_PATH", manifests_dir):
            result = query_utils._build_manifest_index()

        assert result == {}


class TestKeywordSearch:
    """覆盖 query_utils._keyword_search"""

    def test_keyword_search_no_dir(self, tmp_path):
        """搜索目录不存在"""
        from dochris.phases.query_utils import _keyword_search

        with patch("dochris.phases.query_utils.WIKI_CONCEPTS_PATH", tmp_path / "nonexistent"):
            result = _keyword_search("test", tmp_path / "nonexistent", 5, lambda p, t: {}, "wiki")

        assert result == []


class TestGetVectorStore:
    """覆盖 query_engine.get_vector_store"""

    def test_get_vector_store_caches(self):
        """get_vector_store 缓存结果"""
        from dochris.phases import query_engine

        mock_store = MagicMock()
        query_engine._vector_store_cache = mock_store

        result = query_engine.get_vector_store()
        assert result is mock_store

        # 清理
        query_engine._vector_store_cache = None


class TestSearchConcepts:
    """覆盖 query_engine.search_concepts"""

    def test_search_concepts_empty(self):
        """搜索概念返回空"""
        from dochris.phases.query_engine import search_concepts

        with patch("dochris.phases.query_engine.get_plugin_manager") as mock_pm:
            mock_pm.return_value.call_hook_firstresult.return_value = None
            with patch("dochris.phases.query_engine._keyword_search", return_value=[]):
                result = search_concepts("测试", top_k=3)

        assert result == []


class TestSearchSummaries:
    """覆盖 query_engine.search_summaries"""

    def test_search_summaries_empty(self):
        """搜索摘要返回空"""
        from dochris.phases.query_engine import search_summaries

        with patch("dochris.phases.query_engine.get_plugin_manager") as mock_pm:
            mock_pm.return_value.call_hook_firstresult.return_value = None
            with patch("dochris.phases.query_engine._keyword_search", return_value=[]):
                result = search_summaries("测试", top_k=3)

        assert result == []
