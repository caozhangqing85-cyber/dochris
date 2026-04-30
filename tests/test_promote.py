#!/usr/bin/env python3
"""
Promote 模块单元测试
"""

import pytest

from dochris.promote import (
    _copy_file,
    _ensure_dirs,
    _find_output_file,
    promote_to_curated,
    promote_to_wiki,
    show_status,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """创建临时工作区"""
    workspace = tmp_path / "knowledge-base"
    workspace.mkdir()

    # 创建必要的目录
    (workspace / "outputs" / "summaries").mkdir(parents=True)
    (workspace / "outputs" / "concepts").mkdir(parents=True)
    (workspace / "wiki" / "summaries").mkdir(parents=True)
    (workspace / "wiki" / "concepts").mkdir(parents=True)
    (workspace / "curated" / "promoted").mkdir(parents=True)
    (workspace / "manifests" / "sources").mkdir(parents=True)

    return workspace


@pytest.fixture
def sample_manifest(temp_workspace):
    """创建示例 manifest 文件"""
    import json

    manifest = {
        "id": "SRC-0001",
        "title": "测试文档",
        "type": "pdf",
        "status": "compiled",
        "quality_score": 90,
        "source_path": "/test/source.pdf",
        "file_path": "/test/raw/source.pdf",
        "compiled_summary": {
            "one_line": "测试摘要",
            "key_points": ["要点1", "要点2"],
            "detailed_summary": "详细摘要内容",
            "concepts": [
                {"name": "概念1", "explanation": "解释1"},
                {"name": "概念2", "explanation": "解释2"},
            ],
        },
    }

    manifest_path = temp_workspace / "manifests" / "sources" / "SRC-0001.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest


@pytest.fixture
def sample_output_files(temp_workspace, sample_manifest):
    """创建示例输出文件"""
    # 摘要文件
    summary_path = temp_workspace / "outputs" / "summaries" / "测试文档.md"
    summary_path.write_text("# 测试文档\n\n摘要内容", encoding="utf-8")

    # 概念文件
    concept1_path = temp_workspace / "outputs" / "concepts" / "概念1.md"
    concept1_path.write_text("# 概念1\n\n解释1", encoding="utf-8")

    concept2_path = temp_workspace / "outputs" / "concepts" / "概念2.md"
    concept2_path.write_text("# 概念2\n\n解释2", encoding="utf-8")

    return {
        "summary": summary_path,
        "concepts": [concept1_path, concept2_path],
    }


class TestCopyFile:
    """测试 _copy_file 函数"""

    def test_copy_file_new(self, tmp_path):
        """测试复制新文件"""
        src = tmp_path / "source.txt"
        src.write_text("测试内容")
        dst_dir = tmp_path / "dest"
        dst_dir.mkdir()

        result = _copy_file(src, dst_dir)

        assert result == dst_dir / "source.txt"
        assert result.exists()
        assert result.read_text() == "测试内容"

    def test_copy_file_with_conflict(self, tmp_path):
        """测试处理重名冲突"""
        src = tmp_path / "file.txt"
        src.write_text("内容")
        dst_dir = tmp_path / "dest"
        dst_dir.mkdir()

        # 创建已存在的目标文件
        (dst_dir / "file.txt").write_text("已存在")
        (dst_dir / "file_1.txt").write_text("已存在1")

        result = _copy_file(src, dst_dir)

        # 应该创建 file_2.txt
        assert result == dst_dir / "file_2.txt"
        assert result.exists()
        assert result.read_text() == "内容"

    def test_copy_file_max_retries_exceeded(self, tmp_path, monkeypatch):
        """测试超过最大重试次数"""
        # 降低 MAX_COPY_RETRIES 以加快测试
        import dochris.promote
        monkeypatch.setattr(dochris.promote, "MAX_COPY_RETRIES", 3)

        src = tmp_path / "file.txt"
        src.write_text("内容")
        dst_dir = tmp_path / "dest"
        dst_dir.mkdir()

        # 创建冲突文件：file.txt, file_1.txt, file_2.txt, file_3.txt
        (dst_dir / "file.txt").write_text("已存在")
        for i in range(1, 4):
            (dst_dir / f"file_{i}.txt").write_text(f"已存在{i}")

        with pytest.raises(ValueError, match="文件复制重名冲突超过上限"):
            _copy_file(src, dst_dir)


class TestEnsureDirs:
    """测试 _ensure_dirs 函数"""

    def test_ensure_dirs_creates_missing(self, tmp_path):
        """测试创建缺失的目录"""
        dir1 = tmp_path / "new_dir1"
        dir2 = tmp_path / "new_dir2"

        _ensure_dirs(dir1, dir2)

        assert dir1.exists()
        assert dir2.exists()

    def test_ensure_dirs_existing_ok(self, tmp_path):
        """测试已存在的目录不会报错"""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        # 不应该抛出异常
        _ensure_dirs(existing_dir)


class TestFindOutputFile:
    """测试 _find_output_file 函数"""

    def test_find_output_file_direct_match(self, tmp_path):
        """测试直接文件名匹配"""
        (tmp_path / "SRC-0001.md").write_text("内容")

        result = _find_output_file(tmp_path, "SRC-0001", ".md")

        assert result == tmp_path / "SRC-0001.md"

    def test_find_output_file_not_found(self, tmp_path):
        """测试文件未找到"""
        result = _find_output_file(tmp_path, "SRC-9999", ".md")

        assert result is None


class TestPromoteToWiki:
    """测试 promote_to_wiki 函数"""

    def test_promote_to_wiki_success(
        self, temp_workspace, sample_manifest, sample_output_files, monkeypatch
    ):
        """测试成功晋升到 wiki"""
        # Mock get_manifest 和 update_manifest_status
        def mock_get_manifest(path, src_id):
            return sample_manifest

        def mock_update_status(*args, **kwargs):
            pass

        def mock_append_log(*args, **kwargs):
            pass

        import dochris.promote
        monkeypatch.setattr(dochris.promote, "get_manifest", mock_get_manifest)
        monkeypatch.setattr(dochris.promote, "update_manifest_status", mock_update_status)
        monkeypatch.setattr(dochris.promote, "append_log", mock_append_log)

        result = promote_to_wiki(temp_workspace, "SRC-0001")

        assert result is True
        # 检查文件被复制
        assert (temp_workspace / "wiki" / "summaries" / "测试文档.md").exists()

    def test_promote_to_wiki_manifest_not_found(self, temp_workspace, monkeypatch):
        """测试 manifest 不存在"""
        def mock_get_manifest(path, src_id):
            return None

        import dochris.promote
        monkeypatch.setattr(dochris.promote, "get_manifest", mock_get_manifest)

        result = promote_to_wiki(temp_workspace, "SRC-9999")

        assert result is False

    def test_promote_to_wiki_wrong_status(
        self, temp_workspace, sample_manifest, monkeypatch
    ):
        """测试状态不正确"""
        wrong_manifest = sample_manifest.copy()
        wrong_manifest["status"] = "pending"

        def mock_get_manifest(path, src_id):
            return wrong_manifest

        import dochris.promote
        monkeypatch.setattr(dochris.promote, "get_manifest", mock_get_manifest)

        result = promote_to_wiki(temp_workspace, "SRC-0001")

        assert result is False


class TestPromoteToCurated:
    """测试 promote_to_curated 函数"""

    def test_promote_to_curated_success(
        self, temp_workspace, sample_manifest, sample_output_files, monkeypatch
    ):
        """测试成功晋升到 curated"""
        # 先创建 wiki 中的文件
        wiki_summary = temp_workspace / "wiki" / "summaries" / "测试文档.md"
        wiki_summary.write_text("# Wiki 摘要", encoding="utf-8")

        wiki_concept1 = temp_workspace / "wiki" / "concepts" / "概念1.md"
        wiki_concept1.write_text("# Wiki 概念1", encoding="utf-8")

        # 修改 manifest 状态
        wiki_manifest = sample_manifest.copy()
        wiki_manifest["status"] = "promoted_to_wiki"

        def mock_get_manifest(path, src_id):
            return wiki_manifest

        def mock_update_status(*args, **kwargs):
            pass

        def mock_append_log(*args, **kwargs):
            pass

        import dochris.promote
        monkeypatch.setattr(dochris.promote, "get_manifest", mock_get_manifest)
        monkeypatch.setattr(dochris.promote, "update_manifest_status", mock_update_status)
        monkeypatch.setattr(dochris.promote, "append_log", mock_append_log)

        result = promote_to_curated(temp_workspace, "SRC-0001")

        assert result is True
        # 检查文件被复制到 curated
        assert (temp_workspace / "curated" / "promoted" / "测试文档.md").exists()

    def test_promote_to_curated_wrong_status(
        self, temp_workspace, sample_manifest, monkeypatch
    ):
        """测试状态不正确"""
        def mock_get_manifest(path, src_id):
            return sample_manifest

        import dochris.promote
        monkeypatch.setattr(dochris.promote, "get_manifest", mock_get_manifest)

        result = promote_to_curated(temp_workspace, "SRC-0001")

        assert result is False


class TestShowStatus:
    """测试 show_status 函数"""

    def test_show_status_existing(
        self, temp_workspace, sample_manifest, monkeypatch, capsys
    ):
        """测试显示现有 manifest 状态"""
        def mock_get_manifest(path, src_id):
            return sample_manifest

        import dochris.promote
        monkeypatch.setattr(dochris.promote, "get_manifest", mock_get_manifest)

        show_status(temp_workspace, "SRC-0001")

        captured = capsys.readouterr()
        assert "SRC-0001" in captured.out
        assert "测试文档" in captured.out
        assert "compiled" in captured.out

    def test_show_status_not_found(self, temp_workspace, monkeypatch, capsys):
        """测试 manifest 不存在"""
        def mock_get_manifest(path, src_id):
            return None

        import dochris.promote
        monkeypatch.setattr(dochris.promote, "get_manifest", mock_get_manifest)

        show_status(temp_workspace, "SRC-9999")

        captured = capsys.readouterr()
        assert "未找到 manifest" in captured.out
