#!/usr/bin/env python3
"""
Auto-Recompile：编译配置变更驱动的自动重编译

Karpathy 理论：当 prompt 改进时应自动重编译。
Dochris 实现：通过编译配置指纹检测陈旧内容，支持增量重编译。

核心机制：
1. 编译配置版本化 — 每次编译记录完整配置指纹
2. 陈旧检测 — 对比当前配置与已编译 manifest 的配置
3. 增量重编译 — 只重编译配置不匹配的 manifest
4. 质量对比门 — 新编译质量显著低于旧版则自动回滚

触发方式：
- API: POST /api/v1/recompile/stale
- CLI: kb compile --stale
- 配置变更自动触发: settings 更新时检测

用法：
  from dochris.quality.auto_recompile import (
      trigger_stale_recompile,
      recompile_single,
      get_recompile_status,
  )
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from dochris.log import append_log
from dochris.manifest import get_manifest
from dochris.quality.schema_evolution import (
    compute_compile_config,
    detect_stale_compilations,
    stamp_manifest_config,
)
from dochris.settings import get_settings

logger = logging.getLogger(__name__)

# 重编译状态追踪文件
_RECOMPILE_STATUS_FILE = ".recompile_status.json"


def _status_file_path(workspace_path: Path) -> Path:
    return workspace_path / _RECOMPILE_STATUS_FILE


def get_recompile_status(workspace_path: Path) -> dict[str, Any]:
    """获取重编译状态

    Returns:
        {"last_recompile": str | None, "stale_count": int, "status": str}
    """
    workspace_path = Path(workspace_path)
    sf = _status_file_path(workspace_path)

    status = {
        "last_recompile": None,
        "stale_count": 0,
        "status": "idle",
    }

    if sf.exists():
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
            status.update(data)
        except (json.JSONDecodeError, OSError):
            pass

    # 更新陈旧计数
    stale_info = detect_stale_compilations(workspace_path)
    status["stale_count"] = stale_info["stale_count"]
    status["stale_ids"] = stale_info["stale"]
    status["no_config_count"] = stale_info["no_config_count"]
    status["current_hash"] = stale_info["current_hash"]

    return status


def recompile_single(
    workspace_path: Path,
    src_id: str,
    compile_config: dict[str, Any],
) -> dict[str, Any]:
    """重编译单个 manifest

    流程：
    1. 读取当前 manifest 和旧质量分数
    2. 调用编译器重编译
    3. 对比新旧质量分数
    4. 如果新分数显著低于旧分数，回滚

    Args:
        workspace_path: 工作区路径
        src_id: manifest ID
        compile_config: 当前编译配置

    Returns:
        {"success": bool, "src_id": str, "old_score": int, "new_score": int, "rolled_back": bool}
    """
    workspace_path = Path(workspace_path)
    manifest = get_manifest(workspace_path, src_id)

    if manifest is None:
        return {"success": False, "src_id": src_id, "reason": "manifest 不存在"}

    old_score = manifest.get("quality_score", 0)
    old_status = manifest.get("status", "")

    try:
        # 导入编译器（延迟导入避免循环依赖）
        from dochris.workers.compiler_worker import CompilerWorker

        worker = CompilerWorker(workspace_path=str(workspace_path))

        # 重置 manifest 为 ingested 状态以允许重编译
        from dochris.manifest import update_manifest_status

        update_manifest_status(
            workspace_path,
            src_id,
            status="ingested",
            error_message=None,
        )

        # 执行编译
        result = worker.compile_document(src_id)

        if result is None:
            return {"success": False, "src_id": src_id, "reason": "编译返回 None"}

        # 读取新 manifest
        new_manifest = get_manifest(workspace_path, src_id)
        if new_manifest is None:
            return {"success": False, "src_id": src_id, "reason": "编译后 manifest 丢失"}

        new_score = new_manifest.get("quality_score", 0)

        # 质量对比门：新分数比旧分数低超过 10 分则回滚
        quality_drop = old_score - new_score
        rolled_back = False

        if quality_drop > 10 and old_score > 0:
            logger.warning(
                f"{src_id} 重编译质量下降 {quality_drop} 分 ({old_score} → {new_score})，执行回滚"
            )
            # 回滚：恢复旧状态
            update_manifest_status(
                workspace_path,
                src_id,
                status=old_status,
                quality_score=old_score,
            )
            rolled_back = True
        else:
            # 打上新的编译配置指纹
            stamp_manifest_config(workspace_path, src_id, compile_config)

        return {
            "success": not rolled_back,
            "src_id": src_id,
            "old_score": old_score,
            "new_score": new_score,
            "quality_drop": quality_drop,
            "rolled_back": rolled_back,
        }

    except Exception as e:
        logger.error(f"重编译失败 {src_id}: {e}")
        return {"success": False, "src_id": src_id, "reason": str(e)}


def trigger_stale_recompile(
    workspace_path: Path,
    limit: int = 10,
    concurrency: int = 1,
    dry_run: bool = False,
) -> dict[str, Any]:
    """触发陈旧 manifest 的增量重编译

    Args:
        workspace_path: 工作区路径
        limit: 最大重编译数量
        concurrency: 并发数（当前为顺序执行，预留）
        dry_run: 只检测不执行

    Returns:
        重编译结果汇总
    """
    workspace_path = Path(workspace_path)
    settings = get_settings()

    # 获取当前编译配置
    current_config = compute_compile_config(
        model=settings.model,
        temperature=settings.llm_temperature,
    )

    # 检测陈旧 manifest
    stale_info = detect_stale_compilations(workspace_path, current_config)
    stale_ids = stale_info["stale"]

    if dry_run:
        return {
            "status": "dry_run",
            "stale_count": len(stale_ids),
            "stale_ids": stale_ids[:limit],
            "current_config": current_config,
            "details": f"检测到 {len(stale_ids)} 个陈旧 manifest（模拟运行）",
        }

    # 限制重编译数量
    to_recompile = stale_ids[:limit]

    if not to_recompile:
        return {
            "status": "no_work",
            "recompiled": 0,
            "failed": 0,
            "rolled_back": 0,
            "details": "所有 manifest 均为最新配置",
        }

    # 执行重编译
    results = []
    for src_id in to_recompile:
        result = recompile_single(workspace_path, src_id, current_config)
        results.append(result)

    # 汇总结果
    recompiled = sum(1 for r in results if r.get("success"))
    failed = sum(1 for r in results if not r.get("success"))
    rolled_back = sum(1 for r in results if r.get("rolled_back"))

    # 写入重编译状态
    status_data = {
        "last_recompile": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stale_count": len(stale_ids) - len(to_recompile),
        "recompiled": recompiled,
        "failed": failed,
        "rolled_back": rolled_back,
        "current_hash": current_config["config_hash"],
        "status": "completed",
    }
    sf = _status_file_path(workspace_path)
    try:
        sf.write_text(json.dumps(status_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning(f"写入重编译状态失败: {e}")

    # 记录日志
    append_log(
        workspace_path,
        "AUTO_RECOMPILE",
        f"recompiled={recompiled} failed={failed} rolled_back={rolled_back} "
        f"remaining_stale={len(stale_ids) - len(to_recompile)}",
    )

    return {
        "status": "completed",
        "total_stale": len(stale_ids),
        "recompiled": recompiled,
        "failed": failed,
        "rolled_back": rolled_back,
        "remaining_stale": len(stale_ids) - len(to_recompile),
        "current_config": current_config,
        "details": f"重编译完成: {recompiled} 成功, {failed} 失败, {rolled_back} 回滚",
    }
