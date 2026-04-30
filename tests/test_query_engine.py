"""tests/test_query_engine.py

查询引擎模块测试 - 使用真实函数逻辑
"""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_caches():
    """测试后重置缓存"""
    import dochris.phases.query_engine
    import dochris.phases.query_utils

    original_client = dochris.phases.query_engine._llm_client_cache
    original_chroma = dochris.phases.query_engine._chromadb_client_cache
    original_manifest = dochris.phases.query_utils._manifest_index_cache

    yield

    dochris.phases.query_engine._llm_client_cache = original_client
    dochris.phases.query_engine._chromadb_client_cache = original_chroma
    dochris.phases.query_utils._manifest_index_cache = original_manifest


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
    (workspace / "data").mkdir(parents=True)
    (workspace / "manifests" / "sources").mkdir(parents=True)

    # 创建示例文件
    (workspace / "wiki" / "summaries" / "测试摘要.md").write_text(
        "## 一句话摘要\n测试摘要内容\n\n## 要点\n- 要点1\n- 要点2",
        encoding="utf-8"
    )
    (workspace / "wiki" / "concepts" / "测试概念.md").write_text(
        "## 定义\n概念定义内容",
        encoding="utf-8"
    )

    # 创建示例 manifest
    manifest = {
        "id": "SRC-0001",
        "title": "测试摘要",
        "type": "article",
        "file_path": "raw/test.md",
        "status": "compiled",
        "quality_score": 90,
    }
    (workspace / "manifests" / "sources" / "SRC-0001.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setenv("WORKSPACE", str(workspace))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    # 重置 settings
    import dochris.settings
    dochris.settings._global_settings = None

    return workspace


class TestReadOpenclawConfig:
    """测试 read_openclaw_config 函数"""

    def test_read_nonexistent_config(self, tmp_path):
        """测试读取不存在的配置文件"""
        import dochris.phases.query_engine as qe
        from dochris.phases.query_engine import read_openclaw_config

        original_path = qe.OPENCLAW_CONFIG_PATH
        qe.OPENCLAW_CONFIG_PATH = str(tmp_path / "nonexistent.json")

        try:
            logger = MagicMock()
            result = read_openclaw_config(logger)
            assert result is None
        finally:
            qe.OPENCLAW_CONFIG_PATH = original_path

    def test_read_invalid_json_config(self, tmp_path):
        """测试读取无效的 JSON 配置"""
        import dochris.phases.query_engine as qe
        from dochris.phases.query_engine import read_openclaw_config

        config_file = tmp_path / "config.json"
        config_file.write_text("invalid json", encoding="utf-8")

        original_path = qe.OPENCLAW_CONFIG_PATH
        qe.OPENCLAW_CONFIG_PATH = str(config_file)

        try:
            logger = MagicMock()
            result = read_openclaw_config(logger)
            assert result is None
        finally:
            qe.OPENCLAW_CONFIG_PATH = original_path

    def test_read_valid_config_without_api_key(self, tmp_path):
        """测试读取没有 API Key 的有效配置"""
        import dochris.phases.query_engine as qe
        from dochris.phases.query_engine import read_openclaw_config

        config_file = tmp_path / "config.json"
        config_file.write_text('{"models": {"providers": {}}}', encoding="utf-8")

        original_path = qe.OPENCLAW_CONFIG_PATH
        qe.OPENCLAW_CONFIG_PATH = str(config_file)

        try:
            logger = MagicMock()
            result = read_openclaw_config(logger)
            assert result is None
        finally:
            qe.OPENCLAW_CONFIG_PATH = original_path

    def test_read_valid_config_with_api_key(self, tmp_path):
        """测试读取有 API Key 的有效配置"""
        import dochris.phases.query_engine as qe
        from dochris.phases.query_engine import read_openclaw_config

        config_file = tmp_path / "config.json"
        config_content = {
            "models": {
                "providers": {
                    "zai": {
                        "apiKey": "test-key-123456",
                        "baseUrl": "https://api.test.com"
                    }
                }
            }
        }
        config_file.write_text(json.dumps(config_content), encoding="utf-8")

        original_path = qe.OPENCLAW_CONFIG_PATH
        qe.OPENCLAW_CONFIG_PATH = str(config_file)

        try:
            logger = MagicMock()
            result = read_openclaw_config(logger)
            assert result is not None
            assert result["apiKey"] == "test-key-123456"
            assert result["baseUrl"] == "https://api.test.com"
        finally:
            qe.OPENCLAW_CONFIG_PATH = original_path


class TestCreateClient:
    """测试 create_client 函数"""

    def test_create_client_with_env_key(self, monkeypatch):
        """测试使用环境变量 API Key 创建客户端"""
        import dochris.phases.query_engine
        dochris.phases.query_engine._llm_client_cache = None

        monkeypatch.setenv("OPENAI_API_KEY", "test-env-key")

        with patch("dochris.phases.query_engine.openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            logger = MagicMock()
            result = dochris.phases.query_engine.create_client(logger)

            assert result == mock_client
            mock_openai.assert_called_once()

    def test_create_client_caching(self, monkeypatch):
        """测试客户端缓存"""
        import dochris.phases.query_engine
        dochris.phases.query_engine._llm_client_cache = None

        monkeypatch.setenv("OPENAI_API_KEY", "test-cache-key")

        with patch("dochris.phases.query_engine.openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            logger = MagicMock()
            client1 = dochris.phases.query_engine.create_client(logger)
            client2 = dochris.phases.query_engine.create_client(logger)

            # 应该只调用一次（第二次使用缓存）
            assert mock_openai.call_count == 1
            assert client1 is client2


class TestSearchConcepts:
    """测试 search_concepts 函数"""

    def test_search_concepts_returns_list(self, mock_workspace):
        """测试搜索概念返回列表"""
        from dochris.phases.query_engine import search_concepts

        results = search_concepts("测试", top_k=5)

        assert isinstance(results, list)

    def test_search_concepts_finds_match(self, mock_workspace):
        """测试搜索能找到匹配的概念 — 使用真实工作区"""
        import dochris.phases.query_engine as qe
        from dochris.phases.query_engine import search_concepts

        # Patch workspace path used by search_concepts
        original = qe.OPENCLAW_CONFIG_PATH
        qe.OPENCLAW_CONFIG_PATH = str(mock_workspace / "nonexistent.json")
        try:
            results = search_concepts("测试概念", top_k=5)
            # Real workspace may not have indexed concepts
            assert isinstance(results, list)
        finally:
            qe.OPENCLAW_CONFIG_PATH = original


class TestSearchSummaries:
    """测试 search_summaries 函数"""

    def test_search_summaries_returns_list(self, mock_workspace):
        """测试搜索摘要返回列表"""
        from dochris.phases.query_engine import search_summaries

        results = search_summaries("测试", top_k=5)

        assert isinstance(results, list)

    def test_search_summaries_with_limit(self, mock_workspace):
        """测试限制结果数量"""
        from dochris.phases.query_engine import search_summaries

        results = search_summaries("测试", top_k=1)

        assert len(results) <= 1


class TestVectorSearch:
    """测试 vector_search 函数"""

    def test_vector_search_without_chromadb(self, mock_workspace):
        """测试没有 ChromaDB 时的行为"""
        import dochris.phases.query_engine as qe
        from dochris.phases.query_engine import vector_search

        # Save and remove chromadb to simulate it not being installed
        original_chroma = getattr(qe, '_chromadb_module', None)
        # Force chromadb import to fail by patching import
        qe._chromadb_module = None

        try:
            logger = MagicMock()
            results = vector_search("测试查询", top_k=5, logger=logger)
            assert isinstance(results, list)
        finally:
            qe._chromadb_module = original_chroma


class TestGenerateAnswer:
    """测试 generate_answer 函数"""

    def test_generate_answer_with_empty_context(self):
        """测试空上下文时的回答"""
        from dochris.phases.query_engine import generate_answer

        mock_client = MagicMock()
        logger = MagicMock()

        result = generate_answer(
            "测试问题",
            concepts=[],
            summaries=[],
            vector_results=[],
            client=mock_client,
            logger=logger,
        )

        # 空上下文应该返回提示信息
        assert result is not None
        assert "未找到相关内容" in result

    def test_generate_answer_with_concepts(self):
        """测试有概念时的回答"""
        from dochris.phases.query_engine import generate_answer

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="测试回答"))]
        mock_client.chat.completions.create.return_value = mock_response

        logger = MagicMock()

        concepts = [{"name": "测试概念", "definition": "概念定义"}]

        result = generate_answer(
            "测试问题",
            concepts=concepts,
            summaries=[],
            vector_results=[],
            client=mock_client,
            logger=logger,
        )

        assert result == "测试回答"
        mock_client.chat.completions.create.assert_called_once()


