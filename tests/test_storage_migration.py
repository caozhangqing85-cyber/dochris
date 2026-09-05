"""存储重复审计、迁移与回滚测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from dochris.storage.migration import (
    StorageMigrationError,
    audit_storage,
    migrate_storage,
    rollback_storage_migration,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_audit_only_plans_exact_numbered_duplicates(tmp_path: Path) -> None:
    workspace = tmp_path / "kb"
    output_concept = _write(workspace / "outputs/concepts/概念.md", "# 概念\n")
    _write(workspace / "outputs/concepts/概念_SRC-0001.md", "# 概念\n")
    wiki_concept = _write(workspace / "wiki/concepts/概念.md", "# 概念\n")
    numbered = _write(workspace / "wiki/concepts/概念_1.md", "# 概念\n")
    summary = _write(workspace / "outputs/summaries/SRC-0001.md", "# 摘要\n")
    alias = workspace / "outputs/summaries/标题.md"
    alias.symlink_to(summary.name)

    audit = audit_storage(workspace)

    assert [(item.canonical, item.duplicate) for item in audit.planned_moves] == [
        (wiki_concept.relative_to(workspace), numbered.relative_to(workspace))
    ]
    retained_by_kind = {item.kind for item in audit.retained}
    assert retained_by_kind == {
        "cross_tier_replica",
        "source_variant",
        "symlink_alias",
    }
    assert output_concept.exists()
    assert numbered.exists()


def test_migration_defaults_to_dry_run_and_is_idempotent(tmp_path: Path) -> None:
    workspace = tmp_path / "kb"
    canonical = _write(workspace / "wiki/concepts/概念.md", "# 概念\n")
    duplicate = _write(workspace / "wiki/concepts/概念_1.md", "# 概念\n")
    backup_dir = tmp_path / "migration-backup"

    dry_run = migrate_storage(workspace, backup_dir=backup_dir)

    assert dry_run.applied is False
    assert dry_run.moved == 0
    assert duplicate.exists()
    assert not backup_dir.exists()

    applied = migrate_storage(workspace, apply=True, backup_dir=backup_dir)

    assert applied.applied is True
    assert applied.moved == 1
    assert applied.manifest_path == backup_dir / "manifest.json"
    assert canonical.exists()
    assert not duplicate.exists()
    assert (backup_dir / "files/wiki/concepts/概念_1.md").exists()
    assert audit_storage(workspace).planned_moves == []

    repeated = migrate_storage(workspace, apply=True, backup_dir=tmp_path / "second-backup")
    assert repeated.moved == 0
    assert repeated.manifest_path is None


def test_rollback_restores_without_consuming_backup(tmp_path: Path) -> None:
    workspace = tmp_path / "kb"
    _write(workspace / "wiki/summaries/SRC-0001.md", "# 摘要\n")
    duplicate = _write(workspace / "wiki/summaries/SRC-0001_1.md", "# 摘要\n")
    result = migrate_storage(workspace, apply=True, backup_dir=tmp_path / "backup")

    rollback = rollback_storage_migration(workspace, result.manifest_path)

    assert rollback.restored == 1
    assert rollback.skipped == 0
    assert duplicate.read_text(encoding="utf-8") == "# 摘要\n"
    assert (tmp_path / "backup/files/wiki/summaries/SRC-0001_1.md").exists()

    repeated = rollback_storage_migration(workspace, result.manifest_path)
    assert repeated.restored == 0
    assert repeated.skipped == 1


def test_rollback_never_overwrites_conflicting_file(tmp_path: Path) -> None:
    workspace = tmp_path / "kb"
    _write(workspace / "wiki/concepts/概念.md", "# 概念\n")
    duplicate = _write(workspace / "wiki/concepts/概念_1.md", "# 概念\n")
    result = migrate_storage(workspace, apply=True, backup_dir=tmp_path / "backup")
    duplicate.write_text("用户的新内容", encoding="utf-8")

    with pytest.raises(StorageMigrationError, match="拒绝覆盖"):
        rollback_storage_migration(workspace, result.manifest_path)

    assert duplicate.read_text(encoding="utf-8") == "用户的新内容"
