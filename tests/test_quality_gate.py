#!/usr/bin/env python3
"""
测试 quality_gate.py 质量门禁系统
12+ 测试用例
"""

import sys
import tempfile
import unittest
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestQualityGate(unittest.TestCase):
    """测试质量门禁功能"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # 创建目录结构
        (self.temp_path / "wiki" / "summaries").mkdir(parents=True)
        (self.temp_path / "wiki" / "concepts").mkdir(parents=True)
        (self.temp_path / "manifests" / "sources").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_min_quality_score_constant(self):
        """测试最低质量分数常量"""
        from dochris.quality.quality_gate import MIN_QUALITY_SCORE
        self.assertEqual(MIN_QUALITY_SCORE, 85)

    def test_quality_gate_pass(self):
        """测试质量门禁通过"""
        from dochris.manifest import create_manifest
        from dochris.quality.quality_gate import quality_gate

        # 创建高质量 manifest
        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0001",
            title="High Quality Doc",
            file_type="article",
            source_path=Path("/source/test.pdf"),
            file_path="raw/articles/test.pdf",
            content_hash="hash123",
            size_bytes=1024,
        )

        # 更新为 compiled 状态且高分
        from dochris.manifest import update_manifest_status
        update_manifest_status(
            self.temp_path,
            "SRC-0001",
            "compiled",
            quality_score=95,
            summary={"one_line": "test"}
        )

        result = quality_gate(self.temp_path, "SRC-0001")
        self.assertTrue(result["passed"])

    def test_quality_gate_fail_low_score(self):
        """测试质量门禁失败（低分）"""
        from dochris.manifest import create_manifest, update_manifest_status
        from dochris.quality.quality_gate import quality_gate

        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0002",
            title="Low Quality Doc",
            file_type="article",
            source_path=Path("/source/test2.pdf"),
            file_path="raw/articles/test2.pdf",
            content_hash="hash456",
            size_bytes=1024,
        )

        update_manifest_status(
            self.temp_path,
            "SRC-0002",
            "compiled",
            quality_score=60,  # 低于 85
            summary={"one_line": "test"}
        )

        result = quality_gate(self.temp_path, "SRC-0002")
        self.assertFalse(result["passed"])

    def test_quality_gate_fail_wrong_status(self):
        """测试质量门禁失败（错误状态）"""
        from dochris.manifest import create_manifest
        from dochris.quality.quality_gate import quality_gate

        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0003",
            title="Ingested Doc",
            file_type="article",
            source_path=Path("/source/test3.pdf"),
            file_path="raw/articles/test3.pdf",
            content_hash="hash789",
            size_bytes=1024,
        )
        # 状态是 ingested，不是 compiled

        result = quality_gate(self.temp_path, "SRC-0003")
        self.assertFalse(result["passed"])

    def test_quality_gate_missing_manifest(self):
        """测试质量门禁（缺失 manifest）"""
        from dochris.quality.quality_gate import quality_gate

        result = quality_gate(self.temp_path, "SRC-9999")
        self.assertFalse(result["passed"])


class TestPollutionDetection(unittest.TestCase):
    """测试污染检测"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        (self.temp_path / "wiki" / "summaries").mkdir(parents=True)
        (self.temp_path / "wiki" / "concepts").mkdir(parents=True)
        (self.temp_path / "manifests" / "sources").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pollution_detection_clean(self):
        """测试污染检测（干净）"""
        from dochris.quality.quality_gate import check_pollution

        result = check_pollution(self.temp_path)
        self.assertFalse(result["polluted"])

    def test_pollution_detection_with_orphans(self):
        """测试污染检测（有孤儿文件）"""
        from dochris.quality.quality_gate import check_pollution

        # 创建孤儿文件（没有对应 promoted manifest）
        orphan_file = self.temp_path / "wiki" / "summaries" / "orphan.md"
        orphan_file.write_text("# Orphan File\n\nNo manifest references this.")

        result = check_pollution(self.temp_path)
        self.assertTrue(result["polluted"])
        self.assertGreater(result["polluted_count"], 0)

    def test_pollution_detection_structure(self):
        """测试污染检测返回结构"""
        from dochris.quality.quality_gate import check_pollution

        result = check_pollution(self.temp_path)

        self.assertIn("polluted", result)
        self.assertIn("polluted_count", result)
        self.assertIn("orphan_summaries", result)
        self.assertIn("orphan_concepts", result)
        self.assertIn("details", result)


