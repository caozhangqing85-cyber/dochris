#!/usr/bin/env python3
"""
测试 phase3_query.py 模块
专门测试 phase3_query.py 的查询功能，使用 mock 隔离外部依赖
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 添加 src 目录到路径（如需要）
# sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def temp_workspace():
    """创建临时工作区"""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        # 创建必要的目录
        (workspace / "wiki" / "summaries").mkdir(parents=True, exist_ok=True)
        (workspace / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
        (workspace / "outputs" / "summaries").mkdir(parents=True, exist_ok=True)
        (workspace / "outputs" / "concepts").mkdir(parents=True, exist_ok=True)
        (workspace / "data").mkdir(parents=True, exist_ok=True)
        (workspace / "manifests" / "sources").mkdir(parents=True, exist_ok=True)
        (workspace / "logs").mkdir(parents=True, exist_ok=True)
        yield workspace


@pytest.fixture
def sample_concept_file(temp_workspace):
    """创建示例概念文件"""
    concept_file = temp_workspace / "wiki" / "concepts" / "机器学习.md"
    content = """# 机器学习

## 定义
机器学习是人工智能的一个分支，它使计算机能够从数据中学习并改进。

## 相关概念
- 深度学习
- 神经网络
- 数据挖掘
"""
    concept_file.write_text(content, encoding="utf-8")
    return concept_file


@pytest.fixture
def sample_summary_file(temp_workspace):
    """创建示例摘要文件"""
    summary_file = temp_workspace / "wiki" / "summaries" / "Python教程.md"
    content = """# Python教程

## 一句话摘要
Python 是一门简洁易学的编程语言。

## 要点
- Python 语法简洁
- 拥有丰富的库
- 适合初学者
- 应用广泛

## 详细摘要
Python 是一门高级编程语言，由 Guido van Rossum 于 1991 年创建。它具有简洁明了的语法，支持多种编程范式。

