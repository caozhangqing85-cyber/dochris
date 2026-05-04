#!/usr/bin/env python3
"""
批量 Promote 脚本 — 批量晋升知识库产物

功能：
  1. wiki     — 批量 promote 到 wiki（compiled → promoted_to_wiki）
  2. curated  — 批量 promote 到 curated（promoted_to_wiki → promoted）
  3. obsidian — 批量推送到 Obsidian 主库

用法:
  python scripts/batch_promote.py <workspace> wiki --min-score 85 --limit 100
  python scripts/batch_promote.py <workspace> curated --min-score 90
  python scripts/batch_promote.py <workspace> obsidian --min-score 95
"""

import argparse
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dochris.log import append_log
from dochris.manifest import get_all_manifests
from dochris.promote import promote_to_curated, promote_to_wiki
from dochris.settings import get_settings

logger = logging.getLogger(__name__)


# ============================================================
# 通用批量 promote 函数
# ============================================================


def _batch_promote(
    workspace_path: Path,
    target_layer: str,
    promote_fn: Callable[[Path, str], bool],
    source_status: str,
    min_score: int,
    limit: int = 0,
    dry_run: bool = False,
    log_tag: str = "",
) -> dict[str, Any]:
    """通用批量晋升逻辑

    Args:
        workspace_path: 工作区路径
        target_layer: 目标层名称（wiki/curated/obsidian）
        promote_fn: 实际执行晋升的函数 (workspace, src_id) -> bool
        source_status: 筛选的 manifest 状态
        min_score: 最低质量分数
        limit: 最大处理数量（0 = 不限）
        dry_run: 仅预览，不执行
        log_tag: 日志标签

    Returns:
        操作结果统计
    """
    workspace_path = Path(workspace_path)
    manifests = get_all_manifests(workspace_path, status=source_status)

    # 过滤质量分数
    candidates = [m for m in manifests if m.get("quality_score", 0) >= min_score]
    candidates.sort(key=lambda m: m.get("quality_score", 0), reverse=True)

    if limit > 0:
        candidates = candidates[:limit]

    stats: dict[str, Any] = {
        "total": len(candidates),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "details": [],
    }

    logger.info(f"候选数量: {len(candidates)} 个（min_score={min_score}）")
    if dry_run:
        logger.info("[DRY RUN] 仅预览，不执行")
        for m in candidates[:20]:
            logger.info(
                f"  {m['id']} | {m.get('title', '')[:40]} | score={m.get('quality_score', 0)}"
            )
        if len(candidates) > 20:
            logger.info(f"  ... 还有 {len(candidates) - 20} 个")
        return stats

    for m in candidates:
        src_id = m["id"]
        title = m.get("title", "")
        score = m.get("quality_score", 0)

        ok = promote_fn(workspace_path, src_id)
        if ok:
            stats["success"] += 1
            stats["details"].append(f"  {src_id} | {title[:40]} | score={score}")
        else:
            stats["failed"] += 1

    # 追加日志
    append_log(
        workspace_path,
        log_tag or f"BATCH_PROMOTE_{target_layer.upper()}",
        f"total={stats['total']}, success={stats['success']}, failed={stats['failed']}",
    )

    logger.info(f"完成: 成功={stats['success']}, 失败={stats['failed']}, 总计={stats['total']}")
    return stats


# ============================================================
# 对外接口（保持原有签名）
# ============================================================


def batch_promote_to_wiki(
    workspace_path: Path,
    min_score: int = 85,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """批量将 compiled 的产物 promote 到 wiki"""
    return _batch_promote(
        workspace_path=workspace_path,
        target_layer="wiki",
        promote_fn=promote_to_wiki,
        source_status="compiled",
        min_score=min_score,
        limit=limit,
        dry_run=dry_run,
        log_tag="BATCH_PROMOTE_WIKI",
    )


def batch_promote_to_curated(
    workspace_path: Path,
    min_score: int = 90,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """批量将 wiki 中的产物 promote 到 curated"""
    return _batch_promote(
        workspace_path=workspace_path,
        target_layer="curated",
        promote_fn=promote_to_curated,
        source_status="promoted_to_wiki",
        min_score=min_score,
        limit=limit,
        dry_run=dry_run,
        log_tag="BATCH_PROMOTE_CURATED",
    )


def batch_promote_to_obsidian(
    workspace_path: Path,
    min_score: int = 95,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """批量将 promoted 的产物推送到 Obsidian 主库"""
    try:
        from dochris.vault.bridge import promote_to_obsidian
    except ImportError as e:
        logger.error(f"无法导入 vault_bridge: {e}")
        return {"total": 0, "success": 0, "failed": 0}

    return _batch_promote(
        workspace_path=workspace_path,
        target_layer="obsidian",
        promote_fn=promote_to_obsidian,
        source_status="promoted",
        min_score=min_score,
        limit=limit,
        dry_run=dry_run,
        log_tag="BATCH_PROMOTE_OBSIDIAN",
    )


# ============================================================
# CLI
# ============================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="批量 Promote 脚本 — 批量晋升知识库产物",
    )
    parser.add_argument("workspace", type=Path, help="工作区路径")
    parser.add_argument(
        "target",
        choices=["wiki", "curated", "obsidian"],
        help="目标层（wiki/curated/obsidian）",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=None,
        help="最低质量分数（默认: 从配置读取）",
    )
    parser.add_argument("--limit", type=int, default=0, help="最大处理数量（0 = 不限）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行")
    args = parser.parse_args()

    min_score = args.min_score if args.min_score is not None else get_settings().min_quality_score

    if args.target == "wiki":
        batch_promote_to_wiki(args.workspace, min_score, args.limit, args.dry_run)
    elif args.target == "curated":
        batch_promote_to_curated(args.workspace, min_score, args.limit, args.dry_run)
    elif args.target == "obsidian":
        batch_promote_to_obsidian(args.workspace, min_score, args.limit, args.dry_run)


if __name__ == "__main__":
    main()
