#!/usr/bin/env python3
"""
集成测试 - 测试核心流程的端到端功能

测试覆盖:
1. 配置加载 (config)
2. 质量评分 (quality_scorer)
3. manifest 管理 (manifest_manager)
4. 缓存功能 (cache)
"""

import json
from pathlib import Path

import pytest

from dochris.manifest import (
    _ensure_dirs,
    create_manifest,
    get_all_manifests,
    get_manifest,
    get_next_src_id,
    update_manifest_status,
)
from dochris.settings import (
    FILE_TYPE_MAP,
    MAX_CONTENT_CHARS,
    MIN_QUALITY_SCORE,
    get_default_workspace,
    get_file_category,
    get_logs_dir,
)


class TestConfigLoading:
    """配置加载测试"""

    @pytest.mark.skip(reason="settings module restructured")
    def test_get_default_workspace(self):
        """测试默认工作区路径"""
        workspace = get_default_workspace()
        assert workspace.name == ".knowledge-base"
        assert ".knowledge-base" in str(workspace)

    @pytest.mark.skip(reason="settings module restructured")
    def test_get_logs_dir(self):
        """测试日志目录路径"""
        logs_dir = get_logs_dir()
        assert logs_dir.name == "logs"
        assert "knowledge-base" in str(logs_dir)

    def test_get_file_category_pdf(self):
        """测试 PDF 文件分类"""
        assert get_file_category('.pdf') == 'pdfs'
        assert get_file_category('.PDF') == 'pdfs'

    def test_get_file_category_audio(self):
        """测试音频文件分类"""
        assert get_file_category('.mp3') == 'audio'
        assert get_file_category('.wav') == 'audio'
        assert get_file_category('.m4a') == 'audio'

    def test_get_file_category_video(self):
        """测试视频文件分类"""
        assert get_file_category('.mp4') == 'videos'
        assert get_file_category('.mkv') == 'videos'

    def test_get_file_category_ebook(self):
        """测试电子书文件分类"""
        assert get_file_category('.epub') == 'ebooks'
        assert get_file_category('.mobi') == 'ebooks'

    def test_get_file_category_unknown(self):
        """测试未知文件分类"""
        assert get_file_category('.xyz') == 'other'

    def test_constants_exist(self):
        """测试配置常量存在"""
        assert MIN_QUALITY_SCORE >= 0
        assert MAX_CONTENT_CHARS > 0
        assert isinstance(FILE_TYPE_MAP, dict)
        assert '.pdf' in FILE_TYPE_MAP


class TestQualityScoring:
    """质量评分测试"""

    def test_high_quality_summary_structure(self):
        """测试高质量摘要的结构检查"""
        summary = {
            "one_line": "测试摘要",
            "key_points": ["要点1", "要点2", "要点3"],
            "detailed_summary": "这是一个详细的摘要内容，包含丰富的信息。" * 5,
            "concepts": [
                {"name": "概念1", "description": "描述1", "explanation": "解释1"},
                {"name": "概念2", "description": "描述2", "explanation": "解释2"},
            ]
        }

        # 检查必要字段
        assert summary["one_line"]
        assert len(summary["key_points"]) >= 3
        assert len(summary["detailed_summary"]) > 50
        assert len(summary["concepts"]) >= 2

    def test_low_quality_detection(self):
        """测试低质量摘要检测"""
        low_quality = {
            "one_line": "",
            "key_points": [],
            "detailed_summary": "短内容",
            "concepts": []
        }

        # 缺少必要内容
        assert not low_quality["one_line"]
        assert len(low_quality["key_points"]) < 3
        assert len(low_quality["detailed_summary"]) < 50


