"""上传持久化迁移测试（raw 软链反转，修复容器重建丢文件）。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dochris.storage.migration import repair_uploads_symlinks

pytestmark = pytest.mark.fast


def _make_legacy_layout(ws: Path, name: str, content: str) -> tuple[Path, Path]:
    """构造旧行为布局：实体在 uploads/inbox，raw 是指向它的绝对软链。"""
    inbox = ws / "uploads" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    entity = inbox / name
    entity.write_text(content, encoding="utf-8")
    raw_dir = ws / "raw" / "articles"
    raw_dir.mkdir(parents=True, exist_ok=True)
    link = raw_dir / name
    os.symlink(str(entity.resolve()), str(link))
    return link, entity


def test_repair_moves_entity_into_raw_and_relinks_inbox(tmp_path: Path) -> None:
    link, _entity = _make_legacy_layout(tmp_path, "笔记.md", "正文内容")

    # 模拟容器重建：uploads 原实体路径不可依赖（这里直接校验修复后的拓扑）
    stats = repair_uploads_symlinks(tmp_path)

    assert stats["repaired"] == 1
    # raw 现在是真实文件（非软链），内容完好
    assert link.is_file() and not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "正文内容"
    # inbox 出现指向 raw 的反向软链
    inbox_link = tmp_path / "uploads" / "inbox" / "笔记.md"
    assert inbox_link.is_symlink()
    assert os.path.realpath(inbox_link) == os.path.realpath(link)


def test_repair_is_idempotent(tmp_path: Path) -> None:
    link, _ = _make_legacy_layout(tmp_path, "a.md", "aaa")
    repair_uploads_symlinks(tmp_path)

    stats = repair_uploads_symlinks(tmp_path)
    assert stats["repaired"] == 0  # 已是真实文件，跳过
    assert link.read_text(encoding="utf-8") == "aaa"


def test_repair_keeps_external_symlinks_untouched(tmp_path: Path) -> None:
    """指向工作区外部源目录的软链（phase1 行为）不属于迁移范围。"""
    external = tmp_path / "external-src"
    external.mkdir()
    source = external / "b.md"
    source.write_text("外部源文件", encoding="utf-8")
    raw_dir = tmp_path / "raw" / "articles"
    raw_dir.mkdir(parents=True, exist_ok=True)
    link = raw_dir / "b.md"
    os.symlink(str(source.resolve()), str(link))

    stats = repair_uploads_symlinks(tmp_path)

    assert stats["scanned"] == 1
    assert stats["repaired"] == 0
    assert link.is_symlink()  # 保持原样
    assert link.read_text(encoding="utf-8") == "外部源文件"


def test_repair_survives_cross_device_rename(tmp_path: Path, monkeypatch) -> None:
    """模拟 Docker named volume 场景：跨设备 rename 触发 EXDEV 时走复制回退。"""
    import errno

    link, entity = _make_legacy_layout(tmp_path, "跨卷.md", "跨卷内容")
    real_replace = os.replace

    def forbid_replace(src, dst, *args, **kwargs):
        # Docker named volume 下 uploads→raw 的跨卷 rename 必触发 EXDEV；
        # 实现必须先 copyfile 到 raw 同卷临时文件（raw 卷内的 replace 合法）
        if Path(str(src)).is_relative_to(tmp_path / "uploads"):
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr("dochris.storage.migration.os.replace", forbid_replace)
    stats = repair_uploads_symlinks(tmp_path)

    assert stats["repaired"] == 1
    assert link.is_file() and not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "跨卷内容"
    assert not list(tmp_path.rglob("*.migrating")), "临时文件必须清理"
