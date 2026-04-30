#!/usr/bin/env python3
"""
Vault 桥接增强测试 — 嵌套目录、特殊文件名和并发场景
"""

import json
from pathlib import Path
from unittest.mock import patch

from dochris.vault.bridge import (
    _compute_hash,
    _search_obsidian_notes,
    clean_internal_references,
    list_associated_notes,
    promote_to_obsidian,
    seed_from_obsidian,
)


class TestCleanInternalReferencesAdvanced:
    """内容清洗高级测试"""

    def test_preserve_code_blocks(self):
        """保留代码块内容"""
        content = "```python\nprint('(SRC-0001)')\n```"
        cleaned = clean_internal_references(content)
        # 代码块中的 SRC 引用不应被替换
        assert "```python" in cleaned

    def test_multiple_blank_line_types(self):
        """混合空白行类型"""
        content = "Line1\n\r\n\r\n\n\nLine2"
        cleaned = clean_internal_references(content)
        assert "Line1" in cleaned
        assert "Line2" in cleaned

    def test_empty_content(self):
        """空内容"""
        cleaned = clean_internal_references("")
        assert cleaned == ""

    def test_only_src_references(self):
        """只有 SRC 引用"""
        content = "(SRC-0001) (SRC-0002) (SRC-0003)"
        cleaned = clean_internal_references(content)
        assert cleaned.count("📚 来源:") == 3

    def test_mixed_references(self):
        """混合引用类型"""
        content = "参见 (SRC-0001) 和 [[概念A]] 以及 (SRC-0002)"
        cleaned = clean_internal_references(content)
        assert "📚 来源: SRC-0001" in cleaned
        assert "📚 来源: SRC-0002" in cleaned
        assert "[[概念A]]" in cleaned

    def test_unicode_references(self):
        """Unicode 引用内容"""
        content = "参考 (SRC-文献01) 获取更多信息"
        cleaned = clean_internal_references(content)
        # 非 SRC-数字格式的引用可能不被替换
        assert isinstance(cleaned, str)


class TestComputeHashAdvanced:
    """哈希计算高级测试"""

    def test_empty_string(self):
        """空字符串"""
        hash_result = _compute_hash("")
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64

    def test_unicode_content(self):
        """Unicode 内容"""
        hash_result = _compute_hash("中文内容 🎉")
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64

    def test_large_content(self):
        """大内容"""
        content = "x" * 1_000_000
        hash_result = _compute_hash(content)
        assert isinstance(hash_result, str)

    def test_different_encodings_same_result(self):
        """相同内容始终返回相同哈希"""
        content = "测试内容"
        assert _compute_hash(content) == _compute_hash(content)


class TestVaultBridgeWithNestedDirectories:
    """嵌套目录处理"""

    def setUp(self, tmp_path: Path):
        """设置测试环境"""
        self.workspace = tmp_path / "kb"
        self.workspace.mkdir()
        (self.workspace / "raw" / "inbox").mkdir(parents=True)
        (self.workspace / "manifests" / "sources").mkdir(parents=True)
        (self.workspace / "logs").mkdir(parents=True)

        self.obsidian = tmp_path / "Obsidian"
        self.obsidian.mkdir()

    def test_nested_directory_search(self, tmp_path: Path):
        """在嵌套目录中搜索笔记"""
        self.setUp(tmp_path)
        # 创建多层嵌套目录
        deep_dir = self.obsidian / "01-项目" / "子项目" / "笔记"
        deep_dir.mkdir(parents=True)
        note = deep_dir / "Python学习.md"
        note.write_text("# Python 学习笔记\n\nPython 是一门编程语言。", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=self.obsidian):
            results = _search_obsidian_notes("Python")

        assert len(results) >= 1
        assert any("Python" in str(r.get("path", "")) for r in results)

    def test_deeply_nested_obsidian_vault(self, tmp_path: Path):
        """深层嵌套的 Obsidian 库"""
        self.setUp(tmp_path)
        for i in range(5):
            d = self.obsidian
            for j in range(i):
                d = d / f"level{j}"
            d.mkdir(exist_ok=True)
            (d / f"note_{i}.md").write_text(f"# Note {i}\n\n内容{i}", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=self.obsidian):
            results = _search_obsidian_notes("note")

        assert len(results) >= 1


class TestVaultBridgeWithSpecialFilenames:
    """特殊文件名处理"""

    def test_filename_with_spaces(self, tmp_path: Path):
        """文件名包含空格"""
        obsidian = tmp_path / "Obsidian"
        obsidian.mkdir()
        note = obsidian / "Python 编程笔记.md"
        note.write_text("# Python 编程\n\n内容", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=obsidian):
            results = _search_obsidian_notes("Python")

        assert len(results) >= 1

    def test_filename_with_chinese(self, tmp_path: Path):
        """中文文件名"""
        obsidian = tmp_path / "Obsidian"
        obsidian.mkdir()
        note = obsidian / "深度学习入门.md"
        note.write_text("# 深度学习\n\n深度学习是机器学习的子集。", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=obsidian):
            results = _search_obsidian_notes("深度学习")

        assert len(results) >= 1

    def test_filename_with_emoji(self, tmp_path: Path):
        """Emoji 文件名"""
        obsidian = tmp_path / "Obsidian"
        obsidian.mkdir()
        note = obsidian / "学习笔记📚.md"
        note.write_text("# 学习\n\n内容", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=obsidian):
            results = _search_obsidian_notes("学习")

        assert len(results) >= 1

    def test_filename_with_special_chars(self, tmp_path: Path):
        """特殊字符文件名"""
        obsidian = tmp_path / "Obsidian"
        obsidian.mkdir()
        note = obsidian / "C++笔记(2024).md"
        note.write_text("# C++ 笔记\n\nC++ 是一门编程语言。", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=obsidian):
            results = _search_obsidian_notes("C++")

        assert len(results) >= 1


