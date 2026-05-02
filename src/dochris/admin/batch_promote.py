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

import logging
import sys
from pathlib import Path
from typing import Any

# 确保 scripts 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dochris.log import append_log
from dochris.manifest import get_all_manifests
from dochris.promote import promote_to_curated, promote_to_wiki
from dochris.settings import get_settings

logger = logging.getLogger(__name__)

# ============================================================
# 批量 promote 到 wiki
# ============================================================


def batch_promote_to_wiki(
    workspace_path: Path,
    min_score: int = 85,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """批量将 compiled 的产物 promote 到 wiki

    Args:
        workspace_path: 工作区路径
        min_score: 最低质量分数
        limit: 最大处理数量（0 = 不限）
        dry_run: 仅预览，不执行

    Returns:
        操作结果统计
    """
    workspace_path = Path(workspace_path)
    manifests = get_all_manifests(workspace_path, status="compiled")

    # 过滤质量分数
    candidates = [m for m in manifests if m.get("quality_score", 0) >= min_score]
    candidates.sort(key=lambda m: m.get("quality_score", 0), reverse=True)

    if limit > 0:
        candidates = candidates[:limit]

    stats: dict[str, Any] = {"total": len(candidates), "success": 0, "failed": 0, "skipped": 0, "details": []}

    logger.info(f"候选数量: {len(candidates)} 个（min_score={min_score}）")
    if dry_run:
        logger.info("[DRY RUN] 仅预览，不执行")
        for m in candidates[:20]:
            logger.info(f"  {m['id']} | {m.get('title', '')[:40]} | score={m.get('quality_score', 0)}")
        if len(candidates) > 20:
            logger.info(f"  ... 还有 {len(candidates) - 20} 个")
        return stats

    for m in candidates:
        src_id = m["id"]
        title = m.get("title", "")
        score = m.get("quality_score", 0)

        ok = promote_to_wiki(workspace_path, src_id)
        if ok:
            stats["success"] += 1
            stats["details"].append(f"  {src_id} | {title[:40]} | score={score}")
        else:
            stats["failed"] += 1

    # 追加日志
    append_log(
        workspace_path,
        "BATCH_PROMOTE_WIKI",
        f"total={stats['total']}, success={stats['success']}, failed={stats['failed']}",
    )

    logger.info(f"完成: 成功={stats['success']}, 失败={stats['failed']}, 总计={stats['total']}")
    return stats


# ============================================================
# 批量 promote 到 curated
# ============================================================


def batch_promote_to_curated(
    workspace_path: Path,
    min_score: int = 90,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """批量将 wiki 中的产物 promote 到 curated

    Args:
        workspace_path: 工作区路径
        min_score: 最低质量分数
        limit: 最大处理数量（0 = 不限）
        dry_run: 仅预览，不执行

    Returns:
        操作结果统计
    """
    workspace_path = Path(workspace_path)
    manifests = get_all_manifests(workspace_path, status="promoted_to_wiki")

    # 过滤质量分数
    candidates = [m for m in manifests if m.get("quality_score", 0) >= min_score]
    candidates.sort(key=lambda m: m.get("quality_score", 0), reverse=True)

    if limit > 0:
        candidates = candidates[:limit]

    stats: dict[str, Any] = {"total": len(candidates), "success": 0, "failed": 0, "skipped": 0, "details": []}

    logger.info(f"候选数量: {len(candidates)} 个（min_score={min_score}）")
    if dry_run:
        logger.info("[DRY RUN] 仅预览，不执行")
        for m in candidates[:20]:
            logger.info(f"  {m['id']} | {m.get('title', '')[:40]} | score={m.get('quality_score', 0)}")
        if len(candidates) > 20:
            logger.info(f"  ... 还有 {len(candidates) - 20} 个")
        return stats

    for m in candidates:
        src_id = m["id"]
        title = m.get("title", "")
        score = m.get("quality_score", 0)

        ok = promote_to_curated(workspace_path, src_id)
        if ok:
            stats["success"] += 1
            stats["details"].append(f"  {src_id} | {title[:40]} | score={score}")
        else:
            stats["failed"] += 1

    # 追加日志
    append_log(
        workspace_path,
        "BATCH_PROMOTE_CURATED",
        f"total={stats['total']}, success={stats['success']}, failed={stats['failed']}",
    )

    logger.info(f"完成: 成功={stats['success']}, 失败={stats['failed']}, 总计={stats['total']}")
    return stats


# ============================================================
# 批量推送到 Obsidian
# ============================================================


def batch_promote_to_obsidian(
    workspace_path: Path,
    min_score: int = 95,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """批量将 promoted 的产物推送到 Obsidian 主库

    Args:
        workspace_path: 工作区路径
        min_score: 最低质量分数
        limit: 最大处理数量（0 = 不限）
        dry_run: 仅预览，不执行

    Returns:
        操作结果统计
    """
    workspace_path = Path(workspace_path)

    # 导入 vault_bridge
    try:
        from dochris.vault.bridge import promote_to_obsidian
    except ImportError as e:
        logger.error(f"无法导入 vault_bridge: {e}")
        return {"total": 0, "success": 0, "failed": 0}

    manifests = get_all_manifests(workspace_path, status="promoted")

    # 过滤质量分数
    candidates = [m for m in manifests if m.get("quality_score", 0) >= min_score]
    candidates.sort(key=lambda m: m.get("quality_score", 0), reverse=True)

    if limit > 0:
        candidates = candidates[:limit]

    stats: dict[str, Any] = {"total": len(candidates), "success": 0, "failed": 0, "skipped": 0, "details": []}

    logger.info(f"候选数量: {len(candidates)} 个（min_score={min_score}）")
    if dry_run:
        logger.info("[DRY RUN] 仅预览，不执行")
        for m in candidates[:20]:
            logger.info(f"  {m['id']} | {m.get('title', '')[:40]} | score={m.get('quality_score', 0)}")
        if len(candidates) > 20:
            logger.info(f"  ... 还有 {len(candidates) - 20} 个")
        return stats

    for m in candidates:
        src_id = m["id"]
        title = m.get("title", "")
        score = m.get("quality_score", 0)

        ok = promote_to_obsidian(workspace_path, src_id)
        if ok:
            stats["success"] += 1
            stats["details"].append(f"  {src_id} | {title[:40]} | score={score}")
        else:
            stats["failed"] += 1

    # 追加日志
    append_log(
        workspace_path,
        "BATCH_PROMOTE_OBSIDIAN",
        f"total={stats['total']}, success={stats['success']}, failed={stats['failed']}",
    )

    logger.info(f"完成: 成功={stats['success']}, 失败={stats['failed']}, 总计={stats['total']}")
    return stats


# ============================================================
# CLI
# ============================================================


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        print("用法:")
        print(f"  python {sys.argv[0]} <workspace> wiki --min-score 85 --limit 100")
        print(f"  python {sys.argv[0]} <workspace> curated --min-score 90")
        print(f"  python {sys.argv[0]} <workspace> obsidian --min-score 95")
        print(f"  python {sys.argv[0]} <workspace> wiki --dry-run")
        sys.exit(1)

    workspace = Path(sys.argv[1])
    target = sys.argv[2].lower()

    # 解析参数
    min_score = get_settings().min_quality_score
    limit = 0
    dry_run = False

    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--min-score" and i + 1 < len(args):
            min_score = int(args[i + 1])
            i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--dry-run":
            dry_run = True
            i += 1
        else:
            i += 1

    if target == "wiki":
        batch_promote_to_wiki(workspace, min_score, limit, dry_run)
    elif target == "curated":
        batch_promote_to_curated(workspace, min_score, limit, dry_run)
    elif target == "obsidian":
        batch_promote_to_obsidian(workspace, min_score, limit, dry_run)
    else:
        print(f"未知目标: {target}，支持: wiki / curated / obsidian")
        sys.exit(1)


if __name__ == "__main__":
    main()
