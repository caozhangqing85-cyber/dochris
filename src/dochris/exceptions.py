#!/usr/bin/env python3
"""
异常层次结构
定义项目中所有自定义异常
"""


# ============================================================
# 基础异常
# ============================================================


class KnowledgeBaseError(Exception):
    """知识库系统基础异常"""

    pass


# ============================================================
# 配置异常
# ============================================================


class ConfigurationError(KnowledgeBaseError):
    """配置错误"""

    pass


class APIKeyError(ConfigurationError):
    """API 密钥错误或缺失"""

    pass


# ============================================================
# 文件处理异常
# ============================================================


class FileProcessingError(KnowledgeBaseError):
    """文件处理异常"""

    def __init__(self, message: str = "", file_path: str | None = None) -> None:
        super().__init__(message)
        self.file_path = file_path


class IngestionError(FileProcessingError):
    """文件摄入异常"""

    pass


class FileNotFoundError(FileProcessingError):
    """文件不存在"""

    pass


class FileReadError(FileProcessingError):
    """文件读取失败"""

    pass


class TextExtractionError(FileProcessingError):
    """文本提取失败"""

    pass


# ============================================================
# LLM 异常
# ============================================================


class LLMError(KnowledgeBaseError):
    """LLM 调用异常"""

    pass


class LLMTimeoutError(LLMError):
    """LLM 请求超时"""

    pass


class LLMRateLimitError(LLMError):
    """LLM 速率限制"""

    pass


class LLMContentFilterError(LLMError):
    """LLM 内容过滤"""

    pass


class LLMConnectionError(LLMError):
    """LLM 连接错误"""

    pass


class LLMResponseError(LLMError):
    """LLM 响应解析错误"""

    pass


# ============================================================
# 编译异常
# ============================================================


class CompilationError(KnowledgeBaseError):
    """编译异常"""

    pass


class QualityScoreError(CompilationError):
    """质量评分不达标"""

    pass


class CacheError(CompilationError):
    """缓存错误"""

    pass


# ============================================================
# Manifest 异常
# ============================================================


class ManifestError(KnowledgeBaseError):
    """Manifest 异常"""

    pass


class ManifestNotFoundError(ManifestError):
    """Manifest 不存在"""

    pass


class ManifestUpdateError(ManifestError):
    """Manifest 更新失败"""

    pass


# ============================================================
# 查询异常
# ============================================================


class QueryError(KnowledgeBaseError):
    """查询异常"""

    pass


# ============================================================
# API 异常
# ============================================================


class APIError(KnowledgeBaseError):
    """API 异常"""

    def __init__(self, message: str = "", status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ============================================================
# 验证异常
# ============================================================


class ValidationError(KnowledgeBaseError):
    """验证异常"""

    def __init__(self, message: str = "", field: str | None = None) -> None:
        super().__init__(message)
        self.field = field