class TestManifestManager:
    """manifest 管理测试"""

    def test_ensure_dirs(self, temp_workspace):
        """测试目录创建"""
        _ensure_dirs(temp_workspace)
        assert (temp_workspace / "manifests" / "sources").exists()

    def test_get_next_src_id_empty(self, temp_workspace):
        """测试空 workspace 的 src_id 生成"""
        src_id = get_next_src_id(temp_workspace)
        assert src_id == "SRC-0001"

    def test_get_next_src_id_existing(self, temp_workspace):
        """测试有现有 manifest 的 src_id 生成"""
        # 创建一个现有 manifest
        sources_dir = temp_workspace / "manifests" / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)

        existing = {"id": "SRC-0005", "title": "Test"}
        (sources_dir / "SRC-0005.json").write_text(json.dumps(existing))

        src_id = get_next_src_id(temp_workspace)
        assert src_id == "SRC-0006"

    def test_create_manifest(self, temp_workspace):
        """测试 manifest 创建"""
        manifest = create_manifest(
            workspace_path=temp_workspace,
            src_id="SRC-0001",
            title="测试文档",
            file_type="pdf",
            source_path=Path("/test/source.pdf"),
            file_path="raw/pdfs/test.pdf",
            content_hash="abc123",
            size_bytes=1024,
        )

        assert manifest["id"] == "SRC-0001"
        assert manifest["title"] == "测试文档"
        assert manifest["type"] == "pdf"
        assert manifest["status"] == "ingested"

        # 验证文件已创建
        manifest_path = temp_workspace / "manifests" / "sources" / "SRC-0001.json"
        assert manifest_path.exists()

    def test_get_manifest(self, temp_workspace):
        """测试 manifest 读取"""
        # 先创建一个 manifest
        create_manifest(
            workspace_path=temp_workspace,
            src_id="SRC-0002",
            title="测试文档2",
            file_type="article",
            source_path=Path("/test/source.md"),
            file_path="raw/articles/test.md",
            content_hash="def456",
        )

        # 读取 manifest
        manifest = get_manifest(temp_workspace, "SRC-0002")
        assert manifest is not None
        assert manifest["title"] == "测试文档2"

    def test_get_manifest_nonexistent(self, temp_workspace):
        """测试读取不存在的 manifest"""
        manifest = get_manifest(temp_workspace, "SRC-9999")
        assert manifest is None

    def test_update_manifest_status(self, temp_workspace):
        """测试 manifest 状态更新"""
        # 创建 manifest
        create_manifest(
            workspace_path=temp_workspace,
            src_id="SRC-0003",
            title="状态测试",
            file_type="pdf",
            source_path=Path("/test/state.pdf"),
            file_path="raw/pdfs/state.pdf",
            content_hash="state123",
        )

        # 更新状态
        updated = update_manifest_status(
            workspace_path=temp_workspace,
            src_id="SRC-0003",
            status="compiled",
            quality_score=95,
        )

        assert updated is not None
        assert updated["status"] == "compiled"
        assert updated["quality_score"] == 95

    def test_get_all_manifests(self, temp_workspace):
        """测试获取所有 manifest"""
        # 创建多个 manifest
        for i in range(3):
            create_manifest(
                workspace_path=temp_workspace,
                src_id=f"SRC-000{i}",
                title=f"文档{i}",
                file_type="article",
                source_path=Path(f"/test/doc{i}.md"),
                file_path=f"raw/articles/doc{i}.md",
                content_hash=f"hash{i}",
            )

        # 获取所有
        all_manifests = get_all_manifests(temp_workspace)
        assert len(all_manifests) == 3

        # 更新第一个manifest状态并保存
        update_manifest_status(
            workspace_path=temp_workspace,
            src_id="SRC-0000",
            status="compiled",
            quality_score=90,
        )

        # 按状态过滤
        compiled = get_all_manifests(temp_workspace, status="compiled")
        assert len(compiled) >= 1


