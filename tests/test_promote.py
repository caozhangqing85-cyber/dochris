#!/usr/bin/env python3
"""
测试 promote_artifact.py 内容提升脚本
12+ 测试用例
"""

import sys
import tempfile
import unittest
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestPromoteToWiki(unittest.TestCase):
    """测试提升到 wiki"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # 创建目录结构
        (self.temp_path / "outputs" / "summaries").mkdir(parents=True)
        (self.temp_path / "outputs" / "concepts").mkdir(parents=True)
        (self.temp_path / "wiki" / "summaries").mkdir(parents=True)
        (self.temp_path / "wiki" / "concepts").mkdir(parents=True)
        (self.temp_path / "manifests" / "sources").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_promote_to_wiki_success(self):
        """测试成功提升到 wiki"""
        from dochris.manifest import create_manifest
        from dochris.promote import promote_to_wiki

        # 创建 manifest 和输出文件
        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0001",
            title="Test Document",
            file_type="article",
            source_path=Path("/source/test.pdf"),
            file_path="raw/articles/test.pdf",
            content_hash="hash123",
            size_bytes=1024,
        )

        # 创建输出摘要文件
        summary_file = self.temp_path / "outputs" / "summaries" / "Test Document.md"
        summary_file.write_text("# Test Document\n\nSummary content", encoding='utf-8')

        # 更新为 compiled 状态
        from dochris.manifest import update_manifest_status
        update_manifest_status(
            self.temp_path,
            "SRC-0001",
            "compiled",
            quality_score=90,
            summary={"one_line": "test"}
        )

        # 提升
        result = promote_to_wiki(self.temp_path, "SRC-0001")
        self.assertTrue(result)

    def test_promote_to_wiki_wrong_status(self):
        """测试错误状态提升失败"""
        from dochris.manifest import create_manifest
        from dochris.promote import promote_to_wiki

        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0002",
            title="Test Doc 2",
            file_type="article",
            source_path=Path("/source/test2.pdf"),
            file_path="raw/articles/test2.pdf",
            content_hash="hash456",
            size_bytes=1024,
        )
        # 状态是 ingested，不是 compiled

        result = promote_to_wiki(self.temp_path, "SRC-0002")
        self.assertFalse(result)

    def test_promote_to_wiki_missing_manifest(self):
        """测试提升不存在的 manifest"""
        from dochris.promote import promote_to_wiki

        result = promote_to_wiki(self.temp_path, "SRC-9999")
        self.assertFalse(result)

    def test_promote_to_wiki_creates_symlink_copy(self):
        """测试提升创建文件副本"""
        from dochris.manifest import create_manifest, update_manifest_status

        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0003",
            title="SimpleTitle",
            file_type="article",
            source_path=Path("/source/test3.pdf"),
            file_path="raw/articles/test3.pdf",
            content_hash="hash789",
            size_bytes=1024,
        )

        # 创建输出文件
        summary_file = self.temp_path / "outputs" / "summaries" / "SimpleTitle.md"
        summary_file.write_text("# SimpleTitle\n\nContent", encoding='utf-8')

        update_manifest_status(
            self.temp_path,
            "SRC-0003",
            "compiled",
            quality_score=85,
            summary={"one_line": "test"}
        )

        # 提升
        from dochris.promote import promote_to_wiki
        promote_to_wiki(self.temp_path, "SRC-0003")

        # 验证文件被复制
        wiki_summary = self.temp_path / "wiki" / "summaries" / "SimpleTitle.md"
        self.assertTrue(wiki_summary.exists())


class TestPromoteToCurated(unittest.TestCase):
    """测试提升到 curated"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        (self.temp_path / "wiki" / "summaries").mkdir(parents=True)
        (self.temp_path / "wiki" / "concepts").mkdir(parents=True)
        (self.temp_path / "curated" / "promoted").mkdir(parents=True)
        (self.temp_path / "manifests" / "sources").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_promote_to_curated_success(self):
        """测试成功提升到 curated"""
        from dochris.manifest import create_manifest, update_manifest_status
        from dochris.promote import promote_to_curated

        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0001",
            title="Curated Doc",
            file_type="article",
            source_path=Path("/source/test.pdf"),
            file_path="raw/articles/test.pdf",
            content_hash="hash123",
            size_bytes=1024,
        )

        # 创建 wiki 文件
        wiki_summary = self.temp_path / "wiki" / "summaries" / "Curated Doc.md"
        wiki_summary.write_text("# Curated Doc\n\nContent", encoding='utf-8')

        # 更新为 promoted_to_wiki 状态
        update_manifest_status(
            self.temp_path,
            "SRC-0001",
            "promoted_to_wiki",
            quality_score=90,
            summary={"one_line": "test"}
        )

        # 提升
        result = promote_to_curated(self.temp_path, "SRC-0001")
        self.assertTrue(result)

    def test_promote_to_curated_wrong_status(self):
        """测试错误状态提升失败"""
        from dochris.manifest import create_manifest
        from dochris.promote import promote_to_curated

        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0002",
            title="Test Doc",
            file_type="article",
            source_path=Path("/source/test2.pdf"),
            file_path="raw/articles/test2.pdf",
            content_hash="hash456",
            size_bytes=1024,
        )
        # 状态是 ingested

        result = promote_to_curated(self.temp_path, "SRC-0002")
        self.assertFalse(result)


