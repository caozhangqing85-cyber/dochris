#!/usr/bin/env python3
"""
测试 query_utils.py 查询工具函数
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSetupLogging(unittest.TestCase):
    """测试日志设置"""

    def test_setup_logging_returns_logger(self):
        """测试返回 logger 实例"""
        from dochris.phases.query_utils import setup_logging

        logger = setup_logging()

        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "phase3")

    def test_setup_logging_creates_log_file(self):
        """测试创建日志文件"""
        from dochris.phases.query_utils import LOGS_PATH, setup_logging

        setup_logging()

        # 验证日志目录存在
        self.assertTrue(LOGS_PATH.exists())


class TestBuildManifestIndex(unittest.TestCase):
    """测试构建 manifest 索引"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.manifests_dir = self.temp_path / "manifests" / "sources"
        self.manifests_dir.mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_manifest_index_empty(self):
        """测试空目录构建索引"""
        from dochris.phases.query_utils import _build_manifest_index

        with patch('dochris.phases.query_utils.MANIFESTS_PATH', self.manifests_dir):
            index = _build_manifest_index()

        self.assertEqual(index, {})

    def test_build_manifest_index_with_files(self):
        """测试有 manifest 文件时构建索引"""
        from dochris.phases.query_utils import _build_manifest_index

        # 创建测试 manifest
        manifest_data = {
            "id": "SRC-0001",
            "title": "Test Doc",
            "file_path": "raw/articles/test.pdf",
        }
        manifest_file = self.manifests_dir / "SRC-0001.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        with patch('dochris.phases.query_utils.MANIFESTS_PATH', self.manifests_dir):
            index = _build_manifest_index()

        self.assertIn("raw/articles/test.pdf", index)
        self.assertEqual(index["raw/articles/test.pdf"], "SRC-0001")


class TestGetManifestId(unittest.TestCase):
    """测试获取 manifest ID"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.manifests_dir = self.temp_path / "manifests" / "sources"
        self.manifests_dir.mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_manifest_id_direct_match(self):
        """测试直接匹配文件路径"""
        from dochris.phases.query_utils import _get_manifest_id

        manifest_data = {
            "id": "SRC-0001",
            "title": "Test Doc",
            "file_path": "raw/articles/test.pdf",
        }
        manifest_file = self.manifests_dir / "SRC-0001.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        with patch('dochris.phases.query_utils.MANIFESTS_PATH', self.manifests_dir):
            # 清除缓存
            import dochris.phases.query_utils as qu
            qu._manifest_index_cache = None

            result = _get_manifest_id("raw/articles/test.pdf")

        self.assertEqual(result, "SRC-0001")

    def test_get_manifest_id_not_found(self):
        """测试未找到 manifest"""
        from dochris.phases.query_utils import _get_manifest_id

        with patch('dochris.phases.query_utils.MANIFESTS_PATH', self.manifests_dir):
            # 清除缓存
            import dochris.phases.query_utils as qu
            qu._manifest_index_cache = None

            result = _get_manifest_id("nonexistent/file.pdf")

        self.assertIsNone(result)


class TestGetManifestStatus(unittest.TestCase):
    """测试获取 manifest 状态"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.manifests_dir = self.temp_path / "manifests" / "sources"
        self.manifests_dir.mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_manifest_status_found(self):
        """测试找到 manifest 状态"""
        from dochris.phases.query_utils import _get_manifest_status

        manifest_data = {
            "id": "SRC-0001",
            "status": "compiled",
        }
        manifest_file = self.manifests_dir / "SRC-0001.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        with patch('dochris.phases.query_utils.MANIFESTS_PATH', self.manifests_dir):
            result = _get_manifest_status("SRC-0001")

        self.assertEqual(result, "compiled")

    def test_get_manifest_status_not_found(self):
        """测试未找到 manifest"""
        from dochris.phases.query_utils import _get_manifest_status

        with patch('dochris.phases.query_utils.MANIFESTS_PATH', self.manifests_dir):
            result = _get_manifest_status("SRC-9999")

        self.assertIsNone(result)

    def test_get_manifest_status_empty_src_id(self):
        """测试空 src_id"""
        from dochris.phases.query_utils import _get_manifest_status

        result = _get_manifest_status("")

        self.assertIsNone(result)