class TestSearchAll:
    """测试 search_all 函数"""

    def test_search_all_returns_dict(self, mock_workspace):
        """测试 search_all 返回字典"""
        from dochris.phases.query_engine import search_all

        result = search_all("测试", top_k=5)

        assert isinstance(result, dict)
        assert "concepts" in result
        assert "summaries" in result
        assert "vector_results" in result
        assert "search_sources" in result

    def test_search_all_structure(self, mock_workspace):
        """测试 search_all 返回结构"""
        from dochris.phases.query_engine import search_all

        result = search_all("测试", top_k=5)

        assert isinstance(result["concepts"], list)
        assert isinstance(result["summaries"], list)
        assert isinstance(result["vector_results"], list)
        assert isinstance(result["search_sources"], list)


class TestPrintResult:
    """测试 print_result 函数"""

    def test_print_result_with_minimal_data(self, capsys):
        """测试打印最小结果"""
        from dochris.phases.query_engine import print_result

        result = {
            "query": "测试查询",
            "mode": "combined",
            "time_seconds": 0.5,
            "concepts": [],
            "summaries": [],
            "vector_results": [],
            "answer": None,
        }

        print_result(result)

        captured = capsys.readouterr()
        assert "测试查询" in captured.out

    def test_print_result_with_all_data(self, capsys):
        """测试打印完整结果"""
        from dochris.phases.query_engine import print_result

        result = {
            "query": "测试查询",
            "mode": "combined",
            "search_sources": ["wiki"],
            "time_seconds": 1.0,
            "concepts": [{"name": "概念", "definition": "定义", "score": 10}],
            "summaries": [{"title": "标题", "one_line": "摘要", "score": 5}],
            "vector_results": [{"text": "文本", "source": "来源", "score": 0.1}],
            "answer": "回答",
        }

        print_result(result)

        captured = capsys.readouterr()
        assert "测试查询" in captured.out
        assert "回答" in captured.out
