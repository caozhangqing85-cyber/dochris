"""
配置模块单元测试
"""

from pathlib import Path

import pytest

from dochris.settings import (
    BATCH_SIZE,
    CACHE_RETENTION_DAYS,
    DEFAULT_API_BASE,
    DEFAULT_CONCURRENCY,
    FILE_TYPE_MAP,
    INFO_KEYWORDS,
    LEARNING_KEYWORDS,
    MAX_CONTENT_CHARS,
    MAX_FILE_SIZE,
    MIN_QUALITY_SCORE,
    MIN_TEXT_LENGTH,
    OPENROUTER_API_BASE,
    OPENROUTER_MODEL,
    QUERY_MODEL,
    SKIP_EXTENSIONS,
    SOURCE_PATH,
    TEMPLATE_DEDUCTION,
    TEMPLATE_PATTERNS,
    get_cache_dir,
    get_data_dir,
    get_default_workspace,
    get_file_category,
    get_logs_dir,
    get_manifests_dir,
    get_outputs_dir,
    get_progress_file,
    get_raw_dir,
    get_wiki_concepts_dir,
    get_wiki_dir,
    get_wiki_summaries_dir,
)


class TestPathFunctions:
    """测试路径相关函数"""

    def test_get_default_workspace(self):
        """测试获取默认工作区路径"""
        path = get_default_workspace()
        assert "knowledge-base" in str(path)
        assert path.is_absolute()

    def test_get_logs_dir(self):
        """测试获取日志目录路径"""
        path = get_logs_dir()
        assert "logs" in str(path)

    def test_get_cache_dir(self):
        """测试获取缓存目录路径"""
        path = get_cache_dir()
        assert "cache" in str(path)

    def test_get_outputs_dir(self):
        """测试获取输出目录路径"""
        path = get_outputs_dir()
        assert "outputs" in str(path)

    def test_get_raw_dir(self):
        """测试获取 raw 目录路径"""
        path = get_raw_dir()
        assert "raw" in str(path)

    def test_get_wiki_dir(self):
        """测试获取 wiki 目录路径"""
        path = get_wiki_dir()
        assert "wiki" in str(path)

    def test_get_wiki_summaries_dir(self):
        """测试获取 wiki 摘要目录路径"""
        path = get_wiki_summaries_dir()
        assert "wiki" in str(path)
        assert "summaries" in str(path)

    def test_get_wiki_concepts_dir(self):
        """测试获取 wiki 概念目录路径"""
        path = get_wiki_concepts_dir()
        assert "wiki" in str(path)
        assert "concepts" in str(path)

    def test_get_manifests_dir(self):
        """测试获取 manifests 目录路径"""
        path = get_manifests_dir()
        assert "manifests" in str(path)
        assert "sources" in str(path)

    def test_get_data_dir(self):
        """测试获取数据目录路径"""
        path = get_data_dir()
        assert "data" in str(path)

    def test_get_progress_file(self):
        """测试获取进度文件路径"""
        path = get_progress_file()
        assert "progress.json" in str(path)


class TestAPIConfig:
    """测试 API 配置常量"""

    def test_default_api_base(self):
        """测试默认 API base URL（通用端点或 Coding 端点）"""
        assert DEFAULT_API_BASE in (
            "https://open.bigmodel.cn/api/paas/v4",
            "https://open.bigmodel.cn/api/coding/paas/v4",
        )

    def test_openrouter_api_base(self):
        """测试 OpenRouter API base URL"""
        assert OPENROUTER_API_BASE == "https://openrouter.ai/api/v1"

    def test_openrouter_model(self):
        """测试 OpenRouter 模型名"""
        assert "qwen" in OPENROUTER_MODEL.lower()

    def test_query_model(self):
        """测试查询模型名"""
        assert QUERY_MODEL == "glm-4-flash"


class TestCompilationConfig:
    """测试编译配置常量"""

    def test_default_concurrency(self):
        """测试默认并发数"""
        assert DEFAULT_CONCURRENCY == 3

    def test_batch_size(self):
        """测试批次大小"""
        assert BATCH_SIZE == 10

    def test_min_quality_score(self):
        """测试最低质量分数"""
        assert MIN_QUALITY_SCORE == 85

    def test_max_content_chars(self):
        """测试最大内容字符数"""
        assert MAX_CONTENT_CHARS == 20000

    def test_cache_retention_days(self):
        """测试缓存保留天数"""
        assert CACHE_RETENTION_DAYS == 30

    def test_template_deduction(self):
        """测试模板扣分"""
        assert TEMPLATE_DEDUCTION == 20

    def test_min_text_length(self):
        """测试最小文本长度"""
        assert MIN_TEXT_LENGTH == 100

    def test_max_file_size(self):
        """测试最大文件大小"""
        assert MAX_FILE_SIZE == 500 * 1024 * 1024