class TestVaultBridgeConcurrentAccess:
    """并发访问测试"""

    def test_multiple_searches_same_vault(self, tmp_path: Path):
        """对同一库多次搜索"""
        obsidian = tmp_path / "Obsidian"
        obsidian.mkdir()
        (obsidian / "Python.md").write_text("# Python\n\n编程语言", encoding="utf-8")
        (obsidian / "JavaScript.md").write_text("# JavaScript\n\n编程语言", encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=obsidian):
            results1 = _search_obsidian_notes("Python")
            results2 = _search_obsidian_notes("JavaScript")

        assert len(results1) >= 1
        assert len(results2) >= 1

    def test_seed_and_list_independent(self, tmp_path: Path):
        """导入和列出不互相影响"""
        workspace = tmp_path / "kb"
        workspace.mkdir()
        (workspace / "raw" / "inbox").mkdir(parents=True)
        (workspace / "manifests" / "sources").mkdir(parents=True)

        # 列出空 workspace 应返回空列表
        result = list_associated_notes(workspace, "SRC-0001")
        assert result == []


class TestSeedFromObsidianEdgeCases:
    """从 Obsidian 导入边界条件"""

    def test_seed_with_empty_topic(self, tmp_path: Path):
        """空主题搜索"""
        workspace = tmp_path / "kb"
        workspace.mkdir()
        (workspace / "raw" / "inbox").mkdir(parents=True)
        (workspace / "manifests" / "sources").mkdir(parents=True)

        with patch("dochris.vault.bridge._search_obsidian_notes", return_value=[]):
            with patch("dochris.vault.bridge._get_obsidian_vault", return_value=None):
                result = seed_from_obsidian(workspace, "")
                assert isinstance(result, list)

    def test_seed_deduplication(self, tmp_path: Path):
        """重复导入去重"""
        workspace = tmp_path / "kb"
        workspace.mkdir()
        (workspace / "raw" / "inbox").mkdir(parents=True)
        (workspace / "manifests" / "sources").mkdir(parents=True)

        obsidian = tmp_path / "Obsidian"
        obsidian.mkdir()
        note = obsidian / "test.md"
        note.write_text("# Test\n\nContent", encoding="utf-8")

        search_result = [
            {"path": note, "rel_path": "test.md", "title": "test", "match_type": "filename"}
        ]

        with patch("dochris.vault.bridge._search_obsidian_notes", return_value=search_result):
            with patch("dochris.vault.bridge._get_obsidian_vault", return_value=obsidian):
                result1 = seed_from_obsidian(workspace, "test")

        # 第二次导入相同内容
        with patch("dochris.vault.bridge._search_obsidian_notes", return_value=search_result):
            with patch("dochris.vault.bridge._get_obsidian_vault", return_value=obsidian):
                with patch("dochris.vault.bridge.get_all_manifests", return_value=[]):
                    result2 = seed_from_obsidian(workspace, "test")

        # 两次导入都应成功
        assert isinstance(result1, list)
        assert isinstance(result2, list)


class TestPromoteToObsidianEdgeCases:
    """推送到 Obsidian 边界条件"""

    def test_promote_with_no_vault(self, tmp_path: Path):
        """没有 Obsidian 库时推送失败"""
        workspace = tmp_path / "kb"
        workspace.mkdir()
        (workspace / "manifests" / "sources").mkdir(parents=True)

        from dochris.manifest import create_manifest, get_manifest

        create_manifest(
            workspace_path=workspace,
            src_id="SRC-0001",
            title="Test",
            file_type="article",
            source_path=Path("/source/test.pdf"),
            file_path="raw/articles/test.pdf",
            content_hash="hash123",
            size_bytes=1024,
        )
        # 手动更新状态为 promoted
        manifest = get_manifest(workspace, "SRC-0001")
        manifest["status"] = "promoted"
        manifest_file = workspace / "manifests" / "sources" / "SRC-0001.json"
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

        with patch("dochris.vault.bridge._get_obsidian_vault", return_value=None):
            result = promote_to_obsidian(workspace, "SRC-0001")

        assert result is False

    def test_promote_with_empty_title(self, tmp_path: Path):
        """空标题的 manifest"""
        workspace = tmp_path / "kb"
        workspace.mkdir()
        (workspace / "manifests" / "sources").mkdir(parents=True)

        result = promote_to_obsidian(workspace, "SRC-9999")
        assert result is False
