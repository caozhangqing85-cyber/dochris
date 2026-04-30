"""
测试 constants.py 模块
"""


class TestConstantsModule:
    """测试常量模块"""

    def test_constants_module_exists(self):
        """测试常量模块可以导入"""
        from dochris import constants

        assert constants is not None

    def test_project_constants(self):
        """测试项目信息常量"""
        from dochris.constants import (
            PROJECT_AUTHOR,
            PROJECT_NAME,
            PROJECT_VERSION,
            REPO_URL,
        )

        assert PROJECT_NAME == "dochris"
        assert PROJECT_VERSION == "1.0.1"
        assert isinstance(PROJECT_AUTHOR, str)
        assert isinstance(REPO_URL, str)

    def test_default_api_config(self):
        """测试默认 API 配置常量"""
        from dochris.constants import (
            DEFAULT_API_BASE,
            DEFAULT_EMBEDDING_MODEL,
            DEFAULT_MODEL,
            DEFAULT_QUERY_MODEL,
        )

        assert isinstance(DEFAULT_API_BASE, str)
        assert "://" in DEFAULT_API_BASE
        assert isinstance(DEFAULT_MODEL, str)
        assert isinstance(DEFAULT_QUERY_MODEL, str)
        assert isinstance(DEFAULT_EMBEDDING_MODEL, str)

    def test_concurrency_config(self):
        """测试并发配置常量"""
        from dochris.constants import DEFAULT_BATCH_SIZE, DEFAULT_MAX_CONCURRENCY

        assert DEFAULT_MAX_CONCURRENCY > 0
        assert DEFAULT_BATCH_SIZE > 0

    def test_quality_threshold(self):
        """测试质量门槛常量"""
        from dochris.constants import DEFAULT_QUALITY_THRESHOLD

        assert 0 <= DEFAULT_QUALITY_THRESHOLD <= 100

    def test_file_size_limits(self):
        """测试文件大小限制常量"""
        from dochris.constants import MAX_CONTENT_CHARS, MAX_FILE_SIZE_MB

        assert MAX_FILE_SIZE_MB > 0
        assert MAX_CONTENT_CHARS > 0

    def test_supported_extensions(self):
        """测试支持的文件扩展名"""
        from dochris.constants import AUDIO_EXTENSIONS, SUPPORTED_EXTENSIONS

        assert isinstance(SUPPORTED_EXTENSIONS, set)
        assert len(SUPPORTED_EXTENSIONS) > 0
        assert all(ext.startswith(".") for ext in SUPPORTED_EXTENSIONS)

        assert isinstance(AUDIO_EXTENSIONS, set)
        assert len(AUDIO_EXTENSIONS) > 0
        assert all(ext in SUPPORTED_EXTENSIONS for ext in AUDIO_EXTENSIONS)

    def test_common_extensions(self):
        """测试常见扩展名存在"""
        from dochris.constants import SUPPORTED_EXTENSIONS

        # 文档类型
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".txt" in SUPPORTED_EXTENSIONS
        assert ".md" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS

        # 音频类型
        assert ".mp3" in SUPPORTED_EXTENSIONS
        assert ".wav" in SUPPORTED_EXTENSIONS

        # 视频类型
        assert ".mp4" in SUPPORTED_EXTENSIONS

    def test_log_level(self):
        """测试默认日志级别"""
        from dochris.constants import DEFAULT_LOG_LEVEL

        assert DEFAULT_LOG_LEVEL in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
