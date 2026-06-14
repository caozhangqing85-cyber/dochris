#!/usr/bin/env python3
"""
kb clean 命令：清理知识库工作区中的缓存、日志和失败记录
"""

import logging
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def cmd_clean(args: Any) -> int:
    """清理知识库工作区

    Args:
        args: 命令行参数
            - cache: 清理缓存
            - logs: 清理旧日志
            - failed: 清理失败 manifest
            - all: 全部清理

    Returns:
        退出码（0 表示成功，非 0 表示错误）
    """
    clean_cache = getattr(args, "cache", False)
    clean_logs = getattr(args, "logs", False)
    clean_failed = getattr(args, "failed", False)
    clean_all = getattr(args, "all", False)

    if not any([clean_cache, clean_logs, clean_failed, clean_all]):
        print("⚠️  请指定清理目标，使用 --cache/--logs/--failed/--all")
        return 1

    from dochris.settings import get_settings

    settings = get_settings()
    workspace = settings.workspace

    # --all 需要二次确认（交互模式下）
    if clean_all and sys.stdin.isatty():
        print("⚠️  即将执行全部清理：")
        print("   - 清理 .cache/ 目录")
        print("   - 清理 30 天前的日志")
        print("   - 删除 status=failed 的 manifest")
        confirm = input("   确认继续？[y/N]: ")
        if confirm.lower() != "y":
            print("   已取消")
            return 0

    if clean_all:
        clean_cache = clean_logs = clean_failed = True

    total_removed = 0

    if clean_cache:
        total_removed += _clean_cache(workspace)
    if clean_logs:
        total_removed += _clean_logs(workspace)
    if clean_failed:
        total_removed += _clean_failed_manifests(workspace)

    if total_removed > 0:
        print(f"\n✅ 清理完成，共清理 {total_removed} 项")
    else:
        print("\n✅ 没有需要清理的内容")

    return 0


def _clean_cache(workspace: Path) -> int:
    """清理 .cache/ 目录"""
    cache_dir = workspace / ".cache"
    if not cache_dir.exists():
        print("   .cache/ 不存在，跳过")
        return 0

    # 安全校验：cache_dir 必须在 workspace 内，且 workspace 必须是合法工作区
    # （含 manifests/ 子目录），防止 WORKSPACE 误配为 / 或 ~ 时 rmtree 删关键目录
    try:
        cache_dir.resolve().relative_to(workspace.resolve())
    except ValueError:
        print("   ❌ .cache/ 不在 workspace 内，拒绝清理（路径异常）")
        return 0
    if not (workspace / "manifests").exists():
        print("   ❌ workspace 非法（无 manifests/ 目录），拒绝清理")
        return 0

    count = sum(1 for _ in cache_dir.rglob("*") if _.is_file())
    try:
        shutil.rmtree(cache_dir)
        print(f"   🗑️  清理 .cache/ ({count} 个文件)")
        return count
    except OSError as e:
        print(f"   ❌ 清理 .cache/ 失败: {e}")
        return 0


def _clean_logs(workspace: Path) -> int:
    """清理 30 天前的日志"""
    logs_dir = workspace / "logs"
    if not logs_dir.exists():
        print("   logs/ 不存在，跳过")
        return 0

    cutoff = datetime.now(UTC) - timedelta(days=30)
    removed = 0

    for f in logs_dir.rglob("*"):
        if not f.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            continue

    print(f"   🗑️  清理旧日志 ({removed} 个文件，>30天)")
    return removed


def _clean_failed_manifests(workspace: Path) -> int:
    """删除 status=failed 的 manifest（JSON + 索引一并清理）"""
    from dochris.manifest import delete_manifest, get_all_manifests

    manifests_dir = workspace / "manifests" / "sources"
    if not manifests_dir.exists():
        print("   manifests/sources/ 不存在，跳过")
        return 0

    removed = 0
    # 通过 delete_manifest 统一删除，保证索引一致
    for m in get_all_manifests(workspace, status="failed"):
        src_id = m.get("id", "")
        if src_id and delete_manifest(workspace, src_id):
            removed += 1
            logger.debug(f"已删除失败 manifest: {src_id}")

    print(f"   🗑️  清理失败 manifest ({removed} 个文件)")
    return removed
