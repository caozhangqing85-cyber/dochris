#!/usr/bin/env python3
"""
测试 query_engine.py 查询引擎
"""

import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestGetVectorStore(unittest.TestCase):
    """测试向量存储工厂函数"""

    def setUp(self):
        """清理缓存"""
        import dochris.phases.query_engine as qe
        qe._vector_store_cache = None

    def tearDown(self):
        """清理缓存"""
        import dochris.phases.query_engine as qe
        qe._vector_store_cache = None

    @patch('dochris.vector.get_store')
    @patch('dochris.phases.query_engine.get_settings')
    def test_get_vector_store_chromadb(self, mock_settings, mock_get_store):
        """测试获取 ChromaDB 向量存储"""
        from dochris.phases.query_engine import get_vector_store

        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_store_cls = Mock()
        mock_store_instance = Mock()
        mock_store_cls.return_value = mock_store_instance
        mock_get_store.return_value = mock_store_cls

        with patch('dochris.phases.query_engine.DATA_PATH', Path("/tmp/test")):
            result = get_vector_store()

        mock_store_cls.assert_called_once_with(persist_directory=str(Path("/tmp/test")))
        self.assertEqual(result, mock_store_instance)

    @patch('dochris.vector.get_store')
    @patch('dochris.phases.query_engine.get_settings')
    def test_get_vector_store_cache(self, mock_settings, mock_get_store):
        """测试向量存储缓存"""
        from dochris.phases.query_engine import get_vector_store

        mock_config = Mock()
        mock_config.vector_store = "faiss"
        mock_settings.return_value = mock_config

        mock_store_cls = Mock()
        mock_store_instance = Mock()
        mock_store_cls.return_value = mock_store_instance
        mock_get_store.return_value = mock_store_cls

        # 第一次调用
        result1 = get_vector_store()
        # 第二次调用应该使用缓存
        result2 = get_vector_store()

        mock_get_store.assert_called_once()
        self.assertEqual(result1, result2)


class TestSearchConcepts(unittest.TestCase):
    """测试概念搜索"""

    @patch('dochris.phases.query_engine._keyword_search')
    def test_search_concepts_wiki_has_results(self, mock_search):
        """测试 wiki 有结果时的概念搜索"""
        from dochris.phases.query_engine import search_concepts

        mock_results = [{"name": "test", "score": 10}]
        mock_search.return_value = mock_results

        result = search_concepts("test query", 5)

        mock_search.assert_called_once()
        self.assertEqual(result, mock_results)

    @patch('dochris.phases.query_engine._keyword_search')
    def test_search_concepts_fallback_to_outputs(self, mock_search):
        """测试 wiki 无结果时 fallback 到 outputs"""
        from dochris.phases.query_engine import search_concepts

        # 第一次调用返回空，第二次返回结果
        mock_search.side_effect = [[], [{"name": "test", "score": 10}]]

        result = search_concepts("test query", 5)

        self.assertEqual(mock_search.call_count, 2)
        self.assertEqual(len(result), 1)


class TestSearchSummaries(unittest.TestCase):
    """测试摘要搜索"""

    @patch('dochris.phases.query_engine._keyword_search')
    def test_search_summaries_wiki_has_results(self, mock_search):
        """测试 wiki 有结果时的摘要搜索"""
        from dochris.phases.query_engine import search_summaries

        mock_results = [{"title": "test", "score": 10}]
        mock_search.return_value = mock_results

        result = search_summaries("test query", 5)

        mock_search.assert_called_once()
        self.assertEqual(result, mock_results)


class TestSearchAll(unittest.TestCase):
    """测试搜索全部"""

    @patch('dochris.phases.query_engine.vector_search')
    @patch('dochris.phases.query_engine.search_summaries')
    @patch('dochris.phases.query_engine.search_concepts')
    def test_search_all_combined_results(self, mock_concepts, mock_summaries, mock_vector):
        """测试搜索全部合并结果"""
        from dochris.phases.query_engine import search_all

        mock_concepts.return_value = [{"name": "c1", "source": "wiki", "score": 10}]
        mock_summaries.return_value = [{"title": "s1", "source": "wiki", "score": 8}]
        mock_vector.return_value = [{"text": "v1", "score": 0.5}]

        result = search_all("test", 5)

        self.assertIn("concepts", result)
        self.assertIn("summaries", result)
        self.assertIn("vector_results", result)
        self.assertIn("search_sources", result)
        self.assertIn("wiki", result["search_sources"])
        self.assertIn("vector", result["search_sources"])

    @patch('dochris.phases.query_engine.vector_search')
    @patch('dochris.phases.query_engine.search_summaries')
    @patch('dochris.phases.query_engine.search_concepts')
    def test_search_all_empty_results(self, mock_concepts, mock_summaries, mock_vector):
        """测试搜索全部无结果"""
        from dochris.phases.query_engine import search_all

        mock_concepts.return_value = []
        mock_summaries.return_value = []
        mock_vector.return_value = []

        result = search_all("test", 5)

        self.assertEqual(result["concepts"], [])
        self.assertEqual(result["summaries"], [])
        self.assertEqual(result["vector_results"], [])