class TestAutoDowngrade(unittest.TestCase):
    """测试自动降级"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        (self.temp_path / "wiki" / "summaries").mkdir(parents=True)
        (self.temp_path / "manifests" / "sources").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_auto_downgrade_from_promoted(self):
        """测试从 promoted 降级"""
        from dochris.manifest import create_manifest, update_manifest_status
        from dochris.quality.quality_gate import auto_downgrade

        create_manifest(
            workspace_path=self.temp_path,
            src_id="SRC-0001",
            title="Test Doc",
            file_type="article",
            source_path=Path("/source/test.pdf"),
            file_path="raw/articles/test.pdf",
            content_hash="hash123",
            size_bytes=1024,
        )

        # 先提升到 promoted
        update_manifest_status(
            self.temp_path,
            "SRC-0001",
            "promoted",
            quality_score=90,
            summary={"one_line": "test"}
        )

        # 降级
        result = auto_downgrade(self.temp_path, "SRC-0001", reason="test")
        self.assertTrue(result["success"])
        self.assertEqual(result["from_status"], "promoted")
        self.assertEqual(result["to_status"], "promoted_to_wiki")

    def test_auto_downgrade_invalid_transition(self):
        """测试无效降级转换"""
        from dochris.manifest import create_manifest
        from dochris.quality.quality_gate import auto_downgrade

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
        # ingested 不能再降级

        result = auto_downgrade(self.temp_path, "SRC-0002", reason="test")
        self.assertFalse(result["success"])

    def test_auto_downgrade_nonexistent_manifest(self):
        """测试降级不存在的 manifest"""
        from dochris.quality.quality_gate import auto_downgrade

        result = auto_downgrade(self.temp_path, "SRC-9999", reason="test")
        self.assertFalse(result["success"])


class TestScanWiki(unittest.TestCase):
    """测试 wiki 扫描"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        (self.temp_path / "wiki" / "summaries").mkdir(parents=True)
        (self.temp_path / "wiki" / "concepts").mkdir(parents=True)
        (self.temp_path / "manifests" / "sources").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_wiki_empty(self):
        """测试扫描空的 wiki"""
        from dochris.quality.quality_gate import scan_wiki

        result = scan_wiki(self.temp_path)
        self.assertEqual(result["wiki_summaries"], 0)
        self.assertEqual(result["wiki_concepts"], 0)

    def test_scan_wiki_with_files(self):
        """测试扫描有文件的 wiki"""
        from dochris.quality.quality_gate import scan_wiki

        # 创建测试文件
        (self.temp_path / "wiki" / "summaries" / "test1.md").write_text("# Test 1")
        (self.temp_path / "wiki" / "summaries" / "test2.md").write_text("# Test 2")
        (self.temp_path / "wiki" / "concepts" / "concept1.md").write_text("# Concept 1")

        result = scan_wiki(self.temp_path)
        self.assertEqual(result["wiki_summaries"], 2)
        self.assertEqual(result["wiki_concepts"], 1)

    def test_scan_wiki_result_structure(self):
        """测试扫描结果结构"""
        from dochris.quality.quality_gate import scan_wiki

        result = scan_wiki(self.temp_path)

        self.assertIn("wiki_summaries", result)
        self.assertIn("wiki_concepts", result)
        self.assertIn("wiki_total", result)
        self.assertIn("pollution", result)
        self.assertIn("manifest_total", result)


class TestGenerateReport(unittest.TestCase):
    """测试报告生成"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        (self.temp_path / "wiki" / "summaries").mkdir(parents=True)
        (self.temp_path / "wiki" / "concepts").mkdir(parents=True)
        (self.temp_path / "manifests" / "sources").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_report_structure(self):
        """测试报告结构"""
        from dochris.quality.quality_gate import generate_report

        report = generate_report(self.temp_path)

        self.assertIn("trust_model", report)
        self.assertIn("layers", report)
        self.assertIn("pollution", report)
        self.assertIn("score_distribution", report)
        self.assertIn("min_quality_score", report)

    def test_report_layers(self):
        """测试报告中的信任层级"""
        from dochris.quality.quality_gate import generate_report

        report = generate_report(self.temp_path)

        layers = report["layers"]
        self.assertIn("Layer 0 (outputs/)", layers)
        self.assertIn("Layer 1 (wiki/)", layers)
        self.assertIn("Layer 2 (curated/)", layers)
        self.assertIn("Layer 3 (locked/)", layers)


if __name__ == "__main__":
    unittest.main()
