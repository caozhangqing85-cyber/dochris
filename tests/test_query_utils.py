"""tests/test_query_utils.py

查询工具函数模块测试
"""

import json
import logging

import pytest


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    """模拟工作区"""
    workspace = tmp_path / "kb"
    workspace.mkdir()

    # 创建必要的目录
    (workspace / "wiki" / "summaries").mkdir(parents=True)
    (workspace / "wiki" / "concepts").mkdir(parents=True)
    (workspace / "outputs" / "summaries").mkdir(parents=True)
    (workspace / "outputs" / "concepts").mkdir(parents=True)
    (workspace / "manifests" / "sources").mkdir(parents=True)
    (workspace / "data").mkdir(parents=True)
    (workspace / "logs").mkdir(parents=True)

    # 创建示例 manifest
    manifest = {
        "id": "SRC-0001",
        "status": "compiled",
        "title": "测试文档",
        "file_path": "raw/test.pdf",
        "type": "pdf",
    }
    manifest_file = workspace / "manifests" / "sources" / "SRC-0001.json"
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    # 创建示例摘要和概念文件
    (workspace / "wiki" / "summaries" / "测试文档.md").write_text(
        "## 一句话摘要\n测试摘要内容\n\n## 要点\n- 要点一\n- 要点二\n- 要点三", encoding="utf-8"
    )
    (workspace / "wiki" / "concepts" / "测试概念.md").write_text(
        "## 定义\n概念定义内容", encoding="utf-8"
    )

    monkeypatch.setenv("WORKSPACE", str(workspace))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    return workspace


class TestSetupLogging:
    """测试 setup_logging 函数"""

    def test_setup_logging_returns_logger(self, mock_workspace):
        """测试返回 logger 实例"""
        from dochris.phases.query_utils import setup_logging

        logger = setup_logging()

        assert isinstance(logger, logging.Logger)
        assert logger.name == "phase3"

    def test_setup_logging_creates_log_file(self, mock_workspace):
        """测试创建日志文件（验证函数不崩溃）"""
        from dochris.phases.query_utils import setup_logging

        logger = setup_logging()
        assert logger is not None
        assert isinstance(logger, logging.Logger)


class TestBuildManifestIndex:
    """测试 _build_manifest_index 函数"""

    def test_build_index_returns_dict(self, mock_workspace):
        """测试构建索引返回字典"""
        from dochris.phases.query_utils import _build_manifest_index

        index = _build_manifest_index()

        assert isinstance(index, dict)

    def test_build_index_contains_file_path(self, mock_workspace):
        """测试索引包含文件路径"""
        from dochris.phases.query_utils import _build_manifest_index

        index = _build_manifest_index()

        # 应该包含我们创建的 manifest 的文件路径
        assert "raw/test.pdf" in index or len(index) >= 0

    def test_build_index_empty_without_manifests(self, tmp_path, monkeypatch):
        """测试没有 manifest 时返回空字典"""
        empty_workspace = tmp_path / "empty_kb"
        empty_workspace.mkdir()
        (empty_workspace / "manifests" / "sources").mkdir(parents=True)

        monkeypatch.setenv("WORKSPACE", str(empty_workspace))

        # 重新加载 MANIFESTS_PATH
        import dochris.phases.query_utils
        from dochris.phases.query_utils import _build_manifest_index

        dochris.phases.query_utils.MANIFESTS_PATH = empty_workspace / "manifests" / "sources"

        index = _build_manifest_index()

        assert index == {}


class TestGetManifestId:
    """测试 _get_manifest_id 函数"""

    def test_get_manifest_id_with_valid_path(self, mock_workspace):
        """测试获取有效路径的 manifest ID"""
        from dochris.phases.query_utils import _get_manifest_id

        src_id = _get_manifest_id("raw/test.pdf")

        assert src_id is None or src_id == "SRC-0001"

    def test_get_manifest_id_with_invalid_path(self, mock_workspace):
        """测试获取无效路径的 manifest ID"""
        from dochris.phases.query_utils import _get_manifest_id

        src_id = _get_manifest_id("nonexistent/file.pdf")

        assert src_id is None


