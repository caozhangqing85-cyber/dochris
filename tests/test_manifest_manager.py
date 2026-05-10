"""
Manifest 管理模块单元测试
"""

import csv
import json
from pathlib import Path

from dochris.manifest import (
    append_to_index,
    create_manifest,
    get_all_manifests,
    get_default_workspace,
    get_manifest,
    get_next_src_id,
    rebuild_index,
    update_index_entry,
    update_manifest_status,
)


class TestGetDefaultWorkspace:
    """测试获取默认工作区"""

    def test_returns_path(self):
        """测试返回 Path 对象"""
        result = get_default_workspace()
        assert isinstance(result, Path)

    def test_contains_knowledge_base(self):
        """测试路径包含 knowledge-base"""
        from unittest.mock import patch

        with patch("dochris.settings.paths.get_settings") as mock_settings:
            mock_settings.return_value.workspace = Path.home() / ".openclaw/knowledge-base"
            result = get_default_workspace()
        assert "knowledge-base" in str(result)


class TestGetNextSrcId:
    """测试获取下一个源 ID"""

    def test_empty_directory_returns_src_0001(self, temp_workspace):
        """测试空目录返回 SRC-0001"""
        result = get_next_src_id(temp_workspace)
        assert result == "SRC-0001"

    def test_incrementing_ids(self, temp_workspace):
        """测试递增 ID"""
        # 创建第一个 manifest
        create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test Document",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "abc123",
        )

        result = get_next_src_id(temp_workspace)
        assert result == "SRC-0002"

    def test_skips_invalid_filenames(self, temp_workspace):
        """测试跳过无效文件名"""
        sources_dir = temp_workspace / "manifests" / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)

        # 创建无效文件
        (sources_dir / "invalid.txt").write_text("test")
        (sources_dir / "SRC-invalid.json").write_text("{}")

        result = get_next_src_id(temp_workspace)
        assert result == "SRC-0001"

    def test_finds_maximum_id(self, temp_workspace):
        """测试找到最大 ID"""
        sources_dir = temp_workspace / "manifests" / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)

        # 创建多个 manifest
        for i in [1, 3, 5]:
            manifest_file = sources_dir / f"SRC-{i:04d}.json"
            manifest_file.write_text(json.dumps({"id": f"SRC-{i:04d}"}))

        result = get_next_src_id(temp_workspace)
        assert result == "SRC-0006"


class TestCreateManifest:
    """测试创建 manifest"""

    def test_creates_manifest_file(self, temp_workspace):
        """测试创建 manifest 文件"""
        create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test Document",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "abc123",
        )

        manifest_path = temp_workspace / "manifests" / "sources" / "SRC-0001.json"
        assert manifest_path.exists()

    def test_manifest_content(self, temp_workspace):
        """测试 manifest 内容正确"""
        title = "Test Document"
        file_type = "pdf"
        content_hash = "abc123def456"

        manifest = create_manifest(
            temp_workspace,
            "SRC-0001",
            title,
            file_type,
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            content_hash,
            size_bytes=1024,
        )

        assert manifest["id"] == "SRC-0001"
        assert manifest["title"] == title
        assert manifest["type"] == file_type
        assert manifest["content_hash"] == content_hash
        assert manifest["size_bytes"] == 1024
        assert manifest["status"] == "ingested"
        assert manifest["quality_score"] == 0
        assert manifest["summary"] is None

    def test_creates_with_optional_fields(self, temp_workspace):
        """测试创建带可选字段"""
        tags = ["tag1", "tag2"]
        date_published = "2023-01-01"

        manifest = create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "article",
            Path("/source/test.md"),
            "raw/articles/test.md",
            "hash123",
            tags=tags,
            date_published=date_published,
        )

        assert manifest["tags"] == tags
        assert manifest["date_published"] == date_published

    def test_default_optional_fields(self, temp_workspace):
        """测试默认可选字段"""
        manifest = create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )

        assert manifest["tags"] == []
        assert manifest["date_published"] is None
        assert manifest["error_message"] is None
        assert manifest["promoted_to"] is None


class TestGetManifest:
    """测试获取 manifest"""

    def test_get_existing_manifest(self, temp_workspace):
        """测试获取存在的 manifest"""
        create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )

        manifest = get_manifest(temp_workspace, "SRC-0001")
        assert manifest is not None
        assert manifest["id"] == "SRC-0001"

    def test_get_nonexistent_manifest(self, temp_workspace):
        """测试获取不存在的 manifest 返回 None"""
        manifest = get_manifest(temp_workspace, "SRC-9999")
        assert manifest is None


