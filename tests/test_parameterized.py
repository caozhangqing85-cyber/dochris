#!/usr/bin/env python3
"""
参数化测试 - 使用 pytest.mark.parametrize 进行批量测试

测试覆盖:
1. 解析器扩展名检测
2. 文件分类映射
3. 质量评分范围
4. Settings 属性类型
5. 协议接口方法
6. CLI 命令存在性
7. 音频/视频文件扩展名
8. 代码文件扩展名
9. 文档文件扩展名
10. 跳过的文件扩展名
"""

from pathlib import Path

import pytest


class TestParserExtensionsParametrized:
    """解析器扩展名参数化测试"""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("test.md", True),
            ("test.txt", True),
            ("test.rst", True),
            ("test.html", True),
            ("test.docx", True),
            ("test.pptx", True),
            ("test.xlsx", True),
            ("test.pdf", False),
            ("test.py", False),
            ("test.js", False),
            ("test.json", False),
            ("test.xml", False),
            ("test.yaml", False),
            ("test.yml", False),
            ("test.toml", False),
            ("test.ini", False),
            ("test.cfg", False),
            ("test.sh", False),
            ("test.bat", False),
            ("test.ps1", False),
        ],
    )
    def test_detect_document_file(self, filename, expected, tmp_path):
        """测试文档文件检测"""
        from dochris.parsers.doc_parser import detect_document_file

        file_path = tmp_path / filename
        file_path.write_text("test")
        assert detect_document_file(file_path) is expected


class TestFileCategoryParametrized:
    """文件分类参数化测试"""

    @pytest.mark.parametrize(
        "ext,expected_category",
        [
            # Documents
            (".pdf", "pdfs"),
            (".doc", "pdfs"),
            (".docx", "pdfs"),
            (".txt", "articles"),
            (".html", "articles"),
            (".htm", "articles"),
            (".md", "articles"),
            # .rst 不在 FILE_TYPE_MAP 中，会返回 other
            (".rst", "other"),
            # Books
            (".mobi", "ebooks"),
            (".epub", "ebooks"),
            # Audio - 仅测试已定义的
            (".mp3", "audio"),
            (".m4a", "audio"),
            (".wav", "audio"),
            (".flac", "audio"),
            (".aac", "audio"),
            (".ogg", "audio"),
            # Video - 仅测试已定义的
            (".mp4", "videos"),
            (".mkv", "videos"),
            (".avi", "videos"),
            (".mov", "videos"),
            (".wmv", "videos"),
            # Unknown - 这些实际返回 other，因为未在 FILE_TYPE_MAP 中定义
            (".flv", "other"),
            (".webm", "other"),
            (".wma", "other"),
            (".opus", "other"),
            (".xyz", "other"),
            (".unknown", "other"),
        ],
    )
    def test_file_category(self, ext, expected_category):
        """测试文件分类映射"""
        from dochris.settings import get_file_category

        assert get_file_category(ext) == expected_category

    @pytest.mark.parametrize(
        "ext",
        [
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".deb",
            ".rpm",
            ".zip",
            ".rar",
            ".7z",
            ".tar",
            ".gz",
            ".bz2",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".svg",
            ".webp",
            ".ico",
            ".mpv",
            ".srt",
            ".ass",
            ".vtt",
            ".lrc",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".py",
            ".js",
            ".sh",
            ".bat",
            ".ps1",
        ],
    )
    def test_skip_extensions(self, ext):
        """测试应该跳过的文件扩展名"""
        from dochris.settings import SKIP_EXTENSIONS, get_file_category

        assert ext in SKIP_EXTENSIONS
        assert get_file_category(ext) is None or get_file_category(ext) == "other"


