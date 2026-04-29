"""
测试 phase3_query.py 模块
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def mock_workspace(tmp_path):
    """创建模拟工作区"""
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "wiki").mkdir()
    (workspace / "wiki" / "summaries").mkdir(parents=True)
    (workspace / "wiki" / "concepts").mkdir(parents=True)
    (workspace / "outputs").mkdir()
    (workspace / "outputs" / "summaries").mkdir(parents=True)
    (workspace / "outputs" / "concepts").mkdir(parents=True)
    (workspace / "data").mkdir()
    (workspace / "manifests").mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    return workspace


@pytest.fixture
def sample_concept_file(mock_workspace):
    """创建示例概念文件"""
    concepts_dir = mock_workspace / "wiki" / "concepts"
    content = """# 测试概念

## 定义
这是测试概念的定义。
"""
    concept_file = concepts_dir / "测试概念.md"
    concept_file.write_text(content, encoding="utf-8")
    return concept_file


@pytest.fixture
def sample_summary_file(mock_workspace):
    """创建示例摘要文件"""
    summaries_dir = mock_workspace / "wiki" / "summaries"
    content = """# 测试文档

## 一句话摘要
这是一句话摘要。

## 要点
- 要点一
- 要点二
- 要点三
"""
    summary_file = summaries_dir / "测试文档.md"
    summary_file.write_text(content, encoding="utf-8")
    return summary_file


@pytest.fixture
def sample_manifest(mock_workspace):
    """创建示例 manifest"""
    manifest = {
        "id": "SRC-0001",
        "status": "compiled",
        "title": "测试文档",
        "file_path": "wiki/summaries/测试文档.md",
        "type": "pdf",
    }
    manifest_file = mock_workspace / "manifests" / "sources" / "SRC-0001.json"
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest


class TestPhase3SetupLogging:
    """测试日志设置功能"""

    def test_setup_logging_returns_logger(self, mock_workspace):
        """测试 setup_logging 返回 logger"""
        from dochris.phases.phase3_query import LOGS_PATH, setup_logging

        original_path = LOGS_PATH
        try:
            import phase3_query
            logs_dir = mock_workspace / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            phase3_query.LOGS_PATH = logs_dir

            logger = setup_logging()

            assert logger is not None
            assert logger.name == "phase3"
        finally:
            phase3_query.LOGS_PATH = original_path

    def test_setup_logging_creates_log_file(self, mock_workspace):
        """测试 setup_logging 创建日志文件"""
        from dochris.phases.phase3_query import LOGS_PATH, setup_logging

        original_path = LOGS_PATH
        try:
            import phase3_query
            logs_dir = mock_workspace / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            phase3_query.LOGS_PATH = logs_dir

            setup_logging()

            log_files = list(logs_dir.glob("phase3_*.log"))
            assert len(log_files) > 0
        finally:
            phase3_query.LOGS_PATH = original_path


class TestPhase3ManifestIndex:
    """测试 Manifest 索引功能"""

    def test_build_manifest_index_empty(self, mock_workspace):
        """测试空的 manifest 索引"""
        from dochris.phases.phase3_query import MANIFESTS_PATH, _build_manifest_index

        # 保存原始路径
        original_path = MANIFESTS_PATH
        try:
            # 临时修改模块常量
            import phase3_query
            phase3_query.MANIFESTS_PATH = mock_workspace / "manifests" / "sources"
            # 清除缓存
            phase3_query._manifest_index_cache = None

            index = _build_manifest_index()

            assert index == {}
        finally:
            # 恢复原始路径
            phase3_query.MANIFESTS_PATH = original_path
            phase3_query._manifest_index_cache = None

    def test_build_manifest_index_with_manifests(self, mock_workspace, sample_manifest):
        """测试构建 manifest 索引"""
        from dochris.phases.phase3_query import MANIFESTS_PATH, _build_manifest_index

        original_path = MANIFESTS_PATH
        try:
            import phase3_query
            phase3_query.MANIFESTS_PATH = mock_workspace / "manifests" / "sources"
            phase3_query._manifest_index_cache = None

            index = _build_manifest_index()

            assert "wiki/summaries/测试文档.md" in index
            assert index["wiki/summaries/测试文档.md"] == "SRC-0001"
        finally:
            phase3_query.MANIFESTS_PATH = original_path
            phase3_query._manifest_index_cache = None

    def test_get_manifest_id(self, mock_workspace, sample_manifest):
        """测试获取 manifest ID"""
        from dochris.phases.phase3_query import MANIFESTS_PATH, _get_manifest_id

        original_path = MANIFESTS_PATH
        try:
            import phase3_query
            phase3_query.MANIFESTS_PATH = mock_workspace / "manifests" / "sources"
            phase3_query._manifest_index_cache = None

            manifest_id = _get_manifest_id("wiki/summaries/测试文档.md")

            assert manifest_id == "SRC-0001"
        finally:
            phase3_query.MANIFESTS_PATH = original_path
            phase3_query._manifest_index_cache = None

    def test_get_manifest_status(self, mock_workspace, sample_manifest):
        """测试获取 manifest 状态"""
        from dochris.phases.phase3_query import MANIFESTS_PATH, _get_manifest_status

        original_path = MANIFESTS_PATH
        try:
            import phase3_query
            phase3_query.MANIFESTS_PATH = mock_workspace / "manifests" / "sources"

            status = _get_manifest_status("SRC-0001")

            assert status == "compiled"
        finally:
            phase3_query.MANIFESTS_PATH = original_path


class TestPhase3ConceptSearch:
    """测试概念搜索功能"""

    def test_search_concepts_empty_directory(self, mock_workspace):
        """测试搜索空目录"""
        from dochris.phases.phase3_query import (
            OUTPUTS_CONCEPTS_PATH,
            WIKI_CONCEPTS_PATH,
            search_concepts,
        )

        original_wiki = WIKI_CONCEPTS_PATH
        original_outputs = OUTPUTS_CONCEPTS_PATH
        try:
            import phase3_query
            phase3_query.WIKI_CONCEPTS_PATH = mock_workspace / "wiki" / "concepts"
            phase3_query.OUTPUTS_CONCEPTS_PATH = mock_workspace / "outputs" / "concepts"

            results = search_concepts("测试")

            assert results == []
        finally:
            phase3_query.WIKI_CONCEPTS_PATH = original_wiki
            phase3_query.OUTPUTS_CONCEPTS_PATH = original_outputs

    def test_search_concepts_with_results(self, mock_workspace, sample_concept_file):
        """测试搜索有结果"""
        from dochris.phases.phase3_query import (
            OUTPUTS_CONCEPTS_PATH,
            WIKI_CONCEPTS_PATH,
            search_concepts,
        )

        original_wiki = WIKI_CONCEPTS_PATH
        original_outputs = OUTPUTS_CONCEPTS_PATH
        try:
            import phase3_query
            phase3_query.WIKI_CONCEPTS_PATH = mock_workspace / "wiki" / "concepts"
            phase3_query.OUTPUTS_CONCEPTS_PATH = mock_workspace / "outputs" / "concepts"

            results = search_concepts("测试")

            assert len(results) > 0
            assert results[0]["name"] == "测试概念"
            assert "definition" in results[0]
        finally:
            phase3_query.WIKI_CONCEPTS_PATH = original_wiki
            phase3_query.OUTPUTS_CONCEPTS_PATH = original_outputs

    def test_search_concepts_fallback_to_outputs(self, mock_workspace):
        """测试搜索 fallback 到 outputs"""
        from dochris.phases.phase3_query import (
            OUTPUTS_CONCEPTS_PATH,
            WIKI_CONCEPTS_PATH,
            search_concepts,
        )

        # 在 outputs 目录创建文件
        outputs_dir = mock_workspace / "outputs" / "concepts"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        content = "# 测试概念\n## 定义\n这是定义。"
        (outputs_dir / "测试概念.md").write_text(content, encoding="utf-8")

        original_wiki = WIKI_CONCEPTS_PATH
        original_outputs = OUTPUTS_CONCEPTS_PATH
        try:
            import phase3_query
            phase3_query.WIKI_CONCEPTS_PATH = mock_workspace / "wiki" / "concepts"
            phase3_query.OUTPUTS_CONCEPTS_PATH = outputs_dir

            results = search_concepts("测试")

            assert len(results) > 0
        finally:
            phase3_query.WIKI_CONCEPTS_PATH = original_wiki
            phase3_query.OUTPUTS_CONCEPTS_PATH = original_outputs


class TestPhase3SummarySearch:
    """测试摘要搜索功能"""

    def test_search_summaries_empty_directory(self, mock_workspace):
        """测试搜索空目录"""
        from dochris.phases.phase3_query import (
            OUTPUTS_SUMMARIES_PATH,
            WIKI_SUMMARIES_PATH,
            search_summaries,
        )

        original_wiki = WIKI_SUMMARIES_PATH
        original_outputs = OUTPUTS_SUMMARIES_PATH
        try:
            import phase3_query
            phase3_query.WIKI_SUMMARIES_PATH = mock_workspace / "wiki" / "summaries"
            phase3_query.OUTPUTS_SUMMARIES_PATH = mock_workspace / "outputs" / "summaries"

            results = search_summaries("测试")

            assert results == []
        finally:
            phase3_query.WIKI_SUMMARIES_PATH = original_wiki
            phase3_query.OUTPUTS_SUMMARIES_PATH = original_outputs

    def test_search_summaries_with_results(self, mock_workspace, sample_summary_file):
        """测试搜索有结果"""
        from dochris.phases.phase3_query import (
            OUTPUTS_SUMMARIES_PATH,
            WIKI_SUMMARIES_PATH,
            search_summaries,
        )

        original_wiki = WIKI_SUMMARIES_PATH
        original_outputs = OUTPUTS_SUMMARIES_PATH
        try:
            import phase3_query
            phase3_query.WIKI_SUMMARIES_PATH = mock_workspace / "wiki" / "summaries"
            phase3_query.OUTPUTS_SUMMARIES_PATH = mock_workspace / "outputs" / "summaries"

            results = search_summaries("测试")

            assert len(results) > 0
            assert results[0]["title"] == "测试文档"
            assert "one_line" in results[0]
        finally:
            phase3_query.WIKI_SUMMARIES_PATH = original_wiki
            phase3_query.OUTPUTS_SUMMARIES_PATH = original_outputs


class TestPhase3VectorSearch:
    """测试向量搜索功能"""

    def test_vector_search_no_chromadb(self, mock_workspace):
        """测试没有 ChromaDB 时的向量搜索"""
        from dochris.phases.phase3_query import DATA_PATH, vector_search

        original_path = DATA_PATH
        try:
            import phase3_query
            phase3_query.DATA_PATH = mock_workspace / "data"
            phase3_query._chromadb_client_cache = None

            # Mock import chromadb 语句来模拟 ImportError
            import builtins
            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == 'chromadb':
                    raise ImportError("chromadb not installed")
                return real_import(name, *args, **kwargs)

            with patch('builtins.__import__', side_effect=mock_import):
                results = vector_search("测试", 5)

            assert results == []
        finally:
            phase3_query.DATA_PATH = original_path
            phase3_query._chromadb_client_cache = None

    def test_vector_search_with_mock_client(self, mock_workspace):
        """测试模拟客户端的向量搜索"""
        from dochris.phases.phase3_query import DATA_PATH, vector_search

        original_path = DATA_PATH
        try:
            import phase3_query
            phase3_query.DATA_PATH = mock_workspace / "data"
            phase3_query._chromadb_client_cache = None

            # 创建真实的 chromadb mock 客户端
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.count.return_value = 10
            mock_collection.query.return_value = {
                'documents': [['文档1内容', '文档2内容']],
                'metadatas': [[{'source': 'file1.pdf'}, {'source': 'file2.pdf'}]],
                'distances': [[0.1, 0.2]]
            }
            mock_client.list_collections.return_value = [mock_collection]

            # 使用 patch 来替换 chromadb.PersistentClient
            with patch('chromadb.PersistentClient', return_value=mock_client):
                results = vector_search("测试", 5)

            assert len(results) > 0
            assert results[0]["type"] == "vector"
        finally:
            phase3_query.DATA_PATH = original_path
            phase3_query._chromadb_client_cache = None


class TestPhase3GenerateAnswer:
    """测试 LLM 回答生成"""

    @patch('dochris.phases.phase3_query.create_client')
    def test_generate_answer_no_context(self, mock_create_client):
        """测试无上下文时的回答"""
        from dochris.phases.phase3_query import generate_answer

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_logger = MagicMock()

        result = generate_answer("测试", [], [], [], mock_client, mock_logger)

        assert result == "未找到相关内容。请尝试其他关键词。"

    @patch('dochris.phases.phase3_query.create_client')
    def test_generate_answer_with_context(self, mock_create_client):
        """测试有上下文时的回答"""
        from dochris.phases.phase3_query import generate_answer

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="测试回答"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_create_client.return_value = mock_client

        mock_logger = MagicMock()

        concepts = [{"name": "测试概念", "definition": "测试定义"}]
        summaries = [{"title": "测试", "one_line": "测试摘要", "key_points": ["要点1"]}]

        result = generate_answer("测试", concepts, summaries, [], mock_client, mock_logger)

        assert result == "测试回答"

    @patch('dochris.phases.phase3_query.create_client')
    def test_generate_answer_api_error(self, mock_create_client):
        """测试 API 错误处理"""
        import openai

        from dochris.phases.phase3_query import generate_answer

        mock_client = MagicMock()
        # 创建一个简单的 APIError 模拟
        error = openai.APIError("API 错误", request=MagicMock(), body=None)
        mock_client.chat.completions.create.side_effect = error
        mock_create_client.return_value = mock_client

        mock_logger = MagicMock()

        concepts = [{"name": "测试概念", "definition": "测试定义"}]

        result = generate_answer("测试", concepts, [], [], mock_client, mock_logger)

        assert result is None


class TestPhase3ClientManagement:
    """测试客户端管理功能"""

    @patch('dochris.phases.phase3_query.read_openclaw_config')
    def test_create_client_from_openclaw_config(self, mock_read_config):
        """测试从 OpenClaw 配置创建客户端"""
        from dochris.phases.phase3_query import create_client

        mock_read_config.return_value = {
            "apiKey": "test-key",
            "baseUrl": "https://api.test.com"
        }

        with patch('dochris.phases.phase3_query.openai.OpenAI') as mock_openai:
            mock_openai.return_value = MagicMock()
            client = create_client()

        assert client is not None

    @patch('dochris.phases.phase3_query.read_openclaw_config')
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'env-key'})
    def test_create_client_from_env_var(self, mock_read_config):
        """测试从环境变量创建客户端"""
        from dochris.phases.phase3_query import create_client

        mock_read_config.return_value = None

        with patch('dochris.phases.phase3_query.openai.OpenAI') as mock_openai:
            mock_openai.return_value = MagicMock()
            client = create_client()

        assert client is not None

    def test_read_openclaw_config(self, mock_workspace, monkeypatch, tmp_path):
        """测试读取 OpenClaw 配置（使用临时目录，不污染真实配置文件）"""
        from dochris.phases.phase3_query import read_openclaw_config

        # 使用 tmp_path 而不是真实的 ~/.openclaw/openclaw.json
        config_file = tmp_path / "openclaw.json"
        config_content = {
            "models": {
                "providers": {
                    "zai": {
                        "apiKey": "test-api-key",
                        "baseUrl": "https://api.zai.com"
                    }
                }
            }
        }
        config_file.write_text(json.dumps(config_content), encoding="utf-8")

        with patch('dochris.phases.phase3_query.OPENCLAW_CONFIG_PATH', str(config_file)):
            config = read_openclaw_config()

        assert config is not None
        assert config["apiKey"] == "test-api-key"
        assert config["baseUrl"] == "https://api.zai.com"


class TestPhase3Query:
    """测试统一查询功能"""

    @patch('dochris.phases.phase3_query.search_concepts')
    @patch('dochris.phases.phase3_query.search_summaries')
    @patch('dochris.phases.phase3_query.vector_search')
    @patch('dochris.phases.phase3_query.create_client')
    def test_query_concept_mode(self, mock_create, mock_vector, mock_summaries, mock_concepts):
        """测试概念查询模式"""
        from dochris.phases.phase3_query import query

        mock_concepts.return_value = [{"name": "测试", "definition": "定义", "source": "wiki"}]
        mock_summaries.return_value = []
        mock_vector.return_value = []
        mock_create.return_value = None

        result = query("测试", mode="concept")

        assert result["mode"] == "concept"
        assert len(result["concepts"]) > 0
        assert result["search_sources"] == ["wiki"]

    @patch('dochris.phases.phase3_query.search_concepts')
    @patch('dochris.phases.phase3_query.search_summaries')
    @patch('dochris.phases.phase3_query.vector_search')
    @patch('dochris.phases.phase3_query.create_client')
    def test_query_summary_mode(self, mock_create, mock_vector, mock_summaries, mock_concepts):
        """测试摘要查询模式"""
        from dochris.phases.phase3_query import query

        mock_concepts.return_value = []
        mock_summaries.return_value = [{"title": "测试", "one_line": "摘要", "source": "wiki"}]
        mock_vector.return_value = []
        mock_create.return_value = None

        result = query("测试", mode="summary")

        assert result["mode"] == "summary"
        assert len(result["summaries"]) > 0

    @patch('dochris.phases.phase3_query.search_concepts')
    @patch('dochris.phases.phase3_query.search_summaries')
    @patch('dochris.phases.phase3_query.vector_search')
    @patch('dochris.phases.phase3_query.create_client')
    def test_query_vector_mode(self, mock_create, mock_vector, mock_summaries, mock_concepts):
        """测试向量查询模式"""
        from dochris.phases.phase3_query import query

        mock_concepts.return_value = []
        mock_summaries.return_value = []
        mock_vector.return_value = [{"text": "内容", "score": 0.1}]
        mock_create.return_value = None

        result = query("测试", mode="vector")

        assert result["mode"] == "vector"
        assert len(result["vector_results"]) > 0

    @patch('dochris.phases.phase3_query.search_concepts')
    @patch('dochris.phases.phase3_query.search_summaries')
    @patch('dochris.phases.phase3_query.vector_search')
    @patch('dochris.phases.phase3_query.create_client')
    def test_query_all_mode(self, mock_create, mock_vector, mock_summaries, mock_concepts):
        """测试全部查询模式"""
        from dochris.phases.phase3_query import query

        mock_concepts.return_value = [{"name": "测试", "definition": "定义", "source": "wiki"}]
        mock_summaries.return_value = [{"title": "测试", "one_line": "摘要", "source": "wiki"}]
        mock_vector.return_value = [{"text": "内容", "score": 0.1}]
        mock_create.return_value = None

        result = query("测试", mode="all")

        assert result["mode"] == "all"
        assert len(result["concepts"]) > 0
        assert len(result["summaries"]) > 0
        assert len(result["vector_results"]) > 0


class TestPhase3ExtractFunctions:
    """测试提取函数"""

    def test_extract_concept(self):
        """测试概念提取"""
        from dochris.phases.phase3_query import _extract_concept

        text = """# 测试概念

