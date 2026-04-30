#!/usr/bin/env python3
"""
集成测试 v2 - 测试核心流程的端到端功能（扩展版）

测试覆盖:
1. 文件解析 (doc_parser)
2. 质量评分 (quality_scorer)
3. 配置加载 (settings)
4. 模块导入
5. 插件系统 (plugin)
6. LLM 提供商 (llm)
7. 向量存储 (vector)
8. 协议接口 (protocols)
"""

import pytest


class TestDocParserIntegration:
    """文档解析器集成测试"""

    def test_parse_markdown_file(self, tmp_path):
        """测试解析 Markdown 文件"""
        from dochris.parsers.doc_parser import parse_document

        # 创建测试文件
        md_file = tmp_path / "test.md"
        md_file.write_text("# 测试标题\n\n这是测试内容。", encoding="utf-8")

        # 解析
        result = parse_document(md_file)

        assert result is not None
        assert "测试标题" in result
        assert "测试内容" in result

    def test_parse_txt_file(self, tmp_path):
        """测试解析纯文本文件"""
        from dochris.parsers.doc_parser import parse_document

        # 创建测试文件
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("纯文本内容\n第二行", encoding="utf-8")

        # 解析
        result = parse_document(txt_file)

        assert result is not None
        assert "纯文本内容" in result

    def test_parse_html_file(self, tmp_path):
        """测试解析 HTML 文件"""
        from dochris.parsers.doc_parser import parse_document

        # 创建测试文件
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body><h1>标题</h1><p>段落</p></body></html>", encoding="utf-8")

        # 解析
        result = parse_document(html_file)

        assert result is not None
        assert "标题" in result

    def test_parse_empty_file(self, tmp_path):
        """测试解析空文件"""
        from dochris.parsers.doc_parser import parse_document

        # 创建空文件
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding="utf-8")

        # 解析
        result = parse_document(empty_file)

        # 空文件返回空字符串或 None 都是可接受的
        assert result is None or result == ""

    def test_parse_nonexistent_file(self, tmp_path):
        """测试解析不存在的文件"""
        from dochris.parsers.doc_parser import parse_document

        # 不存在的文件
        nonexistent = tmp_path / "nonexistent.txt"

        # 解析应该返回 None 或优雅处理错误
        result = parse_document(nonexistent)
        assert result is None

    def test_detect_document_file(self, tmp_path):
        """测试文档文件检测"""
        from dochris.parsers.doc_parser import detect_document_file

        # 检测支持的文档类型
        assert detect_document_file(tmp_path / "test.md") is True
        assert detect_document_file(tmp_path / "test.txt") is True
        assert detect_document_file(tmp_path / "test.docx") is True
        assert detect_document_file(tmp_path / "test.pdf") is False
        assert detect_document_file(tmp_path / "test.py") is False


