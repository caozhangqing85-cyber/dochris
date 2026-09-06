"""Conservative, recoverable migration for exact duplicate knowledge files."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STORAGE_DIRS = (
    Path("outputs/concepts"),
    Path("outputs/summaries"),
    Path("wiki/concepts"),
    Path("wiki/summaries"),
)
_NUMBERED_SUFFIX_RE = re.compile(r"_(\d+)$")
_SOURCE_SUFFIX_RE = re.compile(r"_SRC-\d+$")
_SOURCE_ID_RE = re.compile(r"SRC-\d+$")
_MANIFEST_SCHEMA_VERSION = 1


class StorageMigrationError(RuntimeError):
    """Raised when a storage migration cannot proceed without data risk."""


@dataclass(frozen=True)
class StorageDuplicate:
    """One exact-content alias relationship found by the storage audit."""

    kind: str
    canonical: Path
    duplicate: Path
    content_hash: str
    size_bytes: int
    safe_to_migrate: bool

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["canonical"] = self.canonical.as_posix()
        data["duplicate"] = self.duplicate.as_posix()
        return data


@dataclass(frozen=True)
class StorageAudit:
    """Read-only duplicate audit for the canonical knowledge directories."""

    workspace: Path
    scanned_files: int
    planned_moves: list[StorageDuplicate]
    retained: list[StorageDuplicate]

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace": str(self.workspace),
            "scanned_files": self.scanned_files,
            "safe_to_migrate": len(self.planned_moves),
            "retained_aliases": len(self.retained),
            "planned_moves": [item.as_dict() for item in self.planned_moves],
            "retained": [item.as_dict() for item in self.retained],
        }


@dataclass(frozen=True)
class StorageMigrationResult:
    """Outcome of a dry-run or applied storage migration."""

    audit: StorageAudit
    applied: bool
    moved: int
    manifest_path: Path | None


@dataclass(frozen=True)
class StorageRollbackResult:
    """Outcome of restoring files recorded in a migration manifest."""

    restored: int
    skipped: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path, workspace: Path) -> Path:
    try:
        return path.relative_to(workspace)
    except ValueError as exc:
        raise StorageMigrationError(f"路径不在工作区内: {path}") from exc


def _canonical_rank(path: Path, safe_duplicates: set[Path]) -> tuple[int, int, int, str]:
    """Prefer real, stable identifiers while retaining lifecycle semantics."""
    return (
        int(path in safe_duplicates),
        int(path.is_symlink()),
        0 if _SOURCE_ID_RE.fullmatch(path.stem) else 1,
        path.as_posix(),
    )


def _numbered_base(path: Path) -> Path | None:
    match = _NUMBERED_SUFFIX_RE.search(path.stem)
    if match is None:
        return None
    return path.with_name(f"{path.stem[: match.start()]}{path.suffix}")


def audit_storage(workspace: Path | str) -> StorageAudit:
    """Classify exact duplicate Markdown files without changing storage.

    Only numbered copies in the same directory with an exact-content base file
    are considered safe for automated migration. Lifecycle replicas, source
    variants, and symlink aliases remain visible but are never moved.
    """
    workspace_path = Path(workspace).expanduser().resolve()
    files: list[Path] = []
    for relative_dir in _STORAGE_DIRS:
        root = workspace_path / relative_dir
        if root.exists():
            files.extend(path for path in sorted(root.rglob("*.md")) if path.is_file())

    hashes: dict[Path, str] = {}
    sizes: dict[Path, int] = {}
    groups: dict[str, list[Path]] = {}
    for path in files:
        try:
            content_hash = _sha256(path)
            size = path.stat().st_size
        except OSError as exc:
            raise StorageMigrationError(f"无法审计文件 {path}: {exc}") from exc
        hashes[path] = content_hash
        sizes[path] = size
        groups.setdefault(content_hash, []).append(path)

    planned: list[StorageDuplicate] = []
    retained: list[StorageDuplicate] = []
    safe_duplicates: set[Path] = set()

    for content_hash, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        group_set = set(group)
        for path in group:
            base = _numbered_base(path)
            if (
                base is not None
                and base in group_set
                and not path.is_symlink()
                and not base.is_symlink()
            ):
                safe_duplicates.add(path)
                planned.append(
                    StorageDuplicate(
                        kind="redundant_numbered_copy",
                        canonical=_relative(base, workspace_path),
                        duplicate=_relative(path, workspace_path),
                        content_hash=content_hash,
                        size_bytes=sizes[path],
                        safe_to_migrate=True,
                    )
                )

        canonical = min(group, key=lambda path: _canonical_rank(path, safe_duplicates))
        for path in group:
            if path == canonical or path in safe_duplicates:
                continue
            relation_canonical = canonical
            if path.is_symlink():
                kind = "symlink_alias"
            else:
                source_base = path.with_name(f"{_SOURCE_SUFFIX_RE.sub('', path.stem)}{path.suffix}")
                if _SOURCE_SUFFIX_RE.search(path.stem) and source_base in group_set:
                    kind = "source_variant"
                    relation_canonical = source_base
                elif path.parent != canonical.parent:
                    kind = "cross_tier_replica"
                else:
                    kind = "content_alias"
            retained.append(
                StorageDuplicate(
                    kind=kind,
                    canonical=_relative(relation_canonical, workspace_path),
                    duplicate=_relative(path, workspace_path),
                    content_hash=content_hash,
                    size_bytes=sizes[path],
                    safe_to_migrate=False,
                )
            )

    planned.sort(key=lambda item: item.duplicate.as_posix())
    retained.sort(key=lambda item: (item.kind, item.duplicate.as_posix()))
    return StorageAudit(
        workspace=workspace_path,
        scanned_files=len(files),
        planned_moves=planned,
        retained=retained,
    )


def _default_backup_dir(workspace: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return workspace / "backups" / "storage-migration" / timestamp


def migrate_storage(
    workspace: Path | str,
    *,
    apply: bool = False,
    backup_dir: Path | str | None = None,
) -> StorageMigrationResult:
    """Dry-run or quarantine safe duplicate files with a rollback manifest."""
    audit = audit_storage(workspace)
    if not apply or not audit.planned_moves:
        return StorageMigrationResult(
            audit=audit,
            applied=apply,
            moved=0,
            manifest_path=None,
        )

    workspace_path = audit.workspace
    backup_path = (
        Path(backup_dir).expanduser().resolve()
        if backup_dir is not None
        else _default_backup_dir(workspace_path)
    )
    if backup_path.exists() and any(backup_path.iterdir()):
        raise StorageMigrationError(f"备份目录非空，拒绝复用: {backup_path}")

    moves: list[dict[str, Any]] = []
    for item in audit.planned_moves:
        original = workspace_path / item.duplicate
        canonical = workspace_path / item.canonical
        if not original.exists() or not canonical.exists():
            raise StorageMigrationError(f"迁移前文件状态已变化: {item.duplicate}")
        if _sha256(original) != item.content_hash or _sha256(canonical) != item.content_hash:
            raise StorageMigrationError(f"迁移前内容已变化: {item.duplicate}")
        moves.append(
            {
                "original": item.duplicate.as_posix(),
                "canonical": item.canonical.as_posix(),
                "backup": (Path("files") / item.duplicate).as_posix(),
                "sha256": item.content_hash,
                "size_bytes": item.size_bytes,
            }
        )

    backup_path.mkdir(parents=True, exist_ok=True)
    completed: list[tuple[Path, Path]] = []
    try:
        for move in moves:
            original = workspace_path / move["original"]
            backup_file = backup_path / move["backup"]
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(original), str(backup_file))
            completed.append((original, backup_file))
    except Exception as exc:
        for original, backup_file in reversed(completed):
            if backup_file.exists() and not original.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(backup_file), str(original))
        raise StorageMigrationError(f"迁移失败，已回滚已移动文件: {exc}") from exc

    manifest = {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "workspace": str(workspace_path),
        "moves": moves,
    }
    manifest_path = backup_path / "manifest.json"
    manifest_tmp = backup_path / "manifest.json.tmp"
    manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_tmp.replace(manifest_path)
    return StorageMigrationResult(
        audit=audit,
        applied=True,
        moved=len(moves),
        manifest_path=manifest_path,
    )


def rollback_storage_migration(
    workspace: Path | str, manifest_path: Path | str | None
) -> StorageRollbackResult:
    """Restore a migration without deleting its immutable backup copy."""
    if manifest_path is None:
        raise StorageMigrationError("缺少迁移 manifest 路径")
    workspace_path = Path(workspace).expanduser().resolve()
    manifest_file = Path(manifest_path).expanduser().resolve()
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageMigrationError(f"无法读取迁移 manifest: {exc}") from exc

    if manifest.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise StorageMigrationError("不支持的迁移 manifest 版本")
    if Path(manifest.get("workspace", "")).resolve() != workspace_path:
        raise StorageMigrationError("迁移 manifest 不属于当前工作区")

    restore_plan: list[tuple[Path, Path, str, bool]] = []
    for move in manifest.get("moves", []):
        original = workspace_path / move["original"]
        backup_file = manifest_file.parent / move["backup"]
        expected_hash = move["sha256"]
        if not backup_file.exists() or _sha256(backup_file) != expected_hash:
            raise StorageMigrationError(f"备份缺失或损坏: {move['backup']}")
        if original.exists():
            if _sha256(original) != expected_hash:
                raise StorageMigrationError(f"目标已有新内容，拒绝覆盖: {move['original']}")
            restore_plan.append((original, backup_file, expected_hash, True))
        else:
            restore_plan.append((original, backup_file, expected_hash, False))

    restored = 0
    skipped = 0
    for original, backup_file, _expected_hash, already_present in restore_plan:
        if already_present:
            skipped += 1
            continue
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_file, original)
        restored += 1
    return StorageRollbackResult(restored=restored, skipped=skipped)


def repair_uploads_symlinks(workspace: Path | str) -> dict[str, int]:
    """修复 raw/ 下指向 uploads/inbox 的绝对软链（2026-09 上传持久化迁移）。

    历史行为：Web 上传把实体写入 ``uploads/inbox``，raw/ 保存指向它的绝对
    软链；容器重建后 uploads 卷丢失会导致 raw 全部断链。修复策略是把实体
    迁回 raw/（持久卷），并在 inbox 建立指向 raw 的反向软链。

    幂等：已修复（raw 为真实文件 / 链接已指向 raw）的条目自动跳过。

    Returns:
        {"scanned": 扫描的软链数, "repaired": 修复数, "broken_recovered": 从断链恢复数}
    """
    import logging

    logger = logging.getLogger(__name__)
    ws = Path(workspace)
    raw_dir = ws / "raw"
    inbox_dir = ws / "uploads" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    scanned = repaired = recovered = 0
    if not raw_dir.is_dir():
        return {"scanned": 0, "repaired": 0, "broken_recovered": 0}

    for link in sorted(raw_dir.rglob("*")):
        if not link.is_symlink():
            continue
        scanned += 1
        try:
            target = Path(os.path.realpath(link, strict=False))
        except OSError:
            continue

        entity_moved = False
        if target.is_file() and _is_under(target, ws / "uploads"):
            # 实体在 uploads：迁到 raw 原位，再把 inbox 链回来
            tmp = link.with_name(link.name + ".migrating")
            try:
                os.replace(target, tmp)
                os.replace(tmp, link)
                entity_moved = True
                repaired += 1
            except OSError:
                logger.warning("迁移上传实体失败: %s", link, exc_info=True)
                continue
        elif not target.exists():
            # 断链：实体已丢。无法恢复内容，只记录（由用户重新上传）。
            logger.warning("raw 软链目标缺失（需重新上传）: %s -> %s", link, target)
            continue

        if entity_moved:
            # inbox 反向软链（best-effort）
            inbox_link = inbox_dir / link.name
            try:
                if inbox_link.is_symlink() or inbox_link.exists():
                    inbox_link.unlink()
                os.symlink(str(link.resolve()), str(inbox_link))
            except OSError:
                logger.debug("inbox 反向软链创建失败: %s", link.name, exc_info=True)

        _ = recovered
    return {"scanned": scanned, "repaired": repaired, "broken_recovered": recovered}


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
