"""Manifest 核心模块测试"""

from __future__ import annotations

import json
from pathlib import Path

from dochris.manifest import (
    create_manifest,
    get_all_manifests,
    get_manifest,
    get_next_src_id,
    rebuild_index,
    update_index_entry,
    update_manifest_status,
)


def _write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── get_next_src_id ────────────────────────────────────────────


class TestGetNextSrcId:
    """获取下一个 SRC ID"""

    def test_empty_directory_returns_src_0001(self, tmp_path):
        """空目录返回 SRC-0001"""
        assert get_next_src_id(tmp_path) == "SRC-0001"

    def test_nonexistent_directory_returns_src_0001(self, tmp_path):
        """目录不存在时返回 SRC-0001"""
        assert get_next_src_id(tmp_path / "no_such_dir") == "SRC-0001"

    def test_picks_max_plus_one(self, tmp_path):
        """取最大编号 +1"""
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        for i in [1, 3, 5]:
            _write_manifest(sources / f"SRC-{i:04d}.json", {"id": f"SRC-{i:04d}"})
        assert get_next_src_id(tmp_path) == "SRC-0006"

    def test_ignores_non_matching_files(self, tmp_path):
        """忽略不匹配的文件名"""
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        _write_manifest(sources / "README.json", {"id": "bad"})
        _write_manifest(sources / "SRC-0002.json", {"id": "SRC-0002"})
        assert get_next_src_id(tmp_path) == "SRC-0003"


# ── get_manifest ───────────────────────────────────────────────


class TestGetManifest:
    """读取单个 manifest"""

    def test_returns_manifest_dict(self, tmp_path):
        """正常读取返回 dict"""
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        data = {"id": "SRC-0001", "title": "Test", "status": "ingested"}
        _write_manifest(sources / "SRC-0001.json", data)
        result = get_manifest(tmp_path, "SRC-0001")
        assert result == data

    def test_returns_none_when_not_found(self, tmp_path):
        """文件不存在返回 None"""
        assert get_manifest(tmp_path, "SRC-9999") is None

    def test_returns_none_for_non_dict_json(self, tmp_path):
        """JSON 不是字典时返回 None"""
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        _write_manifest(sources / "SRC-0001.json", ["not", "a", "dict"])
        assert get_manifest(tmp_path, "SRC-0001") is None

    def test_warns_on_missing_id_field(self, tmp_path):
        """缺少 id 字段时仍然返回数据（但有警告日志）"""
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        data = {"title": "no id field"}
        _write_manifest(sources / "SRC-0001.json", data)
        result = get_manifest(tmp_path, "SRC-0001")
        assert result is not None
        assert "title" in result


# ── create_manifest ────────────────────────────────────────────


class TestCreateManifest:
    """创建 manifest"""

    def test_creates_file_on_disk(self, tmp_path):
        """创建后文件存在于磁盘"""
        m = create_manifest(
            tmp_path,
            src_id="SRC-0001",
            title="Test PDF",
            file_type="pdf",
            source_path=Path("/tmp/test.pdf"),
            file_path="raw/test.pdf",
            content_hash="abc123",
            size_bytes=1024,
        )
        assert m["id"] == "SRC-0001"
        assert m["title"] == "Test PDF"
        assert m["status"] == "ingested"
        assert m["tags"] == []

        manifest_file = tmp_path / "manifests" / "sources" / "SRC-0001.json"
        assert manifest_file.exists()
        loaded = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert loaded["id"] == "SRC-0001"

    def test_creates_index_entry(self, tmp_path):
        """创建时同步写入 source_index.csv"""
        create_manifest(
            tmp_path,
            src_id="SRC-0001",
            title="Indexed",
            file_type="pdf",
            source_path=Path("/tmp/a.pdf"),
            file_path="raw/a.pdf",
            content_hash="h1",
        )
        index_file = tmp_path / "manifests" / "source_index.csv"
        assert index_file.exists()
        content = index_file.read_text(encoding="utf-8")
        assert "SRC-0001" in content
        assert "Indexed" in content

    def test_custom_tags(self, tmp_path):
        """支持自定义标签"""
        m = create_manifest(
            tmp_path,
            src_id="SRC-0002",
            title="Tagged",
            file_type="article",
            source_path=Path("/tmp/a.html"),
            file_path="raw/a.html",
            content_hash="h2",
            tags=["ai", "research"],
        )
        assert m["tags"] == ["ai", "research"]


# ── update_manifest_status ─────────────────────────────────────