class TestKeywordSearch(unittest.TestCase):
    """测试关键词搜索"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.search_dir = self.temp_path / "summaries"
        self.search_dir.mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_keyword_search_no_directory(self):
        """测试目录不存在"""
        from dochris.phases.query_utils import _keyword_search

        nonexistent = Path("/nonexistent/directory")
        result = _keyword_search(
            "test",
            nonexistent,
            5,
            lambda p, t: {"title": p.stem},
            "wiki",
        )

        self.assertEqual(result, [])

    def test_keyword_search_with_results(self):
        """测试有搜索结果"""
        from dochris.phases.query_utils import _keyword_search

        # 创建测试文件
        test_file = self.search_dir / "python_basics.md"
        test_file.write_text("# Python Basics\n\nThis is about Python programming.", encoding="utf-8")

        result = _keyword_search(
            "python",
            self.search_dir,
            5,
            lambda p, t: {"title": p.stem},
            "wiki",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "python_basics")

    def test_keyword_search_filename_match(self):
        """测试文件名匹配优先级"""
        from dochris.phases.query_utils import _keyword_search

        # 创建测试文件
        test_file = self.search_dir / "test_concept.md"
        test_file.write_text("Some content", encoding="utf-8")

        result = _keyword_search(
            "test concept",
            self.search_dir,
            5,
            lambda p, t: {"title": p.stem},
            "wiki",
        )

        self.assertGreater(len(result), 0)
        # 文件名精确匹配应该有较高分数
        self.assertGreater(result[0]["score"], 0)


class TestExtractConcept(unittest.TestCase):
    """测试提取概念"""

    def test_extract_concept_with_definition(self):
        """测试提取概念定义"""
        from dochris.phases.query_utils import _extract_concept

        test_file = Path("/tmp/test_concept.md")
        content = """# 概念名

## 定义
这是概念的详细定义。
可以有多行。

## 其他
其他内容...
"""
        result = _extract_concept(test_file, content)

        self.assertEqual(result["name"], "test_concept")
        self.assertIn("概念的详细定义", result["definition"])

    def test_extract_concept_no_definition(self):
        """测试没有定义部分"""
        from dochris.phases.query_utils import _extract_concept

        test_file = Path("/tmp/test_concept.md")
        content = """# 概念名

## 其他
其他内容...
"""
        result = _extract_concept(test_file, content)

        self.assertEqual(result["name"], "test_concept")
        self.assertEqual(result["definition"], "")


class TestExtractSummary(unittest.TestCase):
    """测试提取摘要"""

    def test_extract_summary_complete(self):
        """测试提取完整摘要"""
        from dochris.phases.query_utils import _extract_summary

        test_file = Path("/tmp/test_summary.md")
        content = """# 标题

## 一句话摘要
这是摘要内容。

## 要点
- 要点一
- 要点二
- 要点三
- 要点四（超过限制）

## 其他
其他内容...
"""
        result = _extract_summary(test_file, content)

        self.assertEqual(result["title"], "test_summary")
        self.assertEqual(result["one_line"], "这是摘要内容。")
        self.assertEqual(len(result["key_points"]), 3)  # 最多 3 个
        self.assertEqual(result["key_points"][0], "要点一")

    def test_extract_summary_no_sections(self):
        """测试没有摘要部分"""
        from dochris.phases.query_utils import _extract_summary

        test_file = Path("/tmp/test_summary.md")
        content = """# 标题

只是普通内容...
"""
        result = _extract_summary(test_file, content)

        self.assertEqual(result["title"], "test_summary")
        self.assertEqual(result["one_line"], "")
        self.assertEqual(result["key_points"], [])


class TestPathConstants(unittest.TestCase):
    """测试路径常量"""

    def test_paths_are_defined(self):
        """测试路径常量已定义"""
        from dochris.phases.query_utils import (
            DATA_PATH,
            KB_PATH,
            LOGS_PATH,
            MANIFESTS_PATH,
            WIKI_PATH,
        )

        # 所有路径都应该是 Path 对象
        self.assertIsInstance(KB_PATH, Path)
        self.assertIsInstance(WIKI_PATH, Path)
        self.assertIsInstance(DATA_PATH, Path)
        self.assertIsInstance(LOGS_PATH, Path)
        self.assertIsInstance(MANIFESTS_PATH, Path)


if __name__ == "__main__":
    unittest.main()