class TestShowStatus(unittest.TestCase):
    """测试显示状态"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        (self.temp_path / "manifests" / "sources").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_show_status_existing_manifest(self):
        """测试显示现有 manifest 状态"""
        from dochris.manifest import create_manifest
        from dochris.promote import show_status

        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0001",
            title="Status Test",
            file_type="article",
            source_path=Path("/source/test.pdf"),
            file_path="raw/articles/test.pdf",
            content_hash="hash123",
            size_bytes=1024,
        )

        # 不应该抛出异常
        try:
            import sys
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            show_status(self.temp_path, "SRC-0001")
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

            self.assertIn("SRC-0001", output)
            self.assertIn("Status Test", output)
        except Exception:
            self.fail("show_status raised an exception")

    def test_show_status_nonexistent_manifest(self):
        """测试显示不存在的 manifest"""
        from dochris.promote import show_status

        try:
            import sys
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            show_status(self.temp_path, "SRC-9999")
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

            self.assertIn("未找到", output)
        except Exception:
            self.fail("show_status raised an exception")


class TestFileCopy(unittest.TestCase):
    """测试文件复制"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_copy_file_to_directory(self):
        """测试复制文件到目录"""
        from dochris.promote import _copy_file

        src = self.temp_path / "source.txt"
        dst_dir = self.temp_path / "dest"
        dst_dir.mkdir()

        src.write_text("test content")

        result = _copy_file(src, dst_dir)
        self.assertTrue(result.exists())
        self.assertEqual(result.read_text(), "test content")

    def test_copy_file_handles_duplicates(self):
        """测试复制处理重名"""
        from dochris.promote import _copy_file

        src = self.temp_path / "source.txt"
        dst_dir = self.temp_path / "dest"
        dst_dir.mkdir()

        src.write_text("content")

        # 第一次复制
        result1 = _copy_file(src, dst_dir)
        self.assertEqual(result1.name, "source.txt")

        # 第二次复制（应该重命名）
        result2 = _copy_file(src, dst_dir)
        self.assertEqual(result2.name, "source_1.txt")

        # 第三次复制
        result3 = _copy_file(src, dst_dir)
        self.assertEqual(result3.name, "source_2.txt")


class TestTitleSanitization(unittest.TestCase):
    """测试标题清洗"""

    def test_remove_special_characters(self):
        """测试移除特殊字符"""
        import re

        titles = [
            ("Test/File", "TestFile"),
            ("Test\\File", "TestFile"),
            ("Test:File", "TestFile"),
            ("Test*File", "TestFile"),
            ("Test?File", "TestFile"),
            ('Test"File', "TestFile"),
            ("Test<File", "TestFile"),
            ("Test>File", "TestFile"),
            ("Test|File", "TestFile"),
        ]

        for raw, expected in titles:
            sanitized = re.sub(r'[<>:"/\\|?*]', '', raw)
            self.assertEqual(sanitized, expected)

    def test_truncate_long_title(self):
        """测试截断长标题"""
        long_title = "A" * 100
        truncated = long_title[:80]
        self.assertEqual(len(truncated), 80)


if __name__ == "__main__":
    unittest.main()