class TestUpdateManifestStatus:
    """更新 manifest 状态"""

    def _create_simple(self, tmp_path: Path, src_id: str = "SRC-0001") -> None:
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        _write_manifest(
            sources / f"{src_id}.json",
            {"id": src_id, "title": "T", "status": "ingested", "quality_score": 0},
        )

    def test_updates_status(self, tmp_path):
        """更新状态成功"""
        self._create_simple(tmp_path)
        result = update_manifest_status(tmp_path, "SRC-0001", "compiled", quality_score=90)
        assert result is not None
        assert result["status"] == "compiled"
        assert result["quality_score"] == 90

    def test_returns_none_for_missing(self, tmp_path):
        """manifest 不存在时返回 None"""
        assert update_manifest_status(tmp_path, "SRC-9999", "compiled") is None

    def test_sets_error_message(self, tmp_path):
        """设置错误消息"""
        self._create_simple(tmp_path)
        result = update_manifest_status(
            tmp_path, "SRC-0001", "failed", error_message="OOM"
        )
        assert result["error_message"] == "OOM"

    def test_sets_compiled_timestamp(self, tmp_path):
        """compiled 状态设置 date_compiled"""
        self._create_simple(tmp_path)
        result = update_manifest_status(tmp_path, "SRC-0001", "compiled")
        assert "date_compiled" in result

    def test_sets_failed_timestamp(self, tmp_path):
        """failed 状态设置 date_failed"""
        self._create_simple(tmp_path)
        result = update_manifest_status(tmp_path, "SRC-0001", "failed")
        assert "date_failed" in result

    def test_zero_quality_score_not_overwritten(self, tmp_path):
        """quality_score=0 时不覆盖已有分数"""
        self._create_simple(tmp_path)
        result = update_manifest_status(tmp_path, "SRC-0001", "compiled", quality_score=0)
        assert result["quality_score"] == 0


# ── get_all_manifests ──────────────────────────────────────────


class TestGetAllManifests:
    """获取所有 manifest"""

    def test_empty_directory(self, tmp_path):
        """空目录返回空列表"""
        assert get_all_manifests(tmp_path) == []

    def test_nonexistent_directory(self, tmp_path):
        """目录不存在返回空列表"""
        assert get_all_manifests(tmp_path / "nope") == []

    def test_returns_all_manifests(self, tmp_path):
        """返回目录中所有 manifest"""
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        for i in range(1, 4):
            _write_manifest(
                sources / f"SRC-{i:04d}.json",
                {"id": f"SRC-{i:04d}", "status": "ingested"},
            )
        result = get_all_manifests(tmp_path)
        assert len(result) == 3

    def test_filter_by_status(self, tmp_path):
        """按状态过滤"""
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        _write_manifest(sources / "SRC-0001.json", {"id": "SRC-0001", "status": "compiled"})
        _write_manifest(sources / "SRC-0002.json", {"id": "SRC-0002", "status": "ingested"})
        _write_manifest(sources / "SRC-0003.json", {"id": "SRC-0003", "status": "compiled"})
        result = get_all_manifests(tmp_path, status="compiled")
        assert len(result) == 2

    def test_skips_corrupted_json(self, tmp_path):
        """跳过损坏的 JSON 文件"""
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        _write_manifest(sources / "SRC-0001.json", {"id": "SRC-0001", "status": "ok"})
        (sources / "SRC-0002.json").write_text("{broken json", encoding="utf-8")
        _write_manifest(sources / "SRC-0003.json", {"id": "SRC-0003", "status": "ok"})
        result = get_all_manifests(tmp_path)
        assert len(result) == 2


# ── update_index_entry ─────────────────────────────────────────


class TestUpdateIndexEntry:
    """更新索引条目"""

    def test_updates_existing_entry(self, tmp_path):
        """更新已有索引条目"""
        from dochris.manifest import append_to_index

        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        append_to_index(tmp_path, {"id": "SRC-0001", "title": "T", "type": "pdf",
                                   "date_ingested": "2026-01-01", "file_path": "f",
                                   "content_hash": "h", "status": "ingested", "quality_score": 0})
        update_index_entry(tmp_path, "SRC-0001", "compiled", quality_score=95)
        content = (tmp_path / "manifests" / "source_index.csv").read_text(encoding="utf-8")
        assert "compiled" in content
        assert "95" in content

    def test_nonexistent_index_returns_silently(self, tmp_path):
        """索引文件不存在时静默返回"""
        update_index_entry(tmp_path, "SRC-0001", "compiled")  # 不应抛异常


# ── rebuild_index ──────────────────────────────────────────────


class TestRebuildIndex:
    """从 manifest 文件重建索引"""

    def test_rebuilds_from_scratch(self, tmp_path):
        """从所有 manifest 重建索引"""
        sources = tmp_path / "manifests" / "sources"
        sources.mkdir(parents=True)
        for i, st in enumerate(["compiled", "ingested"], 1):
            _write_manifest(
                sources / f"SRC-{i:04d}.json",
                {"id": f"SRC-{i:04d}", "title": f"File{i}", "type": "pdf",
                 "date_ingested": "2026-01-01", "file_path": f"f{i}",
                 "content_hash": f"h{i}", "status": st, "quality_score": 80},
            )
        rebuild_index(tmp_path)
        index_file = tmp_path / "manifests" / "source_index.csv"
        assert index_file.exists()
        lines = index_file.read_text(encoding="utf-8").strip().split("\n")
        # header + 2 rows
        assert len(lines) == 3