## 定义
这是概念的详细定义。
更多定义内容。

## 其他
其他内容。
"""
        result = _extract_concept(Path("test.md"), text)

        assert result["name"] == "test"
        assert "概念的详细定义" in result["definition"]

    def test_extract_summary(self):
        """测试摘要提取"""
        from dochris.phases.phase3_query import _extract_summary

        text = """# 测试文档

## 一句话摘要
这是测试摘要。

## 要点
- 要点一
- 要点二
- 要点三
- 要点四
"""
        result = _extract_summary(Path("test.md"), text)

        assert result["title"] == "test"
        assert result["one_line"] == "这是测试摘要。"  # 包含句号
        assert len(result["key_points"]) == 3  # 限制为3个


class TestPhase3SearchAll:
    """测试搜索全部功能"""

    @patch('dochris.phases.phase3_query.search_concepts')
    @patch('dochris.phases.phase3_query.search_summaries')
    @patch('dochris.phases.phase3_query.vector_search')
    def test_search_all_wiki_priority(self, mock_vector, mock_summaries, mock_concepts):
        """测试 wiki 优先搜索"""
        from dochris.phases.phase3_query import search_all

        mock_concepts.return_value = [{"name": "测试", "definition": "定义", "source": "wiki"}]
        mock_summaries.return_value = [{"title": "测试", "one_line": "摘要", "source": "wiki"}]
        mock_vector.return_value = [{"text": "内容", "score": 0.1}]

        result = search_all("测试")

        assert "concepts" in result
        assert "summaries" in result
        assert "vector_results" in result
        assert "search_sources" in result
        assert "wiki" in result["search_sources"]


class TestPhase3PrintResult:
    """测试结果打印"""

    @patch('builtins.print')
    def test_print_result_basic(self, mock_print):
        """测试基本结果打印"""
        from dochris.phases.phase3_query import print_result

        result = {
            "query": "测试",
            "mode": "combined",
            "time_seconds": 1.5,
            "concepts": [],
            "summaries": [],
            "vector_results": [],
            "search_sources": [],
            "answer": None  # 添加缺少的字段
        }

        print_result(result)

        mock_print.assert_called()


class TestPhase3EdgeCases:
    """测试边界情况"""

    @patch('dochris.phases.phase3_query.search_concepts')
    @patch('dochris.phases.phase3_query.search_summaries')
    @patch('dochris.phases.phase3_query.vector_search')
    def test_empty_query(self, mock_vector, mock_summaries, mock_concepts):
        """测试空查询"""
        from dochris.phases.phase3_query import query

        mock_concepts.return_value = []
        mock_summaries.return_value = []
        mock_vector.return_value = []

        result = query("", mode="combined")

        assert result is not None

    @patch('dochris.phases.phase3_query.search_concepts')
    @patch('dochris.phases.phase3_query.search_summaries')
    @patch('dochris.phases.phase3_query.vector_search')
    def test_special_characters_query(self, mock_vector, mock_summaries, mock_concepts):
        """测试特殊字符查询"""
        from dochris.phases.phase3_query import query

        mock_concepts.return_value = []
        mock_summaries.return_value = []
        mock_vector.return_value = []

        result = query("测试!@#$%^&*()", mode="combined")

        assert result is not None

    @patch('dochris.phases.phase3_query.search_concepts')
    @patch('dochris.phases.phase3_query.search_summaries')
    @patch('dochris.phases.phase3_query.vector_search')
    def test_very_long_query(self, mock_vector, mock_summaries, mock_concepts):
        """测试超长查询"""
        from dochris.phases.phase3_query import query

        mock_concepts.return_value = []
        mock_summaries.return_value = []
        mock_vector.return_value = []

        long_query = "测试" * 1000
        result = query(long_query, mode="combined")

        assert result is not None