class TestVectorSearch(unittest.TestCase):
    """测试向量检索"""

    def setUp(self):
        """清理缓存"""
        import dochris.phases.query_engine as qe
        qe._chromadb_client_cache = None

    def tearDown(self):
        """清理缓存"""
        import dochris.phases.query_engine as qe
        qe._chromadb_client_cache = None

    def test_vector_search_non_chromadb(self):
        """测试非 ChromaDB 向量存储"""
        from dochris.phases import query_engine

        # patch settings 模块的 get_settings（因为函数内部导入了它）
        with patch('dochris.settings.get_settings') as mock_settings, \
             patch.object(query_engine, '_vector_search_with_store') as mock_store_search:
            mock_config = Mock()
            mock_config.vector_store = "faiss"
            mock_settings.return_value = mock_config

            mock_store_search.return_value = [{"text": "result"}]

            result = query_engine.vector_search("test", 5)

            mock_store_search.assert_called_once()
            self.assertEqual(len(result), 1)

    @patch('dochris.phases.query_engine.get_settings')
    def test_vector_search_chromadb_no_collections(self, mock_settings):
        """测试 ChromaDB 无集合时返回空"""
        from dochris.phases.query_engine import vector_search

        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        with patch('dochris.phases.query_engine.DATA_PATH', Path("/tmp/test")):
            mock_client = Mock()
            mock_client.list_collections.return_value = []

            with patch('chromadb.PersistentClient', return_value=mock_client):
                result = vector_search("test", 5)

        self.assertEqual(result, [])

    @patch('dochris.phases.query_engine.get_settings')
    def test_vector_search_chromadb_import_error(self, mock_settings):
        """测试 ChromaDB 未安装时返回空"""
        from dochris.phases.query_engine import vector_search

        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        with patch('dochris.phases.query_engine.DATA_PATH', Path("/tmp/test")):
            with patch('chromadb.PersistentClient', side_effect=ImportError):
                result = vector_search("test", 5, logger=None)

        self.assertEqual(result, [])


class TestVectorSearchWithStore(unittest.TestCase):
    """测试抽象层向量检索"""

    @patch('dochris.phases.query_engine.get_vector_store')
    def test_vector_search_with_store_no_collections(self, mock_get_store):
        """测试无集合时返回空"""
        from dochris.phases.query_engine import _vector_search_with_store

        mock_store = Mock()
        mock_store.list_collections.return_value = []
        mock_get_store.return_value = mock_store

        result = _vector_search_with_store("test", 5)

        self.assertEqual(result, [])

    @patch('dochris.phases.query_engine.get_vector_store')
    def test_vector_search_with_store_with_results(self, mock_get_store):
        """测试有结果时的向量检索"""
        from dochris.phases.query_engine import _vector_search_with_store

        mock_store = Mock()
        mock_store.list_collections.return_value = ["col1"]
        mock_store.query.return_value = [
            {
                "document": "test document",
                "metadata": {"source": "test.md"},
                "distance": 0.1,
            }
        ]
        mock_get_store.return_value = mock_store

        result = _vector_search_with_store("test", 5)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "test document")
        self.assertEqual(result[0]["source"], "test.md")
        self.assertEqual(result[0]["score"], 0.1)


class TestGenerateAnswer(unittest.TestCase):
    """测试 LLM 回答生成"""

    @patch('dochris.phases.query_engine.openai')
    def test_generate_answer_with_context(self, mock_openai):
        """测试有上下文时生成回答"""
        from dochris.phases.query_engine import generate_answer

        mock_client = Mock()
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Generated answer"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        concepts = [{"name": "概念1", "definition": "定义1"}]
        summaries = [{"title": "标题1", "one_line": "摘要", "key_points": ["要点1"]}]
        vector_results = [{"text": "向量内容", "source": "test.md"}]

        result = generate_answer("test query", concepts, summaries, vector_results, mock_client, Mock())

        self.assertIsNotNone(result)
        self.assertEqual(result, "Generated answer")

    @patch('dochris.phases.query_engine.openai')
    def test_generate_answer_no_context(self, mock_openai):
        """测试无上下文时返回提示"""
        from dochris.phases.query_engine import generate_answer

        mock_client = Mock()
        logger = Mock()

        result = generate_answer("test query", [], [], [], mock_client, logger)

        self.assertEqual(result, "未找到相关内容。请尝试其他关键词。")

    def test_generate_answer_api_error(self):
        """测试 API 错误时返回 None"""
        import openai

        from dochris.phases.query_engine import generate_answer

        mock_client = Mock()
        # 创建一个模拟的 APIError（需要 request 和 body 参数）
        mock_request = Mock()
        mock_body = Mock()
        api_error = openai.APIError("API Error", request=mock_request, body=mock_body)
        mock_client.chat.completions.create.side_effect = api_error
        logger = Mock()

        concepts = [{"name": "概念1", "definition": "定义1"}]
        result = generate_answer("test query", concepts, [], [], mock_client, logger)

        self.assertIsNone(result)
        logger.error.assert_called()


