"""tests/test_query_engine.py

查询引擎模块测试
"""

import json
from unittest.mock import MagicMock, patch

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
    (workspace / "data").mkdir(parents=True)

    # 创建示例文件
    (workspace / "wiki" / "summaries" / "测试.md").write_text(
        "## 一句话摘要\n测试摘要\n\n## 要点\n- 要点1\n- 要点2",
        encoding="utf-8"
    )
    (workspace / "wiki" / "concepts" / "概念.md").write_text(
        "## 定义\n概念定义",
        encoding="utf-8"
    )

    monkeypatch.setenv("WORKSPACE", str(workspace))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    return workspace


class TestReadOpenclawConfig:
    """测试 read_openclaw_config 函数"""

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_read_nonexistent_config(self, mock_open_func):
        """测试读取不存在的配置文件"""
        from dochris.phases.query_engine import read_openclaw_config

        logger = MagicMock()
        result = read_openclaw_config(logger)

        assert result is None

    @patch('builtins.open', side_effect=json.JSONDecodeError("test", doc="", pos=0))
    def test_read_invalid_json_config(self, mock_open_func):
        """测试读取无效的 JSON 配置"""
        from dochris.phases.query_engine import read_openclaw_config

        logger = MagicMock()
        result = read_openclaw_config(logger)

        assert result is None

    @patch('builtins.open')
    def test_read_valid_config_without_api_key(self, mock_open_func):
        """测试读取没有 API Key 的有效配置"""
        from dochris.phases.query_engine import read_openclaw_config

        # 模拟读取返回没有 API Key 的配置
        mock_open_func.return_value.__enter__.return_value.read.return_value = (
            '{"models": {"providers": {}}}'
        )

        logger = MagicMock()
        result = read_openclaw_config(logger)

        assert result is None


class TestCreateClient:
    """测试 create_client 函数"""

    @patch('dochris.phases.query_engine.openai.OpenAI')
    def test_create_client_with_env_key(self, mock_openai, monkeypatch):
        """测试使用环境变量 API Key 创建客户端"""
        # 清除缓存
        import dochris.phases.query_engine
        from dochris.phases.query_engine import create_client
        dochris.phases.query_engine._llm_client_cache = None

        monkeypatch.setenv("OPENAI_API_KEY", "test-env-key")

        logger = MagicMock()
        client = create_client(logger)

        mock_openai.assert_called_once()
        assert client is not None

    @patch('dochris.phases.query_engine.openai.OpenAI')
    def test_create_client_caching(self, mock_openai, monkeypatch):
        """测试客户端缓存"""
        # 清除缓存
        import dochris.phases.query_engine
        from dochris.phases.query_engine import create_client
        dochris.phases.query_engine._llm_client_cache = None

        monkeypatch.setenv("OPENAI_API_KEY", "test-cache-key")

        logger = MagicMock()
        client1 = create_client(logger)
        client2 = create_client(logger)

        # 应该只调用一次（第二次使用缓存）
        assert mock_openai.call_count == 1
        assert client1 is client2


class TestSearchConcepts:
    """测试 search_concepts 函数"""

    def test_search_concepts_returns_list(self, mock_workspace):
        """测试搜索概念返回列表"""
        from dochris.phases.query_engine import search_concepts

        results = search_concepts("概念", top_k=5)

        assert isinstance(results, list)

    def test_search_concepts_empty_query(self, mock_workspace):
        """测试空查询"""
        from dochris.phases.query_engine import search_concepts

        results = search_concepts("", top_k=5)

        assert isinstance(results, list)


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
        from dochris.phases.query_engine import vector_search

        # ChromaDB 可能不可用
        logger = MagicMock()
        results = vector_search("测试查询", top_k=5, logger=logger)

        assert isinstance(results, list)

    def test_vector_search_returns_list(self, mock_workspace):
        """测试向量搜索返回列表"""
        from dochris.phases.query_engine import vector_search

        logger = MagicMock()
        results = vector_search("测试", top_k=5, logger=logger)

        assert isinstance(results, list)


class TestGenerateAnswer:
    """测试 generate_answer 函数"""

    @patch('dochris.phases.query_engine.openai.OpenAI')
    def test_generate_answer_with_empty_context(self, mock_openai):
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
        assert isinstance(result, str)

    @patch('dochris.phases.query_engine.openai.OpenAI')
    def test_generate_answer_with_concepts(self, mock_openai):
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