class TestQualityPatterns:
    """测试质量评分模式"""

    def test_template_patterns_is_list(self):
        """测试模板模式是列表"""
        assert isinstance(TEMPLATE_PATTERNS, list)

    def test_template_patterns_not_empty(self):
        """测试模板模式不为空"""
        assert len(TEMPLATE_PATTERNS) > 0

    def test_learning_keywords_is_list(self):
        """测试学习关键词是列表"""
        assert isinstance(LEARNING_KEYWORDS, list)

    def test_learning_keywords_not_empty(self):
        """测试学习关键词不为空"""
        assert len(LEARNING_KEYWORDS) > 0
        assert "学习" in LEARNING_KEYWORDS

    def test_info_keywords_is_list(self):
        """测试信息关键词是列表"""
        assert isinstance(INFO_KEYWORDS, list)

    def test_info_keywords_not_empty(self):
        """测试信息关键词不为空"""
        assert len(INFO_KEYWORDS) > 0


class TestFileTypeConfig:
    """测试文件类型配置"""

    def test_file_type_map_is_dict(self):
        """测试文件类型映射是字典"""
        assert isinstance(FILE_TYPE_MAP, dict)

    def test_file_type_map_contains_pdf(self):
        """测试文件类型映射包含 PDF"""
        assert ".pdf" in FILE_TYPE_MAP
        assert FILE_TYPE_MAP[".pdf"] == "pdfs"

    def test_file_type_map_contains_audio(self):
        """测试文件类型映射包含音频"""
        assert ".mp3" in FILE_TYPE_MAP
        assert FILE_TYPE_MAP[".mp3"] == "audio"

    def test_skip_extensions_is_set(self):
        """测试跳过扩展名是集合"""
        assert isinstance(SKIP_EXTENSIONS, set)

    def test_skip_extensions_contains_exe(self):
        """测试跳过扩展名包含 exe"""
        assert ".exe" in SKIP_EXTENSIONS


class TestValidateApiKey:
    """测试 API 密钥验证"""

    def test_validate_api_key_missing(self, monkeypatch):
        """测试 API 密钥缺失时抛出异常"""
        from dochris.settings import get_settings, reset_settings

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("BIGMODEL_API_KEY", raising=False)
        reset_settings()  # 重置以清除缓存的 API key
        with pytest.raises(ValueError, match="OPENAI_API_KEY 环境变量未设置"):
            get_settings().validate_api_key()

    def test_validate_api_key_present(self, monkeypatch):
        """测试 API 密钥存在时返回密钥"""
        from dochris.settings import get_settings, reset_settings

        monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
        reset_settings()  # 重置以加载新的 API key
        result = get_settings().validate_api_key()
        assert result == "test-key-123"


class TestGetFileCategory:
    """测试文件分类函数"""

    @pytest.mark.parametrize(
        "ext,expected",
        [
            (".pdf", "pdfs"),
            (".PDF", "pdfs"),  # 测试大小写不敏感
            (".mp3", "audio"),
            (".mp4", "videos"),
            (".md", "articles"),
            (".epub", "ebooks"),
            (".exe", None),  # 跳过
            (".zip", None),  # 跳过
            (".unknown", "other"),  # 默认分类
        ],
    )
    def test_get_file_category(self, ext, expected):
        """测试各种文件扩展名的分类"""
        result = get_file_category(ext)
        assert result == expected

    def test_get_file_category_case_insensitive(self):
        """测试文件扩展名大小写不敏感"""
        assert get_file_category(".PDF") == get_file_category(".pdf")
        assert get_file_category(".MP3") == get_file_category(".mp3")


class TestSourcePath:
    """测试源路径配置"""

    def test_source_path_is_path_or_none(self):
        """测试源路径是 Path 对象或 None"""
        assert SOURCE_PATH is None or isinstance(SOURCE_PATH, Path)

    def test_source_path_absolute_when_set(self):
        """测试源路径配置后是绝对路径"""
        if SOURCE_PATH is not None:
            assert SOURCE_PATH.is_absolute()