## Concepts
- 编程语言
- 脚本语言
- 面向对象
"""
    summary_file.write_text(content, encoding="utf-8")
    return summary_file


@pytest.fixture
def sample_manifest(temp_workspace):
    """创建示例 manifest"""
    manifest = {
        "id": "SRC-0001",
        "title": "Python教程",
        "file_path": "wiki/summaries/Python教程.md",
        "status": "compiled",
    }
    manifest_file = temp_workspace / "manifests" / "sources" / "SRC-0001.json"
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest


# ============================================================
# Test Cases - 概念搜索
# ============================================================


class TestPhase3ConceptSearch:
    """测试概念搜索功能"""

    @patch("dochris.phases.query_utils.WIKI_CONCEPTS_PATH")
    def test_search_concepts_wiki_priority(self, mock_path, temp_workspace, sample_concept_file):
        """测试概念搜索优先使用 wiki 目录"""
        from dochris.phases.phase3_query import search_concepts

        mock_path.__str__.return_value = str(temp_workspace / "wiki" / "concepts")
        mock_path.exists.return_value = True
        mock_path.glob = lambda x: (temp_workspace / "wiki" / "concepts").glob(x)

        results = search_concepts("机器学习", top_k=5)

        # 验证返回结果
        assert isinstance(results, list)
        if results:
            assert "name" in results[0]
            assert "definition" in results[0]

    def test_extract_concept_from_file(self, sample_concept_file):
        """测试从概念文件提取定义"""
        from dochris.phases.query_utils import _extract_concept

        text = sample_concept_file.read_text(encoding="utf-8")
        result = _extract_concept(sample_concept_file, text)

        assert result["name"] == "机器学习"
        assert "人工智能" in result["definition"]

    @patch("dochris.phases.query_utils.WIKI_CONCEPTS_PATH")
    @patch("dochris.phases.query_utils.OUTPUTS_CONCEPTS_PATH")
    def test_concept_fallback_to_outputs(self, mock_outputs, mock_wiki, temp_workspace):
        """测试概念搜索回退到 outputs 目录"""
        from dochris.phases.phase3_query import search_concepts

        # wiki 目录没有结果
        mock_wiki.__str__.return_value = str(temp_workspace / "wiki" / "concepts")
        mock_wiki.exists.return_value = False

        # outputs 目录有结果
        outputs_dir = temp_workspace / "outputs" / "concepts"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        concept_file = outputs_dir / "测试概念.md"
        concept_file.write_text("# 测试概念\n\n## 定义\n测试定义", encoding="utf-8")

        mock_outputs.__str__.return_value = str(outputs_dir)
        mock_outputs.exists.return_value = True
        mock_outputs.glob = lambda x: outputs_dir.glob(x)

        results = search_concepts("测试", top_k=5)

        assert isinstance(results, list)


# ============================================================
# Test Cases - 摘要搜索
# ============================================================


class TestPhase3SummarySearch:
    """测试摘要搜索功能"""

    @patch("dochris.phases.query_utils.WIKI_SUMMARIES_PATH")
    def test_search_summaries_wiki_priority(self, mock_path, temp_workspace, sample_summary_file):
        """测试摘要搜索优先使用 wiki 目录"""
        from dochris.phases.phase3_query import search_summaries

        mock_path.__str__.return_value = str(temp_workspace / "wiki" / "summaries")
        mock_path.exists.return_value = True
        mock_path.glob = lambda x: (temp_workspace / "wiki" / "summaries").glob(x)

        results = search_summaries("Python", top_k=5)

        # 验证返回结果
        assert isinstance(results, list)
        if results:
            assert "title" in results[0]
            assert "one_line" in results[0]
            assert "key_points" in results[0]

    def test_extract_summary_from_file(self, sample_summary_file):
        """测试从摘要文件提取内容"""
        from dochris.phases.query_utils import _extract_summary

        text = sample_summary_file.read_text(encoding="utf-8")
        result = _extract_summary(sample_summary_file, text)

        assert result["title"] == "Python教程"
        assert "简洁易学" in result["one_line"]
        assert len(result["key_points"]) > 0


# ============================================================
# Test Cases - 向量搜索
# ============================================================


class TestPhase3VectorSearch:
    """测试向量搜索功能"""

    def test_vector_search_import_error(self):
        """测试 ChromaDB 未安装时的处理"""
        # Mock import chromadb 语句来模拟 ImportError
        import builtins

        from dochris.phases.phase3_query import vector_search

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "chromadb":
                raise ImportError("chromadb not installed")
            return real_import(name, *args, **kwargs)

        logger = MagicMock()
        with patch("builtins.__import__", side_effect=mock_import):
            results = vector_search("测试查询", top_k=5, logger=logger)

        assert results == []
        logger.warning.assert_called()

    def test_vector_search_no_collections(self):
        """测试没有 collection 时的处理"""
        from dochris.phases.phase3_query import vector_search

        # 创建空的 mock 客户端
        mock_client = MagicMock()
        mock_client.list_collections.return_value = []

        with patch("chromadb.PersistentClient", return_value=mock_client):
            logger = MagicMock()
            results = vector_search("测试查询", top_k=5, logger=logger)

        assert results == []

    def test_vector_search_with_results(self):
        """测试有结果时的向量搜索"""
        from dochris.phases import phase3_query
        from dochris.phases.phase3_query import vector_search

        # 清除缓存
        phase3_query._chromadb_client_cache = None

        # Mock collection
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["文档1内容", "文档2内容"]],
            "metadatas": [[{"source": "test1"}, {"source": "test2"}]],
            "distances": [[0.1, 0.2]],
        }
        mock_collection.count.return_value = 2

        mock_client = MagicMock()
        mock_client.list_collections.return_value = [mock_collection]

        with patch("chromadb.PersistentClient", return_value=mock_client):
            logger = MagicMock()
            results = vector_search("测试查询", top_k=5, logger=logger)

        assert len(results) == 2
        assert results[0]["type"] == "vector"
        assert "text" in results[0]


# ============================================================
# Test Cases - 综合搜索
# ============================================================


class TestPhase3SearchAll:
    """测试综合搜索功能"""

    @patch("dochris.phases.phase3_query.vector_search")
    @patch("dochris.phases.phase3_query.search_summaries")
    @patch("dochris.phases.phase3_query.search_concepts")
    def test_search_all_combines_results(self, mock_concepts, mock_summaries, mock_vector):
        """测试 search_all 组合所有搜索结果"""
        from dochris.phases.phase3_query import search_all

        mock_concepts.return_value = [{"name": "概念1", "score": 10, "source": "wiki"}]
        mock_summaries.return_value = [{"title": "摘要1", "score": 8, "source": "wiki"}]
        mock_vector.return_value = [{"text": "向量结果", "score": 0.5}]

        result = search_all("测试查询", top_k=5)

        assert "concepts" in result
        assert "summaries" in result
        assert "vector_results" in result
        assert "search_sources" in result
        assert "wiki" in result["search_sources"]


# ============================================================
# Test Cases - Manifest 追踪
# ============================================================


class TestPhase3ManifestTracking:
    """测试 manifest 追踪功能"""

    @patch("dochris.phases.query_utils.MANIFESTS_PATH")
    def test_build_manifest_index(self, mock_path, temp_workspace):
        """测试构建 manifest 索引"""
        from dochris.phases import query_utils

        # 创建测试 manifest
        manifest_file = temp_workspace / "manifests" / "sources" / "SRC-0001.json"
        manifest_data = {
            "id": "SRC-0001",
            "file_path": "wiki/summaries/test.md",
            "title": "测试文档",
        }
        manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False), encoding="utf-8")

        manifests_dir = temp_workspace / "manifests" / "sources"
        # 直接设置 mock 对象的属性
        mock_path.__str__ = lambda _: str(manifests_dir)
        mock_path.exists.return_value = True
        mock_path.glob = lambda x: list(manifests_dir.glob(x))

        # 清除缓存确保重新读取
        query_utils._manifest_index_cache = None

        index = query_utils._build_manifest_index()

        assert "wiki/summaries/test.md" in index
        assert index["wiki/summaries/test.md"] == "SRC-0001"

    @patch("dochris.phases.query_utils._manifest_index_cache", None)
    @patch("dochris.phases.phase3_query._build_manifest_index")
    def test_get_manifest_id_caches_index(self, mock_build):
        """测试 manifest ID 查询缓存索引"""
        from dochris.phases.phase3_query import _get_manifest_id

        mock_build.return_value = {"wiki/summaries/test.md": "SRC-0001"}

        # 第一次调用
        result1 = _get_manifest_id("wiki/summaries/test.md")
        # 第二次调用应该使用缓存
        result2 = _get_manifest_id("wiki/summaries/test.md")

        assert result1 == "SRC-0001"
        assert result2 == "SRC-0001"
        mock_build.assert_called_once()


# ============================================================
# Test Cases - LLM 回答生成
# ============================================================


class TestPhase3LLMAnswer:
    """测试 LLM 回答生成功能"""

    @patch("dochris.phases.query_engine.openai")
    def test_generate_answer_with_context(self, mock_openai):
        """测试使用上下文生成回答"""
        from dochris.phases.phase3_query import generate_answer

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "这是生成的回答"
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        logger = MagicMock()

        concepts = [{"name": "概念1", "definition": "定义1"}]
        summaries = [{"title": "摘要1", "one_line": "一句话", "key_points": ["要点1"]}]
        vector_results = []

        answer = generate_answer(
            "测试问题", concepts, summaries, vector_results, mock_client, logger
        )

        assert answer == "这是生成的回答"
        mock_client.chat.completions.create.assert_called_once()

    @patch("dochris.phases.query_engine.openai")
    def test_generate_answer_no_context(self, mock_openai):
        """测试没有上下文时的回答"""
        from dochris.phases.phase3_query import generate_answer

        mock_client = MagicMock()
        logger = MagicMock()

        answer = generate_answer("测试问题", [], [], [], mock_client, logger)

        assert answer == "未找到相关内容。请尝试其他关键词。"

    def test_generate_answer_api_error(self):
        """测试 API 错误处理"""
        import openai

        from dochris.phases.phase3_query import generate_answer

        mock_client = MagicMock()
        # 创建一个正确的 APIError 对象
        error = openai.APIError("API 错误", request=MagicMock(), body=None)
        mock_client.chat.completions.create.side_effect = error

        logger = MagicMock()
        concepts = [{"name": "概念1", "definition": "定义1"}]

        answer = generate_answer("测试问题", concepts, [], [], mock_client, logger)

        assert answer is None
        logger.error.assert_called()


# ============================================================
# Test Cases - 客户端管理
# ============================================================


class TestPhase3ClientManagement:
    """测试客户端管理功能"""

    @patch("dochris.settings.OPENCLAW_CONFIG_PATH")
    @patch("builtins.open")
    def test_read_openclaw_config_success(self, mock_open, mock_path):
        """测试读取 OpenClaw 配置"""
        from dochris.phases.phase3_query import read_openclaw_config

        mock_config = {
            "models": {
                "providers": {
                    "zai": {"apiKey": "test-key-123456", "baseUrl": "https://api.example.com"}
                }
            }
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_config)

        logger = MagicMock()
        result = read_openclaw_config(logger)

        assert result is not None
        assert result["apiKey"] == "test-key-123456"
        assert result["baseUrl"] == "https://api.example.com"  # 添加 baseUrl 断言

    @patch("dochris.settings.OPENCLAW_CONFIG_PATH")
    @patch("builtins.open")
    def test_read_openclaw_config_file_not_found(self, mock_open, mock_path):
        """测试配置文件不存在"""
        from dochris.phases.phase3_query import read_openclaw_config

        mock_open.side_effect = FileNotFoundError()

        logger = MagicMock()
        result = read_openclaw_config(logger)

        assert result is None
        logger.error.assert_called()

    @patch("dochris.phases.query_engine.read_openclaw_config")
    def test_create_client_from_openclaw_config(self, mock_read_config):
        """测试从 OpenClaw 配置创建客户端"""
        from dochris.phases.phase3_query import create_client

        mock_read_config.return_value = {"apiKey": "test-key", "baseUrl": "https://api.example.com"}

        with patch("dochris.phases.query_engine.openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            logger = MagicMock()
            client = create_client(logger)

            assert client is not None
            mock_openai.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "env-key-12345"})
    @patch("dochris.phases.query_engine.read_openclaw_config")
    def test_create_client_from_env_fallback(self, mock_read_config):
        """测试从环境变量创建客户端（fallback）"""
        from dochris.phases.phase3_query import create_client

        mock_read_config.return_value = None

        with patch("dochris.phases.query_engine.openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            logger = MagicMock()
            client = create_client(logger)

            assert client is not None


# ============================================================
# Test Cases - 统一查询
# ============================================================


class TestPhase3UnifiedQuery:
    """测试统一查询功能"""

    @patch("dochris.phases.phase3_query.create_client")
    @patch("dochris.phases.phase3_query.vector_search")
    @patch("dochris.phases.phase3_query.search_summaries")
    @patch("dochris.phases.phase3_query.search_concepts")
    def test_query_concept_mode(self, mock_concepts, mock_summaries, mock_vector, mock_client):
        """测试概念模式查询"""
        from dochris.phases.phase3_query import query

        mock_concepts.return_value = [{"name": "概念1", "score": 10, "source": "wiki"}]
        mock_client.return_value = MagicMock()
        logger = MagicMock()

        result = query("测试查询", mode="concept", logger=logger)

        assert result["mode"] == "concept"
        assert len(result["concepts"]) > 0
        mock_concepts.assert_called_once()

    @patch("dochris.phases.phase3_query.create_client")
    @patch("dochris.phases.phase3_query.vector_search")
    @patch("dochris.phases.phase3_query.search_summaries")
    @patch("dochris.phases.phase3_query.search_concepts")
    def test_query_summary_mode(self, mock_concepts, mock_summaries, mock_vector, mock_client):
        """测试摘要模式查询"""
        from dochris.phases.phase3_query import query

        mock_summaries.return_value = [{"title": "摘要1", "score": 10, "source": "wiki"}]
        mock_client.return_value = MagicMock()
        logger = MagicMock()

        result = query("测试查询", mode="summary", logger=logger)

        assert result["mode"] == "summary"
        assert len(result["summaries"]) > 0
        mock_summaries.assert_called_once()

    @patch("dochris.phases.phase3_query.create_client")
    @patch("dochris.phases.phase3_query.vector_search")
    @patch("dochris.phases.phase3_query.search_summaries")
    @patch("dochris.phases.phase3_query.search_concepts")
    def test_query_vector_mode(self, mock_concepts, mock_summaries, mock_vector, mock_client):
        """测试向量模式查询"""
        from dochris.phases.phase3_query import query

        mock_vector.return_value = [{"text": "结果", "score": 0.5}]
        mock_client.return_value = MagicMock()
        logger = MagicMock()

        result = query("测试查询", mode="vector", logger=logger)

        assert result["mode"] == "vector"
        assert len(result["vector_results"]) > 0
        mock_vector.assert_called_once()

    @patch("dochris.phases.phase3_query.create_client")
    @patch("dochris.phases.phase3_query.generate_answer")
    @patch("dochris.phases.phase3_query.vector_search")
    @patch("dochris.phases.phase3_query.search_summaries")
    @patch("dochris.phases.phase3_query.search_concepts")
    def test_query_combined_mode(
        self, mock_concepts, mock_summaries, mock_vector, mock_generate, mock_client
    ):
        """测试组合模式查询"""
        from dochris.phases.phase3_query import query

        mock_concepts.return_value = [{"name": "概念1", "score": 10, "source": "wiki"}]
        mock_summaries.return_value = [{"title": "摘要1", "score": 8, "source": "wiki"}]
        mock_vector.return_value = [{"text": "结果", "score": 0.5}]
        mock_generate.return_value = "AI 回答"
        mock_client.return_value = MagicMock()
        logger = MagicMock()

        result = query("测试查询", mode="combined", logger=logger)

        assert result["mode"] == "combined"
        assert result["answer"] == "AI 回答"
        mock_generate.assert_called_once()