class TestUpdateManifestStatus:
    """测试更新 manifest 状态"""

    def test_update_status(self, temp_workspace):
        """测试更新状态"""
        create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )

        updated = update_manifest_status(
            temp_workspace,
            "SRC-0001",
            "compiled",
            quality_score=95,
        )

        assert updated is not None
        assert updated["status"] == "compiled"
        assert updated["quality_score"] == 95

    def test_update_nonexistent_manifest(self, temp_workspace):
        """测试更新不存在的 manifest 返回 None"""
        result = update_manifest_status(
            temp_workspace,
            "SRC-9999",
            "compiled",
        )
        assert result is None

    def test_update_with_error_message(self, temp_workspace):
        """测试更新错误消息"""
        create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )

        error_msg = "API 调用失败"
        updated = update_manifest_status(
            temp_workspace,
            "SRC-0001",
            "failed",
            error_message=error_msg,
        )

        assert updated["error_message"] == error_msg
        assert updated["status"] == "failed"

    def test_update_adds_timestamp(self, temp_workspace):
        """测试更新添加时间戳"""
        create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )

        updated = update_manifest_status(
            temp_workspace,
            "SRC-0001",
            "compiled",
        )

        assert "date_compiled" in updated

    def test_update_syncs_to_index(self, temp_workspace):
        """测试更新同步到索引"""
        create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )

        update_manifest_status(
            temp_workspace,
            "SRC-0001",
            "compiled",
            quality_score=90,
        )

        # 检查索引文件是否更新
        index_path = temp_workspace / "manifests" / "source_index.csv"
        assert index_path.exists()

        with open(index_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("id") == "SRC-0001":
                    assert row.get("status") == "compiled"
                    assert row.get("quality_score") == "90"


class TestAppendToIndex:
    """测试追加到索引"""

    def test_creates_index_file(self, temp_workspace):
        """测试创建索引文件"""
        manifest = create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )

        append_to_index(temp_workspace, manifest)

        index_path = temp_workspace / "manifests" / "source_index.csv"
        assert index_path.exists()

    def test_index_has_header(self, temp_workspace):
        """测试索引有表头"""
        manifest = create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )

        append_to_index(temp_workspace, manifest)

        index_path = temp_workspace / "manifests" / "source_index.csv"
        with open(index_path, encoding="utf-8") as f:
            header = f.readline().strip()
            assert "id" in header
            assert "title" in header
            assert "status" in header

    def test_appends_multiple_entries(self, temp_workspace):
        """测试追加多条记录"""
        for i in range(3):
            create_manifest(
                temp_workspace,
                f"SRC-{i + 1:04d}",
                f"Test {i}",
                "pdf",
                Path(f"/source/test{i}.pdf"),
                f"raw/pdfs/test{i}.pdf",
                f"hash{i}",
            )
            # create_manifest 现在会自动调用 append_to_index

        index_path = temp_workspace / "manifests" / "source_index.csv"
        with open(index_path, encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 4  # 1 header + 3 data rows


class TestGetAllManifests:
    """测试获取所有 manifest"""

    def test_empty_directory(self, temp_workspace):
        """测试空目录返回空列表"""
        result = get_all_manifests(temp_workspace)
        assert result == []

    def test_gets_all_manifests(self, temp_workspace):
        """测试获取所有 manifest"""
        for i in range(3):
            create_manifest(
                temp_workspace,
                f"SRC-{i + 1:04d}",
                f"Test {i}",
                "pdf",
                Path(f"/source/test{i}.pdf"),
                f"raw/pdfs/test{i}.pdf",
                f"hash{i}",
            )

        result = get_all_manifests(temp_workspace)
        assert len(result) == 3

    def test_filter_by_status(self, temp_workspace):
        """测试按状态过滤"""
        # 创建不同状态的 manifest
        create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test 1",
            "pdf",
            Path("/source/test1.pdf"),
            "raw/pdfs/test1.pdf",
            "hash1",
        )
        update_manifest_status(temp_workspace, "SRC-0001", "compiled")

        create_manifest(
            temp_workspace,
            "SRC-0002",
            "Test 2",
            "pdf",
            Path("/source/test2.pdf"),
            "raw/pdfs/test2.pdf",
            "hash2",
        )

        compiled = get_all_manifests(temp_workspace, status="compiled")
        all_manifests = get_all_manifests(temp_workspace)

        assert len(compiled) == 1
        assert len(all_manifests) == 2
        assert compiled[0]["id"] == "SRC-0001"

    def test_skips_invalid_json(self, temp_workspace):
        """测试跳过无效 JSON"""
        sources_dir = temp_workspace / "manifests" / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)

        # 创建有效 manifest
        create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )

        # 创建无效 JSON 文件
        (sources_dir / "SRC-0002.json").write_text("invalid json")

        result = get_all_manifests(temp_workspace)
        assert len(result) == 1  # 只返回有效的


class TestUpdateIndexEntry:
    """测试更新索引条目"""

    def test_updates_existing_entry(self, temp_workspace):
        """测试更新现有条目"""
        manifest = create_manifest(
            temp_workspace,
            "SRC-0001",
            "Test",
            "pdf",
            Path("/source/test.pdf"),
            "raw/pdfs/test.pdf",
            "hash123",
        )
        append_to_index(temp_workspace, manifest)

        update_index_entry(
            temp_workspace,
            "SRC-0001",
            "compiled",
            quality_score=95,
        )

        index_path = temp_workspace / "manifests" / "source_index.csv"
        with open(index_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("id") == "SRC-0001":
                    assert row.get("status") == "compiled"
                    assert row.get("quality_score") == "95"

    def test_nonexistent_index_file(self, temp_workspace):
        """测试不存在的索引文件不报错"""
        # 不应该抛出异常
        update_index_entry(temp_workspace, "SRC-0001", "compiled")


class TestRebuildIndex:
    """测试重建索引"""

    def test_rebuilds_from_manifests(self, temp_workspace):
        """测试从 manifest 重建索引"""
        # 创建多个 manifest
        for i in range(3):
            create_manifest(
                temp_workspace,
                f"SRC-{i + 1:04d}",
                f"Test {i}",
                "pdf",
                Path(f"/source/test{i}.pdf"),
                f"raw/pdfs/test{i}.pdf",
                f"hash{i}",
            )
            # 更新一些状态
            if i == 0:
                update_manifest_status(
                    temp_workspace, f"SRC-{i + 1:04d}", "compiled", quality_score=90
                )

        rebuild_index(temp_workspace)

        index_path = temp_workspace / "manifests" / "source_index.csv"
        assert index_path.exists()

        with open(index_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3
            # 检查更新的状态被反映
            compiled_row = next(r for r in rows if r.get("id") == "SRC-0001")
            assert compiled_row.get("status") == "compiled"
            assert compiled_row.get("quality_score") == "90"
