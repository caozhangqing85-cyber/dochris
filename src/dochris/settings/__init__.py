#!/usr/bin/env python3
"""
统一配置管理 - Settings 模块

支持配置优先级: .env 文件 > 环境变量 > 默认值

用法:
    from dochris.settings import get_settings

    settings = get_settings()
    print(settings.workspace)
    print(settings.api_key)
"""

from typing import Any

# ruff: noqa: F405
# ============================================================
# 导入核心类和函数
# ============================================================
from dochris.settings.config import Settings, get_settings, reset_settings
from dochris.settings.constants import *  # noqa: F403
from dochris.settings.file_category import get_file_category

# ============================================================
# 向后兼容：导出所有模块级函数
# ============================================================
from dochris.settings.paths import (
    get_cache_dir,
    get_curated_dir,
    get_curated_promoted_dir,
    get_data_dir,
    get_default_workspace,
    get_embedding_model,
    get_logs_dir,
    get_manifests_dir,
    get_outputs_dir,
    get_phase2_lock_file,
    get_progress_file,
    get_query_model,
    get_raw_dir,
    get_wiki_concepts_dir,
    get_wiki_dir,
    get_wiki_summaries_dir,
    get_workspace,
)

# ============================================================
# 公开 API
# ============================================================

__all__ = [
    # 核心类和函数
    "Settings",
    "get_settings",
    "reset_settings",
    # 路径函数
    "get_workspace",
    "get_logs_dir",
    "get_cache_dir",
    "get_outputs_dir",
    "get_raw_dir",
    "get_wiki_dir",
    "get_wiki_summaries_dir",
    "get_wiki_concepts_dir",
    "get_curated_dir",
    "get_curated_promoted_dir",
    "get_manifests_dir",
    "get_data_dir",
    "get_progress_file",
    "get_phase2_lock_file",
    "get_query_model",
    "get_embedding_model",
    "get_default_workspace",
    # 文件分类
    "get_file_category",
    # 常量（从 constants.py 导入所有）
    "DEFAULT_LLM_API_BASE",
    "OPENROUTER_API_BASE",
    "OPENROUTER_MODEL",
    "DEFAULT_API_KEY",
    "DEFAULT_MODEL",
    "QUALITY_THRESHOLD",
    "MIN_QUALITY_SCORE",
    "TEMPLATE_DEDUCTION",
    "TEMPLATE_PATTERNS",
    "LEARNING_KEYWORDS",
    "INFO_KEYWORDS",
    "DEFAULT_CONCURRENCY",
    "BATCH_SIZE",
    "FILE_TYPE_MAP",
    "SKIP_EXTENSIONS",
    "AUDIO_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "PDF_EXTENSIONS",
    "CODE_EXTENSIONS",
    "DOC_EXTENSIONS",
    "EBOOK_EXTENSIONS",
    "OPENCLAW_CONFIG_PATH",
]  # noqa: F405

# ============================================================
# 模块级便捷变量（延迟访问模式）
# ============================================================


def __getattr__(name: str) -> Any:
    """延迟获取配置值

    允许以模块级变量形式访问配置，同时支持配置动态更新。
    例如: from dochris.settings import SOURCE_PATH

    Args:
        name: 配置项名称

    Returns:
        配置值

    Raises:
        AttributeError: 配置项不存在时
    """
    settings = get_settings()

    # 路径配置
    if name == "SOURCE_PATH":
        return settings.source_path
    elif name == "OBSIDIAN_PATHS":
        return settings.obsidian_vaults
    elif name == "OBSIDIAN_VAULT":
        return settings.obsidian_vaults[0] if settings.obsidian_vaults else None

    # 日志格式
    elif name == "LOG_FORMAT":
        return settings.log_format
    elif name == "LOG_FORMAT_SIMPLE":
        return settings.log_format_simple
    elif name == "LOG_DATE_FORMAT":
        return settings.log_date_format

    # 编译参数
    elif name == "DEFAULT_API_BASE":
        return settings.api_base
    elif name == "DEFAULT_API_KEY":
        return settings.api_key
    elif name == "DEFAULT_MODEL":
        return settings.model
    elif name == "DEFAULT_CONCURRENCY":
        return settings.max_concurrency
    elif name == "BATCH_SIZE":
        return settings.batch_size
    elif name == "LLM_MAX_TOKENS":
        return settings.llm_max_tokens
    elif name == "LLM_TEMPERATURE":
        return settings.llm_temperature
    elif name == "LLM_TIMEOUT":
        return settings.llm_timeout
    elif name == "LLM_REQUEST_DELAY":
        return settings.llm_request_delay

    # 质量/重试/缓存
    elif name == "MAX_CONTENT_CHARS":
        return settings.max_content_chars
    elif name == "MIN_QUALITY_SCORE":
        return settings.min_quality_score
    elif name == "MIN_TEXT_LENGTH" or name == "MIN_AUDIO_TEXT_LENGTH":
        return settings.min_text_length
    elif name == "MAX_FILE_SIZE":
        return settings.max_file_size
    elif name == "MAX_RETRIES":
        return settings.max_retries
    elif name == "CACHE_RETENTION_DAYS":
        return settings.cache_retention_days
    elif name == "QUERY_MODEL":
        return settings.query_model
    elif name == "EMBEDDING_MODEL":
        return settings.embedding_model

    # OpenRouter
    elif name == "OPENROUTER_API_BASE":
        return settings.openrouter_api_base
    elif name == "OPENROUTER_MODEL":
        return settings.openrouter_model

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