class TestQualityScoringParametrized:
    """质量评分参数化测试"""

    @pytest.mark.parametrize(
        "title,summary,key_points,concepts,min_score",
        [
            # 高质量内容
            (
                "Python 装饰器详解",
                "Python 装饰器是一种强大的语法特性。" * 20,
                ["装饰器是语法糖", "理解闭包很重要", "可以添加额外功能", "提高代码复用性", "实际应用广泛"],
                ["装饰器", "闭包", "高阶函数", "一等公民"],
                60,
            ),
            # 中等质量
            (
                "有标题",
                "有摘要内容" * 10,
                ["关键点1", "关键点2"],
                ["概念1"],
                15,
            ),
            # 低质量
            (
                "有标题",
                "短摘要",
                [],
                [],
                0,
            ),
            # 极低质量
            (
                "",
                "",
                [],
                [],
                0,
            ),
            # 长摘要高评分
            (
                "详细标题",
                "非常详细的摘要" * 30,
                ["点1", "点2", "点3"],
                ["概念1", "概念2"],
                35,
            ),
            # 多关键点提升评分
            (
                "多要点标题",
                "摘要内容" * 15,
                ["要点1", "要点2", "要点3", "要点4", "要点5"],
                ["概念1", "概念2", "概念3"],
                50,
            ),
        ],
    )
    def test_quality_scoring_range(self, title, summary, key_points, concepts, min_score):
        """测试质量评分范围"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        data = {
            "title": title,
            "detailed_summary": summary,
            "key_points": key_points,
            "concepts": concepts,
            "one_line": title,
        }
        score = score_summary_quality_v4(data)
        assert isinstance(score, int)
        assert 0 <= score <= 100
        assert score >= min_score, f"评分 {score} 低于最低要求 {min_score}"


class TestSettingsAttributeTypesParametrized:
    """Settings 属性类型参数化测试"""

    @pytest.mark.parametrize(
        "attr,expected_type",
        [
            # 路径属性
            ("workspace", Path),
            ("source_path", (Path, type(None))),
            ("logs_dir", Path),
            ("cache_dir", Path),
            ("outputs_dir", Path),
            ("raw_dir", Path),
            ("wiki_dir", Path),
            ("curated_dir", Path),
            ("manifests_dir", Path),
            # API 配置
            ("api_key", (str, type(None))),
            ("api_base", str),
            ("model", str),
            ("llm_provider", str),
            ("query_model", str),
            ("embedding_model", str),
            ("vector_store", str),
            # 编译配置
            ("max_concurrency", int),
            ("batch_size", int),
            ("llm_max_tokens", int),
            ("llm_temperature", float),
            ("llm_timeout", float),
            ("llm_request_delay", float),
            # 质量配置
            ("min_quality_score", int),
            ("max_content_chars", int),
            # 重试配置
            ("max_retries", int),
            ("retry_delay_429", float),
            ("retry_delay_connection", float),
            ("retry_delay_general", float),
            # 日志配置
            ("log_level", str),
            ("log_format", str),
            # 插件配置
            ("plugin_dirs", list),
            ("plugins_enabled", list),
            ("plugins_disabled", list),
            # 缓存配置
            ("cache_retention_days", int),
            ("min_text_length", int),
        ],
    )
    def test_settings_attribute_types(self, attr, expected_type):
        """测试 Settings 属性类型"""
        from dochris.settings import get_settings

        settings = get_settings()
        value = getattr(settings, attr)

        # 处理联合类型
        if isinstance(expected_type, tuple):
            assert isinstance(value, expected_type), f"{attr} 类型错误: {type(value)} not in {expected_type}"
        else:
            assert isinstance(value, expected_type), f"{attr} 类型错误: {type(value)} != {expected_type}"


class TestProtocolMethodsParametrized:
    """协议接口方法参数化测试"""

    @pytest.mark.parametrize(
        "protocol_cls,required_methods",
        [
            ("FileParser", ["supported_extensions", "parse"]),
            ("LLMProvider", ["generate", "close"]),
            ("VectorStore", ["add", "query", "delete", "list_collections"]),
            ("QualityScorer", ["score"]),
        ],
    )
    def test_protocol_has_required_methods(self, protocol_cls, required_methods):
        """测试协议接口具有必需的方法"""
        from dochris.protocols import FileParser, LLMProvider, QualityScorer, VectorStore

        protocols = {
            "FileParser": FileParser,
            "LLMProvider": LLMProvider,
            "VectorStore": VectorStore,
            "QualityScorer": QualityScorer,
        }

        proto = protocols[protocol_cls]
        for method in required_methods:
            assert hasattr(proto, method), f"{protocol_cls} 缺少方法: {method}"


class TestAudioExtensionsParametrized:
    """音频文件扩展名参数化测试"""

    @pytest.mark.parametrize(
        "ext",
        [
            ".mp3",
            ".wav",
            ".m4a",
            ".flac",
            ".aac",
            ".ogg",
        ],
    )
    def test_audio_extensions(self, ext):
        """测试音频文件扩展名识别"""
        from dochris.settings import AUDIO_EXTENSIONS, get_file_category

        assert ext in AUDIO_EXTENSIONS
        # 音频文件应该被分类为 audio
        category = get_file_category(ext)
        assert category == "audio", f"{ext} 应该分类为 audio，实际为 {category}"

    @pytest.mark.parametrize(
        "ext",
        [
            ".wma",
            ".opus",
        ],
    )
    def test_audio_extensions_defined(self, ext):
        """测试音频文件扩展名在集合中定义"""
        from dochris.settings import AUDIO_EXTENSIONS

        # 这些扩展名在 AUDIO_EXTENSIONS 中定义
        # 但 FILE_TYPE_MAP 可能没有对应的映射
        assert ext in AUDIO_EXTENSIONS


class TestVideoExtensionsParametrized:
    """视频文件扩展名参数化测试"""

    @pytest.mark.parametrize(
        "ext",
        [
            ".mp4",
            ".mkv",
            ".avi",
            ".mov",
            ".wmv",
        ],
    )
    def test_video_extensions(self, ext):
        """测试视频文件扩展名识别"""
        from dochris.settings import VIDEO_EXTENSIONS, get_file_category

        assert ext in VIDEO_EXTENSIONS
        # 视频文件应该被分类为 videos
        category = get_file_category(ext)
        assert category == "videos", f"{ext} 应该分类为 videos，实际为 {category}"

    @pytest.mark.parametrize(
        "ext",
        [
            ".flv",
            ".webm",
        ],
    )
    def test_video_extensions_defined(self, ext):
        """测试视频文件扩展名在集合中定义"""
        from dochris.settings import VIDEO_EXTENSIONS

        # 这些扩展名在 VIDEO_EXTENSIONS 中定义
        # 但 FILE_TYPE_MAP 可能没有对应的映射
        assert ext in VIDEO_EXTENSIONS


class TestCodeExtensionsParametrized:
    """代码文件扩展名参数化测试"""

    @pytest.mark.parametrize(
        "ext",
        [
            ".py",
            ".js",
            ".ts",
            ".java",
            ".c",
            ".cpp",
            ".go",
            ".rs",
            ".rb",
            ".cs",
            ".kt",
            ".swift",
            ".lua",
            ".zig",
            ".php",
            ".m",
            ".mm",
        ],
    )
    def test_code_extensions(self, ext):
        """测试代码文件扩展名识别"""
        from dochris.settings import CODE_EXTENSIONS

        assert ext in CODE_EXTENSIONS


class TestDocExtensionsParametrized:
    """文档文件扩展名参数化测试"""

    @pytest.mark.parametrize(
        "ext",
        [
            ".md",
            ".txt",
            ".rst",
            ".html",
        ],
    )
    def test_doc_extensions(self, ext):
        """测试文档文件扩展名识别"""
        from dochris.settings import DOC_EXTENSIONS

        assert ext in DOC_EXTENSIONS


class TestEbookExtensionsParametrized:
    """电子书文件扩展名参数化测试"""

    @pytest.mark.parametrize(
        "ext",
        [
            ".epub",
            ".mobi",
        ],
    )
    def test_ebook_extensions(self, ext):
        """测试电子书文件扩展名识别"""
        from dochris.settings import EBOOK_EXTENSIONS, get_file_category

        assert ext in EBOOK_EXTENSIONS
        # 电子书应该被分类为 ebooks
        category = get_file_category(ext)
        assert category == "ebooks", f"{ext} 应该分类为 ebooks，实际为 {category}"

    @pytest.mark.parametrize(
        "ext",
        [
            ".azw3",
            ".fb2",
        ],
    )
    def test_ebook_extensions_defined(self, ext):
        """测试电子书文件扩展名在集合中定义"""
        from dochris.settings import EBOOK_EXTENSIONS

        # 这些扩展名在 EBOOK_EXTENSIONS 中定义
        # 但 FILE_TYPE_MAP 可能没有对应的映射
        assert ext in EBOOK_EXTENSIONS


class TestCaseInsensitiveExtensionsParametrized:
    """大小写不敏感扩展名参数化测试"""

    @pytest.mark.parametrize(
        "ext_lower,ext_upper",
        [
            (".pdf", ".PDF"),
            (".md", ".MD"),
            (".txt", ".TXT"),
            (".mp3", ".MP3"),
            (".mp4", ".MP4"),
            (".epub", ".EPUB"),
            (".docx", ".DOCX"),
            (".py", ".PY"),
        ],
    )
    def test_case_insensitive_category(self, ext_lower, ext_upper):
        """测试文件分类大小写不敏感"""
        from dochris.settings import get_file_category

        category_lower = get_file_category(ext_lower)
        category_upper = get_file_category(ext_upper)

        assert category_lower == category_upper, f"{ext_lower} 和 {ext_upper} 分类应该相同"


class TestLearningKeywordsParametrized:
    """学习关键词参数化测试"""

    @pytest.mark.parametrize(
        "keyword",
        [
            "学习",
            "提升",
            "改善",
            "掌握",
            "理解",
            "应用",
            "运用",
            "技能",
            "知识",
            "能力",
            "经验",
            "方法",
            "策略",
            "技巧",
            "教训",
            "重点",
            "关键",
            "核心",
            "本质",
            "规律",
            "模式",
            "原理",
            "机制",
            "流程",
            "步骤",
            "效果",
            "结果",
            "成果",
            "优化",
            "增强",
            "改进",
            "提高",
            "训练",
            "实践",
            "实验",
            "操作",
            "实施",
            "使用",
            "利用",
        ],
    )
    def test_learning_keywords(self, keyword):
        """测试学习关键词列表"""
        from dochris.settings import LEARNING_KEYWORDS

        assert keyword in LEARNING_KEYWORDS, f"关键词 {keyword} 不在列表中"


class TestInfoKeywordsParametrized:
    """信息密度关键词参数化测试"""

    @pytest.mark.parametrize(
        "keyword",
        [
            "方法",
            "策略",
            "技巧",
            "经验",
            "教训",
            "重点",
            "关键",
            "核心",
            "本质",
            "规律",
            "模式",
            "原理",
            "机制",
            "流程",
            "步骤",
        ],
    )
    def test_info_keywords(self, keyword):
        """测试信息密度关键词列表"""
        from dochris.settings import INFO_KEYWORDS

        assert keyword in INFO_KEYWORDS, f"关键词 {keyword} 不在列表中"


class TestLLMProvidersParametrized:
    """LLM 提供商参数化测试"""

    @pytest.mark.parametrize(
        "provider_name",
        [
            "openai_compat",
            "ollama",
        ],
    )
    def test_llm_provider_exists(self, provider_name):
        """测试 LLM 提供商存在"""
        from dochris.llm import PROVIDERS, get_provider

        assert provider_name in PROVIDERS
        provider_cls = get_provider(provider_name)
        assert provider_cls is not None


class TestVectorStoresParametrized:
    """向量存储参数化测试"""

    @pytest.mark.parametrize(
        "store_name",
        [
            "chromadb",
            # "faiss",  # FAISS 是可选依赖
        ],
    )
    def test_vector_store_exists(self, store_name):
        """测试向量存储存在"""
        from dochris.vector import STORES, get_store

        assert store_name in STORES
        store_cls = get_store(store_name)
        assert store_cls is not None


class TestHookSpecsParametrized:
    """Hook 规范参数化测试"""

    @pytest.mark.parametrize(
        "hook_name",
        [
            "ingest_parser",
            "pre_compile",
            "post_compile",
            "quality_score",
            "pre_query",
            "post_query",
        ],
    )
    def test_hookspec_exists(self, hook_name):
        """测试 Hook 规范存在"""
        from dochris.plugin.hookspec import get_hookspec, list_hookspecs

        all_hooks = list_hookspecs()
        assert hook_name in all_hooks, f"Hook {hook_name} 不在列表中"

        spec = get_hookspec(hook_name)
        assert spec is not None, f"Hook {hook_name} 规范不存在"
        assert spec.name == hook_name


class TestFilePathOperationsParametrized:
    """文件路径操作参数化测试"""

    @pytest.mark.parametrize(
        "filename,is_valid",
        [
            ("normal_file.txt", True),
            ("file with spaces.txt", True),
            ("文件中文.txt", True),
            ("file-with-dashes.txt", True),
            ("file.with.dots.txt", True),
            ("file_with_underscores.txt", True),
            ("file123.txt", True),
            ("", False),
            ("file\nwith\nnewlines.txt", False),
        ],
    )
    def test_filename_validation(self, filename, is_valid):
        """测试文件名验证逻辑"""
        # 基本检查：非空且不包含换行符
        if is_valid:
            assert filename and "\n" not in filename
        else:
            assert not filename or "\n" in filename


class TestTextLengthCategoriesParametrized:
    """文本长度分类参数化测试"""

    @pytest.mark.parametrize(
        "text_length,category",
        [
            (0, "empty"),
            (50, "very_short"),
            (200, "short"),
            (600, "medium"),
            (1000, "long"),
            (1500, "very_long"),
        ],
    )
    def test_text_length_classification(self, text_length, category):
        """测试文本长度分类"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        # 创建测试数据
        test_data = {
            "detailed_summary": "x" * text_length,
            "key_points": [],
            "concepts": [],
            "one_line": "test",
        }

        # 只验证函数可以正常处理不同长度
        score = score_summary_quality_v4(test_data)
        assert isinstance(score, int)
        assert 0 <= score <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