class TestQualityScorerIntegration:
    """质量评分器集成测试"""

    def test_score_good_content(self):
        """测试高质量内容评分"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        good_content = {
            "detailed_summary": (
                "Python 是一种高级编程语言，具有简洁明了的语法。"
                "学习 Python 可以帮助你快速开发应用程序，提高编程效率。"
                "掌握 Python 的核心概念包括变量、函数、类和模块等。"
                "通过实践项目，你可以深入理解面向对象编程和函数式编程的思想。"
                "Python 的应用领域非常广泛，包括数据分析、机器学习、Web 开发等。"
                "持续学习和实践是成为优秀 Python 开发者的关键。"
                * 5  # 增加长度
            ),
            "key_points": [
                "Python 语法简洁，易于学习",
                "面向对象和函数式编程支持",
                "广泛应用于数据科学和 Web 开发",
                "丰富的第三方库生态系统",
                "持续实践是提升的关键",
            ],
            "concepts": ["Python", "面向对象", "函数式编程", "数据分析", "机器学习"],
            "one_line": "Python 编程语言学习指南",
        }

        score = score_summary_quality_v4(good_content)
        assert score > 70, f"高质量内容评分过低: {score}"

    def test_score_empty_content(self):
        """测试空内容评分"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        empty_content = {
            "detailed_summary": "",
            "key_points": [],
            "concepts": [],
            "one_line": "",
        }

        score = score_summary_quality_v4(empty_content)
        assert score < 30, f"空内容评分过高: {score}"

    def test_score_with_key_points(self):
        """测试带关键点的内容评分更高"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        # 基础内容
        base_content = {
            "detailed_summary": "这是基础内容。" * 50,
            "key_points": [],
            "concepts": [],
            "one_line": "基础标题",
        }

        base_score = score_summary_quality_v4(base_content)

        # 添加关键点
        content_with_points = {
            "detailed_summary": "这是基础内容。" * 50,
            "key_points": ["要点1", "要点2", "要点3", "要点4", "要点5"],
            "concepts": [],
            "one_line": "带要点的标题",
        }

        score_with_points = score_summary_quality_v4(content_with_points)
        assert score_with_points > base_score, "添加关键点应该提高评分"

    def test_score_none_input(self):
        """测试 None 输入处理"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        score = score_summary_quality_v4(None)
        assert score == 0

    def test_score_learning_keywords_boost(self):
        """测试学习关键词提升评分"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        learning_content = {
            "detailed_summary": (
                "学习是提升技能的关键方法。通过实践，你可以掌握新知识。"
                "理解核心概念有助于应用技术。"
                * 20
            ),
            "key_points": ["学习要点", "理解方法"],
            "concepts": ["学习", "实践"],
            "one_line": "学习方法指南",
        }

        score = score_summary_quality_v4(learning_content)
        # 学习关键词应该提高评分
        assert score > 40, f"学习内容评分过低: {score}"


class TestSettingsIntegration:
    """配置系统集成测试"""

    def test_settings_defaults(self):
        """测试默认设置"""
        from dochris.settings import Settings

        settings = Settings()
        assert settings.workspace is not None
        assert settings.model == "glm-5.1"
        assert settings.vector_store == "chromadb"
        assert settings.max_concurrency > 0

    def test_settings_workspace(self):
        """测试工作区路径配置"""
        from dochris.settings import get_settings

        settings = get_settings()
        workspace = settings.workspace
        assert workspace.exists() or workspace.is_absolute()

    def test_settings_file_category_complete(self):
        """测试文件分类映射完整性"""
        from dochris.settings import FILE_TYPE_MAP

        # 检查常见文件类型
        assert ".pdf" in FILE_TYPE_MAP
        assert ".txt" in FILE_TYPE_MAP
        assert ".md" in FILE_TYPE_MAP
        assert ".mp3" in FILE_TYPE_MAP
        assert ".mp4" in FILE_TYPE_MAP
        assert ".epub" in FILE_TYPE_MAP

    def test_settings_skip_extensions(self):
        """测试跳过的文件扩展名"""
        from dochris.settings import SKIP_EXTENSIONS

        # 检查常见可执行文件类型被跳过
        assert ".exe" in SKIP_EXTENSIONS
        assert ".so" in SKIP_EXTENSIONS
        assert ".dll" in SKIP_EXTENSIONS

    def test_settings_learning_keywords(self):
        """测试学习关键词配置"""
        from dochris.settings import LEARNING_KEYWORDS

        # 检查学习关键词列表不为空
        assert len(LEARNING_KEYWORDS) > 0
        assert "学习" in LEARNING_KEYWORDS
        assert "掌握" in LEARNING_KEYWORDS


class TestModuleImportsIntegration:
    """模块导入集成测试"""

    def test_import_dochris(self):
        """测试导入 dochris 主模块"""
        import dochris

        assert dochris is not None

    def test_import_plugin(self):
        """测试导入插件模块"""
        from dochris.plugin import PluginManager, hookimpl

        assert PluginManager is not None
        assert hookimpl is not None

    def test_import_llm(self):
        """测试导入 LLM 模块"""
        from dochris.llm import PROVIDERS, get_provider

        assert PROVIDERS is not None
        assert "openai_compat" in PROVIDERS
        assert get_provider is not None

    def test_import_vector(self):
        """测试导入向量存储模块"""
        from dochris.vector import STORES, get_store

        assert STORES is not None
        assert "chromadb" in STORES
        assert get_store is not None

    def test_import_protocols(self):
        """测试导入协议接口"""
        from dochris.protocols import FileParser, LLMProvider, QualityScorer, VectorStore

        assert FileParser is not None
        assert LLMProvider is not None
        assert VectorStore is not None
        assert QualityScorer is not None

    def test_import_settings(self):
        """测试导入配置模块"""
        from dochris.settings import get_file_category, get_settings

        assert get_settings is not None
        assert get_file_category is not None

    def test_import_parsers(self):
        """测试导入解析器模块"""
        from dochris.parsers.doc_parser import detect_document_file, parse_document

        assert detect_document_file is not None
        assert parse_document is not None

    def test_import_phases(self):
        """测试导入阶段模块"""
        from dochris.phases.phase1_ingestion import scan_source_dir
        from dochris.phases.phase2_compilation import compile_all

        assert scan_source_dir is not None
        assert compile_all is not None


class TestPluginSystemIntegration:
    """插件系统集成测试"""

    def test_plugin_manager_creation(self):
        """测试插件管理器创建"""
        from dochris.plugin import PluginManager

        pm = PluginManager()
        assert pm is not None

    def test_plugin_hook_registration(self):
        """测试插件 Hook 注册"""
        from dochris.plugin import PluginManager, hookimpl

        pm = PluginManager()

        @hookimpl
        def test_hook(arg: str) -> str:
            return f"processed: {arg}"

        pm.register("test_plugin", "test_hook", test_hook)
        assert pm.list_plugins() is not None

    def test_plugin_hook_call(self):
        """测试插件 Hook 调用"""
        from dochris.plugin import PluginManager, hookimpl

        pm = PluginManager()

        @hookimpl
        def pre_query(query: str) -> str:
            return query.strip().lower()

        pm.register("test", "pre_query", pre_query)
        # call_hook 返回列表
        result = pm.call_hook("pre_query", "  TEST QUERY  ")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == "test query"

    def test_plugin_list_hooks(self):
        """测试列出所有 Hooks"""
        from dochris.plugin.hookspec import list_hookspecs

        hooks = list_hookspecs()
        assert isinstance(hooks, list)
        assert len(hooks) >= 6  # 至少有 6 个基本 hooks


class TestLLMProvidersIntegration:
    """LLM 提供商集成测试"""

    def test_llm_providers_registry(self):
        """测试 LLM 提供商注册表"""
        from dochris.llm import PROVIDERS

        assert "openai_compat" in PROVIDERS
        assert "ollama" in PROVIDERS

    def test_llm_get_provider(self):
        """测试获取提供商"""
        from dochris.llm import get_provider

        provider_cls = get_provider("openai_compat")
        assert provider_cls is not None
        assert provider_cls.__name__ == "OpenAICompatProvider"

    def test_llm_invalid_provider(self):
        """测试无效提供商"""
        from dochris.llm import get_provider

        with pytest.raises(ValueError):
            get_provider("invalid_provider")


class TestVectorStoresIntegration:
    """向量存储集成测试"""

    def test_vector_stores_registry(self):
        """测试向量存储注册表"""
        from dochris.vector import STORES

        assert "chromadb" in STORES

    def test_vector_get_store(self):
        """测试获取存储"""
        from dochris.vector import get_store

        store_cls = get_store("chromadb")
        assert store_cls is not None
        assert store_cls.__name__ == "ChromaDBStore"

    def test_vector_invalid_store(self):
        """测试无效存储"""
        from dochris.vector import get_store

        with pytest.raises(ValueError):
            get_store("invalid_store")


class TestProtocolsIntegration:
    """协议接口集成测试"""

    def test_protocol_fileparser(self):
        """测试 FileParser 协议"""
        from typing import runtime_checkable

        from dochris.protocols import FileParser

        assert runtime_checkable(FileParser)

    def test_protocol_llmprovider(self):
        """测试 LLMProvider 协议"""
        from typing import runtime_checkable

        from dochris.protocols import LLMProvider

        assert runtime_checkable(LLMProvider)

    def test_protocol_vectorstore(self):
        """测试 VectorStore 协议"""
        from typing import runtime_checkable

        from dochris.protocols import VectorStore

        assert runtime_checkable(VectorStore)

    def test_protocol_qualityscorer(self):
        """测试 QualityScorer 协议"""
        from typing import runtime_checkable

        from dochris.protocols import QualityScorer

        assert runtime_checkable(QualityScorer)


class TestTextChunkerIntegration:
    """文本分块器集成测试"""

    def test_text_chunker_exists(self):
        """测试文本分块器模块存在"""
        from dochris.core.text_chunker import fixed_size_chunk, semantic_chunk

        assert fixed_size_chunk is not None
        assert semantic_chunk is not None

    def test_text_chunker_basic(self):
        """测试基础文本分块"""
        from dochris.core.text_chunker import fixed_size_chunk

        long_text = "这是第一段。\n\n" * 10
        chunks = fixed_size_chunk(long_text, chunk_size=100)
        assert len(chunks) > 0

    def test_text_chunker_empty(self):
        """测试空文本分块"""
        from dochris.core.text_chunker import fixed_size_chunk

        chunks = fixed_size_chunk("", chunk_size=100)
        assert chunks == []


class TestCacheIntegration:
    """缓存集成测试"""

    def test_cache_module_exists(self):
        """测试缓存模块存在"""
        from dochris.core.cache import clear_cache, load_cached, save_cached

        assert clear_cache is not None
        assert load_cached is not None
        assert save_cached is not None

    def test_cache_basic_operations(self, tmp_path):
        """测试缓存基本操作"""
        from dochris.core.cache import file_hash, load_cached, save_cached

        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # 计算文件哈希
        h = file_hash(test_file)
        assert h is not None

        # 保存缓存
        cache_data = {"result": "test_value"}
        save_cached(tmp_path, h, cache_data)

        # 加载缓存
        result = load_cached(tmp_path, h)
        assert result is not None
        assert result["result"] == "test_value"

    def test_cache_miss(self, tmp_path):
        """测试缓存未命中"""
        from dochris.core.cache import load_cached

        result = load_cached(tmp_path, "nonexistent_hash")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
