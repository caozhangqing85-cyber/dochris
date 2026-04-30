#!/usr/bin/env python3
"""
路径管理函数
提供各种路径获取函数
"""

from pathlib import Path

from dochris.settings.config import get_settings


def get_workspace() -> Path:
    """获取工作区路径（向后兼容）"""
    return get_settings().workspace


def get_logs_dir() -> Path:
    """获取日志目录路径（向后兼容）"""
    return get_settings().logs_dir


def get_cache_dir() -> Path:
    """获取缓存目录路径（向后兼容）"""
    return get_settings().cache_dir


def get_outputs_dir() -> Path:
    """获取输出目录路径（向后兼容）"""
    return get_settings().outputs_dir


def get_raw_dir() -> Path:
    """获取原始文件目录路径（向后兼容）"""
    return get_settings().raw_dir


def get_wiki_dir() -> Path:
    """获取 Wiki 目录路径（向后兼容）"""
    return get_settings().wiki_dir


def get_wiki_summaries_dir() -> Path:
    """获取 Wiki 摘要目录路径（向后兼容）"""
    return get_settings().wiki_summaries_dir


def get_wiki_concepts_dir() -> Path:
    """获取 Wiki 概念目录路径（向后兼容）"""
    return get_settings().wiki_concepts_dir


def get_curated_dir() -> Path:
    """获取精选内容目录路径（向后兼容）"""
    return get_settings().curated_dir


def get_curated_promoted_dir() -> Path:
    """获取精选已推送目录路径（向后兼容）"""
    return get_settings().curated_promoted_dir


def get_manifests_dir() -> Path:
    """获取 Manifest 目录路径（向后兼容）"""
    return get_settings().manifests_dir


def get_data_dir() -> Path:
    """获取数据目录路径（向后兼容）"""
    return get_settings().data_dir


def get_progress_file() -> Path:
    """获取进度文件路径（向后兼容）"""
    return get_settings().progress_file


def get_phase2_lock_file() -> Path:
    """获取 Phase 2 锁文件路径（向后兼容）"""
    return get_settings().phase2_lock_file


def get_query_model() -> str:
    """获取查询模型（向后兼容）"""
    return get_settings().query_model


def get_embedding_model() -> str:
    """获取向量嵌入模型（向后兼容）"""
    return get_settings().embedding_model


def get_default_workspace() -> Path:
    """获取默认工作区路径（向后兼容）"""
    return get_settings().workspace