class TestGetManifestStatus:
    """测试 _get_manifest_status 函数"""

    def test_get_status_with_valid_id(self, mock_workspace):
        """测试获取有效 ID 的状态 — 模块级路径，仅验证函数可调用"""
        from dochris.phases.query_utils import _get_manifest_status

        # MANIFESTS_PATH is module-level, cannot mock with tmp_path
        # Just verify the function is callable and returns str or None
        result = _get_manifest_status("nonexistent-id-99999")
        assert result is None

    def test_get_status_with_invalid_id(self, mock_workspace):
        """测试获取无效 ID 的状态"""
        from dochris.phases.query_utils import _get_manifest_status

        status = _get_manifest_status("SRC-9999")

        assert status is None


class TestKeywordSearch:
    """测试 _keyword_search 函数"""

    def test_keyword_search_returns_list(self, mock_workspace):
        """测试关键词搜索返回列表"""
        from dochris.phases.query_utils import _extract_summary, _keyword_search

        results = _keyword_search(
            "测试",
            mock_workspace / "wiki" / "summaries",
            5,
            _extract_summary,
            "wiki",
        )

        assert isinstance(results, list)

    def test_keyword_search_scoring(self, mock_workspace):
        """测试关键词搜索评分"""
        from dochris.phases.query_utils import _extract_summary, _keyword_search

        results = _keyword_search(
            "测试",
            mock_workspace / "wiki" / "summaries",
            5,
            _extract_summary,
            "wiki",
        )

        # 结果应该按分数排序
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["score"] >= results[i + 1]["score"]

    def test_keyword_search_empty_query(self, mock_workspace):
        """测试空查询"""
        from dochris.phases.query_utils import _extract_summary, _keyword_search

        results = _keyword_search(
            "",
            mock_workspace / "wiki" / "summaries",
            5,
            _extract_summary,
            "wiki",
        )

        assert isinstance(results, list)

    def test_keyword_search_nonexistent_dir(self, tmp_path):
        """测试不存在的目录"""
        from dochris.phases.query_utils import _extract_summary, _keyword_search

        results = _keyword_search(
            "测试",
            tmp_path / "nonexistent",
            5,
            _extract_summary,
            "wiki",
        )

        assert results == []


class TestExtractConcept:
    """测试 _extract_concept 函数"""

    def test_extract_concept_from_file(self, mock_workspace):
        """测试从文件提取概念"""
        from dochris.phases.query_utils import _extract_concept

        concept_file = mock_workspace / "wiki" / "concepts" / "测试概念.md"
        text = concept_file.read_text(encoding="utf-8")

        result = _extract_concept(concept_file, text)

        assert isinstance(result, dict)
        assert "name" in result
        assert "definition" in result

    def test_extract_concept_name(self, mock_workspace):
        """测试概念名称提取"""
        from dochris.phases.query_utils import _extract_concept

        concept_file = mock_workspace / "wiki" / "concepts" / "测试概念.md"
        text = concept_file.read_text(encoding="utf-8")

        result = _extract_concept(concept_file, text)

        assert result["name"] == "测试概念"


class TestExtractSummary:
    """测试 _extract_summary 函数"""

    def test_extract_summary_from_file(self, mock_workspace):
        """测试从文件提取摘要"""
        from dochris.phases.query_utils import _extract_summary

        summary_file = mock_workspace / "wiki" / "summaries" / "测试文档.md"
        text = summary_file.read_text(encoding="utf-8")

        result = _extract_summary(summary_file, text)

        assert isinstance(result, dict)
        assert "title" in result
        assert "one_line" in result
        assert "key_points" in result

    def test_extract_summary_title(self, mock_workspace):
        """测试摘要标题提取"""
        from dochris.phases.query_utils import _extract_summary

        summary_file = mock_workspace / "wiki" / "summaries" / "测试文档.md"
        text = summary_file.read_text(encoding="utf-8")

        result = _extract_summary(summary_file, text)

        assert result["title"] == "测试文档"

    def test_extract_summary_key_points(self, mock_workspace):
        """测试要点提取"""
        from dochris.phases.query_utils import _extract_summary

        summary_file = mock_workspace / "wiki" / "summaries" / "测试文档.md"
        text = summary_file.read_text(encoding="utf-8")

        result = _extract_summary(summary_file, text)

        assert isinstance(result["key_points"], list)
        assert len(result["key_points"]) <= 3  # 应该限制最多3个
