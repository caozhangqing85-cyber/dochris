"""文本索引性能基准测试

测试 manifest 索引、文件扫描、哈希计算等性能。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestIndexingPerformance:
    """索引性能基准"""

    def test_file_hash(self, benchmark, tmp_path: Path) -> None:
        """文件哈希计算性能（1MB 文件）"""
        from dochris.core.cache import file_hash

        f = tmp_path / "test.bin"
        f.write_bytes(b"x" * (1024 * 1024))
        result = benchmark(file_hash, f)
        assert result is not None
        assert len(result) == 64

    def test_cache_save_load(self, benchmark, tmp_path: Path) -> None:
        """缓存读写性能"""
        from dochris.core.cache import cache_dir, load_cached, save_cached

        cdir = cache_dir(tmp_path)
        data = {
            "title": "测试标题",
            "summary": "测试摘要" * 100,
            "key_points": ["要点1", "要点2", "要点3"],
        }

        def save_and_load() -> dict:
            save_cached(cdir, "test-hash-123", data)
            return load_cached(cdir, "test-hash-123")  # type: ignore[return-value]

        result = benchmark(save_and_load)
        assert result is not None
        assert result["title"] == "测试标题"

    def test_manifest_create(self, benchmark, tmp_path: Path) -> None:
        """Manifest 创建性能"""
        from dochris.manifest import create_manifest

        workspace = tmp_path / "ws"
        workspace.mkdir()

        def create_one() -> dict:
            idx = hash(str(id(create_one))) % 10000
            return create_manifest(
                workspace_path=workspace,
                src_id=f"SRC-{idx:04d}",
                title=f"测试文档 {idx}",
                file_type="pdf",
                source_path=Path("/test/file.pdf"),
                file_path="raw/pdfs/file.pdf",
                content_hash="abc123",
                size_bytes=1024,
            )

        result = benchmark(create_one)
        assert result["id"].startswith("SRC-")

    def test_get_all_manifests(self, benchmark, tmp_path: Path) -> None:
        """批量读取 manifest 性能"""
        from dochris.manifest import create_manifest, get_all_manifests

        workspace = tmp_path / "ws"
        workspace.mkdir()

        # 创建 50 个 manifest
        for i in range(50):
            create_manifest(
                workspace_path=workspace,
                src_id=f"SRC-{i + 1:04d}",
                title=f"文档 {i}",
                file_type="pdf",
                source_path=Path(f"/test/file{i}.pdf"),
                file_path=f"raw/pdfs/file{i}.pdf",
                content_hash=f"hash{i}",
                size_bytes=1024,
            )

        result = benchmark(get_all_manifests, workspace)
        assert len(result) == 50

    def test_manifest_update_status(self, benchmark, tmp_path: Path) -> None:
        """Manifest 状态更新性能"""
        from dochris.manifest import create_manifest, update_manifest_status

        workspace = tmp_path / "ws"
        workspace.mkdir()

        create_manifest(
            workspace_path=workspace,
            src_id="SRC-0001",
            title="测试文档",
            file_type="pdf",
            source_path=Path("/test/file.pdf"),
            file_path="raw/pdfs/file.pdf",
            content_hash="abc123",
            size_bytes=1024,
        )

        result = benchmark(
            update_manifest_status,
            workspace,
            "SRC-0001",
            "compiled",
            quality_score=92,
        )
        assert result is not None
        assert result["status"] == "compiled"

    def test_rebuild_index(self, benchmark, tmp_path: Path) -> None:
        """索引重建性能"""
        from dochris.manifest import create_manifest, rebuild_index

        workspace = tmp_path / "ws"
        workspace.mkdir()

        for i in range(50):
            create_manifest(
                workspace_path=workspace,
                src_id=f"SRC-{i + 1:04d}",
                title=f"文档 {i}",
                file_type="pdf",
                source_path=Path(f"/test/file{i}.pdf"),
                file_path=f"raw/pdfs/file{i}.pdf",
                content_hash=f"hash{i}",
                size_bytes=1024,
            )

        benchmark(rebuild_index, workspace)