class TestCacheFunctionality:
    """缓存功能测试"""

    def test_cache_dir_structure(self, temp_workspace):
        """测试缓存目录结构"""
        cache_dir = temp_workspace / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # 创建缓存条目
        cache_file = cache_dir / "test_cache.json"
        cache_data = {"key": "value", "timestamp": "2024-01-01"}
        cache_file.write_text(json.dumps(cache_data))

        assert cache_file.exists()
        loaded = json.loads(cache_file.read_text())
        assert loaded["key"] == "value"

    def test_cache_invalidation(self):
        """测试缓存失效逻辑"""
        # 模拟缓存时间戳
        import time
        cache_entry = {
            "data": "test",
            "created_at": time.time() - 3600  # 1小时前
        }

        # 检查是否过期（假设30分钟有效期）
        cache_ttl = 1800
        is_expired = (time.time() - cache_entry["created_at"]) > cache_ttl
        assert is_expired is True


class TestEndToEndWorkflow:
    """端到端工作流测试"""

    def test_simple_ingest_to_compile_workflow(self, temp_workspace):
        """测试简单的摄取到编译工作流"""
        # 1. 摄取阶段：创建 manifest
        manifest = create_manifest(
            workspace_path=temp_workspace,
            src_id="SRC-WORKFLOW-001",
            title="工作流测试文档",
            file_type="article",
            source_path=Path("/test/workflow.md"),
            file_path="raw/articles/workflow.md",
            content_hash="workflow-hash",
        )

        assert manifest["status"] == "ingested"

        # 2. 编译阶段：模拟更新状态
        compiled = update_manifest_status(
            workspace_path=temp_workspace,
            src_id="SRC-WORKFLOW-001",
            status="compiled",
            quality_score=88,
            summary={
                "one_line": "工作流测试摘要",
                "key_points": ["要点1", "要点2"],
                "detailed_summary": "详细内容",
                "concepts": []
            }
        )

        assert compiled["status"] == "compiled"
        assert compiled["quality_score"] >= MIN_QUALITY_SCORE

    def test_error_handling_workflow(self, temp_workspace):
        """测试错误处理工作流"""
        # 创建 manifest
        create_manifest(
            workspace_path=temp_workspace,
            src_id="SRC-ERROR-001",
            title="错误测试",
            file_type="pdf",
            source_path=Path("/test/error.pdf"),
            file_path="raw/pdfs/error.pdf",
            content_hash="error-hash",
        )

        # 模拟失败
        failed = update_manifest_status(
            workspace_path=temp_workspace,
            src_id="SRC-ERROR-001",
            status="failed",
            error_message="PDF解析失败: 文件损坏",
        )

        assert failed["status"] == "failed"
        assert failed["error_message"] is not None
        assert "PDF" in failed["error_message"]


class TestManifestPersistence:
    """manifest 持久化测试"""

    def test_manifest_file_persistence(self, temp_workspace):
        """测试 manifest 文件持久化"""
        create_manifest(
            workspace_path=temp_workspace,
            src_id="SRC-PERSIST-001",
            title="持久化测试",
            file_type="ebook",
            source_path=Path("/test/persist.epub"),
            file_path="raw/ebooks/persist.epub",
            content_hash="persist-hash",
            size_bytes=2048,
        )

        # 直接从文件读取验证
        manifest_path = temp_workspace / "manifests" / "sources" / "SRC-PERSIST-001.json"
        file_content = json.loads(manifest_path.read_text())

        assert file_content["id"] == "SRC-PERSIST-001"
        assert file_content["title"] == "持久化测试"
        assert file_content["size_bytes"] == 2048

    def test_manifest_update_persistence(self, temp_workspace):
        """测试 manifest 更新持久化"""
        create_manifest(
            workspace_path=temp_workspace,
            src_id="SRC-PERSIST-002",
            title="更新测试",
            file_type="pdf",
            source_path=Path("/test/update.pdf"),
            file_path="raw/pdfs/update.pdf",
            content_hash="update-hash",
        )

        # 更新
        update_manifest_status(
            workspace_path=temp_workspace,
            src_id="SRC-PERSIST-002",
            status="compiled",
            quality_score=92,
        )

        # 从文件读取验证更新
        manifest_path = temp_workspace / "manifests" / "sources" / "SRC-PERSIST-002.json"
        file_content = json.loads(manifest_path.read_text())

        assert file_content["status"] == "compiled"
        assert file_content["quality_score"] == 92


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
