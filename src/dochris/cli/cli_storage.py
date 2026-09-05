"""CLI for conservative storage duplicate audits and migrations."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any

from dochris.cli.cli_utils import EXIT_FAILURE, EXIT_SUCCESS
from dochris.settings import get_settings
from dochris.storage.migration import (
    StorageMigrationError,
    audit_storage,
    migrate_storage,
    rollback_storage_migration,
)


def _workspace(args: Namespace) -> Path:
    configured = getattr(args, "workspace", None)
    return Path(configured).expanduser() if configured else get_settings().workspace


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_storage(args: Namespace) -> int:
    """Audit, migrate, or roll back exact duplicate storage files."""
    workspace = _workspace(args)
    command = getattr(args, "storage_command", None)
    json_output = bool(getattr(args, "json", False))

    try:
        if command == "audit":
            audit = audit_storage(workspace)
            if json_output:
                _print_json(audit.as_dict())
            else:
                print(f"已扫描 {audit.scanned_files} 个知识文件")
                print(f"可安全迁移: {len(audit.planned_moves)}")
                print(f"仅报告保留: {len(audit.retained)}")
                for item in audit.planned_moves:
                    print(f"  {item.duplicate} -> {item.canonical}")
            return EXIT_SUCCESS

        if command == "migrate":
            result = migrate_storage(
                workspace,
                apply=bool(getattr(args, "apply", False)),
                backup_dir=getattr(args, "backup_dir", None),
            )
            payload = {
                **result.audit.as_dict(),
                "applied": result.applied,
                "moved": result.moved,
                "manifest_path": str(result.manifest_path) if result.manifest_path else None,
            }
            if json_output:
                _print_json(payload)
            elif not result.applied:
                print(
                    f"dry-run: 计划迁移 {len(result.audit.planned_moves)} 个精确编号副本；"
                    "使用 --apply 才会移动文件"
                )
            elif result.moved:
                print(f"已迁移 {result.moved} 个精确编号副本")
                print(f"回滚 manifest: {result.manifest_path}")
            else:
                print("没有需要迁移的安全副本；存储状态已幂等")
            return EXIT_SUCCESS

        if command == "rollback":
            rollback_result = rollback_storage_migration(workspace, getattr(args, "manifest", None))
            payload = {
                "restored": rollback_result.restored,
                "skipped": rollback_result.skipped,
            }
            if json_output:
                _print_json(payload)
            else:
                print(
                    f"已恢复 {rollback_result.restored} 个文件，"
                    f"跳过 {rollback_result.skipped} 个已存在副本"
                )
            return EXIT_SUCCESS

        print("用法: kb storage <audit|migrate|rollback>")
        return EXIT_FAILURE
    except StorageMigrationError as exc:
        if json_output:
            _print_json({"error": "storage_migration_failed", "detail": str(exc)})
        else:
            print(f"存储迁移失败: {exc}")
        return EXIT_FAILURE