class TestReadOpenclawConfig(unittest.TestCase):
    """测试读取 OpenClaw 配置"""

    def test_read_openclaw_config_success(self):
        """测试成功读取配置"""
        from dochris.phases.query_engine import read_openclaw_config

        config_data = {
            "models": {
                "providers": {
                    "zai": {
                        "apiKey": "test-key",
                        "baseUrl": "https://api.test.com"
                    }
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with patch('dochris.phases.query_engine.OPENCLAW_CONFIG_PATH', Path(temp_path)):
                result = read_openclaw_config()

            self.assertIsNotNone(result)
            self.assertEqual(result["apiKey"], "test-key")
        finally:
            os.unlink(temp_path)

    def test_read_openclaw_config_file_not_found(self):
        """测试配置文件不存在"""
        from dochris.phases.query_engine import read_openclaw_config

        with patch('dochris.phases.query_engine.OPENCLAW_CONFIG_PATH', Path("/nonexistent/config.json")):
            result = read_openclaw_config()

        self.assertIsNone(result)

    def test_read_openclaw_config_invalid_json(self):
        """测试配置文件 JSON 格式错误"""
        from dochris.phases.query_engine import read_openclaw_config

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
            temp_path = f.name

        try:
            with patch('dochris.phases.query_engine.OPENCLAW_CONFIG_PATH', Path(temp_path)):
                result = read_openclaw_config()

            self.assertIsNone(result)
        finally:
            os.unlink(temp_path)


class TestCreateClient(unittest.TestCase):
    """测试创建 OpenAI 客户端"""

    def setUp(self):
        """清理缓存"""
        import dochris.phases.query_engine as qe
        qe._llm_client_cache = None
        # 确保 OPENAI_API_KEY 环境变量不存在
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']

    def tearDown(self):
        """清理环境"""
        import dochris.phases.query_engine as qe
        qe._llm_client_cache = None
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']

    @patch('dochris.phases.query_engine.openai')
    @patch('dochris.phases.query_engine.get_settings')
    def test_create_client_from_env(self, mock_settings, mock_openai):
        """测试从环境变量创建客户端"""
        from dochris.phases.query_engine import create_client

        os.environ['OPENAI_API_KEY'] = 'env-key'

        mock_config = Mock()
        mock_config.api_key = None
        mock_config.api_base = "https://api.test.com"
        mock_settings.return_value = mock_config

        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client

        result = create_client()

        self.assertEqual(result, mock_client)

    @patch('dochris.phases.query_engine.openai')
    @patch('dochris.phases.query_engine.get_settings')
    def test_create_client_from_settings(self, mock_settings, mock_openai):
        """测试从 settings 创建客户端"""
        from dochris.phases.query_engine import create_client

        mock_config = Mock()
        mock_config.api_key = 'settings-key'
        mock_config.api_base = "https://api.test.com"
        mock_settings.return_value = mock_config

        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client

        result = create_client()

        self.assertEqual(result, mock_client)

    def test_create_client_no_api_key(self):
        """测试无 API Key 时返回 None"""
        from dochris.phases.query_engine import create_client

        with patch('dochris.phases.query_engine.get_settings') as mock_settings:
            mock_config = Mock()
            mock_config.api_key = None
            mock_config.api_base = None
            mock_settings.return_value = mock_config

            with patch('dochris.phases.query_engine.read_openclaw_config', return_value=None):
                result = create_client()

        self.assertIsNone(result)


class TestPrintResult(unittest.TestCase):
    """测试打印查询结果"""

    def test_print_result_basic(self):
        """测试基本打印"""
        from dochris.phases.query_engine import print_result

        result = {
            "query": "test query",
            "mode": "combined",
            "time_seconds": 1.5,
            "concepts": [{"name": "概念1", "definition": "定义1", "score": 10, "source": "wiki"}],
            "summaries": [],
            "vector_results": [],
            "search_sources": ["wiki"],
            "answer": None,  # 添加 answer 键
        }

        output = StringIO()
        with patch('sys.stdout', output):
            print_result(result)

        output_str = output.getvalue()
        self.assertIn("test query", output_str)
        self.assertIn("概念1", output_str)

    def test_print_result_with_answer(self):
        """测试带答案的打印"""
        from dochris.phases.query_engine import print_result

        result = {
            "query": "test query",
            "mode": "all",
            "time_seconds": 2.0,
            "concepts": [],
            "summaries": [],
            "vector_results": [],
            "answer": "这是 AI 生成的回答",
            "search_sources": [],
        }

        output = StringIO()
        with patch('sys.stdout', output):
            print_result(result)

        output_str = output.getvalue()
        self.assertIn("AI 回答", output_str)
        self.assertIn("这是 AI 生成的回答", output_str)


if __name__ == "__main__":
    unittest.main()
