"""
dochris: 个人知识库编译系统

四层信任模型:
  Layer 0: outputs/     — LLM 生成，不可信（默认）
  Layer 1: wiki/        — 经 promote 审核，半可信
  Layer 2: curated/     — 人工精选，可信
  Layer 3: locked/      — 锁定保护，不可修改

四阶段流水线:
  Phase 1: 摄入（ingestion）  — 扫描原始文件，创建 manifest
  Phase 2: 编译（compilation） — LLM 异步编译，输出到 outputs/
  Phase 3: 审核（review）     — 质量门禁 + 手动 promote
  Phase 4: 分发（distribution）— Vault Bridge + 批量操作

Usage:
    kb ingest [path]              # Phase 1: 摄入文件
    kb compile [limit]            # Phase 2: 编译
    kb query "关键词" [options]    # Phase 3: 查询
    kb status                     # 显示状态概览
    kb promote <src_id> --to <target>  # Promote 操作
    kb quality [--report]         # 质量检查
    kb vault <subcommand>         # Obsidian 联动
    kb config                     # 显示当前配置
    kb version                    # 显示版本
"""

from typing import Any

__version__ = "1.4.0"
__author__ = "caozhangqing85-cyber"

__all__ = [
    "__version__",
    "__author__",
    "get_settings",
    "Settings",
    "LLMClient",
    # 类型定义
    "FileStatus",
    "FileType",
    "ManifestEntry",
    "CompilationResult",
    "QueryResult",
    "QualityReport",
]


def __getattr__(name: str) -> Any:
    """延迟导入，避免循环依赖

    当访问 LLMClient、Settings 等类型时，仅在需要时导入对应模块。
    """
    if name == "LLMClient":
        from dochris.core.llm_client import LLMClient

        return LLMClient
    elif name == "Settings":
        from dochris.settings import Settings

        return Settings
    elif name == "get_settings":
        from dochris.settings import get_settings

        return get_settings
    elif name in (
        "FileStatus",
        "FileType",
        "ManifestEntry",
        "CompilationResult",
        "QueryResult",
        "QualityReport",
    ):
        from dochris import types

        return getattr(types, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
