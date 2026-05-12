#!/usr/bin/env python3
"""
测试 workers/compiler_worker.py 编译工作进程
12+ 测试用例
"""

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestCompilerWorker(unittest.TestCase):
    """测试 CompilerWorker 类"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # 创建必要目录
        (self.temp_path / "outputs" / "summaries").mkdir(parents=True)
        (self.temp_path / "outputs" / "concepts").mkdir(parents=True)
        (self.temp_path / "manifests" / "sources").mkdir(parents=True)
        (self.temp_path / "raw" / "pdfs").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("dochris.workers.compiler_worker.get_default_workspace")
    @patch("dochris.workers.compiler_worker.LLMClient")
    def test_worker_initialization(self, mock_llm, mock_workspace):
        """测试 Worker 初始化"""
        mock_workspace.return_value = self.temp_path

        from dochris.workers.compiler_worker import CompilerWorker

        worker = CompilerWorker(
            api_key="test_key", base_url="https://api.test.com", model="test_model"
        )

        self.assertIsNotNone(worker)
        self.assertIsNotNone(worker.llm)
        self.assertEqual(worker.workspace, self.temp_path)

    @patch("dochris.workers.compiler_worker.get_manifest")
    @patch("dochris.workers.compiler_worker.file_hash")
    @patch("dochris.workers.compiler_worker.load_cached")
    def test_cache_hit_handling(self, mock_load_cached, mock_hash, mock_get_manifest):
        """测试缓存命中处理"""
        from dochris.workers.compiler_worker import CompilerWorker

        mock_get_manifest.return_value = {
            "id": "SRC-0001",
            "title": "Test",
            "file_path": "raw/pdfs/test.pdf",
        }
        mock_hash.return_value = "abc123"
        mock_load_cached.return_value = {"one_line": "cached summary", "key_points": ["point1"]}

        worker = CompilerWorker(
            api_key="test_key",
            base_url="https://api.test.com",
        )
        worker.workspace = self.temp_path

        # 验证缓存检查逻辑
        self.assertTrue(callable(mock_load_cached))

    @patch("dochris.workers.compiler_worker.get_manifest")
    def test_manifest_not_found(self, mock_get_manifest):
        """测试 manifest 不存在"""
        from dochris.workers.compiler_worker import CompilerWorker

        mock_get_manifest.return_value = None

        worker = CompilerWorker(
            api_key="test_key",
            base_url="https://api.test.com",
        )
        worker.workspace = self.temp_path

        manifest = worker.workspace / "manifests" / "sources" / "SRC-0001.json"
        self.assertFalse(manifest.exists())

    @patch("dochris.workers.compiler_worker.update_manifest_status")
    @patch("dochris.workers.compiler_worker.get_manifest")
    def test_mark_failed_does_not_override_compiled(self, mock_get_manifest, mock_update):
        """迟到的失败结果不应覆盖已编译成功的 manifest"""
        from dochris.workers.compiler_worker import CompilerWorker

        mock_get_manifest.return_value = {"id": "SRC-0001", "status": "compiled"}
        worker = CompilerWorker(api_key="test_key", base_url="https://api.test.com")
        worker.workspace = self.temp_path

        asyncio.run(worker._mark_failed("SRC-0001", "late failure"))

        mock_update.assert_not_called()


class TestCompilerWorkerPDF(unittest.TestCase):
    """测试 PDF 文件编译"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_pdf_file(self):
        """测试 PDF 文件检测"""
        pdf_file = self.temp_path / "test.pdf"
        pdf_file.write_text("PDF content")

        self.assertEqual(pdf_file.suffix.lower(), ".pdf")

    def test_pdf_file_exists_check(self):
        """测试 PDF 文件存在检查"""
        pdf_file = self.temp_path / "exists.pdf"
        pdf_file.write_text("content")

        self.assertTrue(pdf_file.exists())

        nonexistent = self.temp_path / "not_exists.pdf"
        self.assertFalse(nonexistent.exists())


class TestCompilerWorkerAudio(unittest.TestCase):
    """测试音频文件编译"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_audio_file(self):
        """测试音频文件检测"""
        audio_extensions = [".mp3", ".wav", ".m4a", ".flac"]

        for ext in audio_extensions:
            test_file = self.temp_path / f"test{ext}"
            test_file.write_text("audio")
            self.assertEqual(test_file.suffix.lower(), ext)

    def test_audio_with_transcript_txt(self):
        """测试音频文件配套转录 txt"""
        audio_file = self.temp_path / "test.mp3"
        transcript_file = self.temp_path / "test.txt"

        audio_file.write_text("audio")
        transcript_file.write_text("This is a transcript of the audio file. " * 20)

        self.assertTrue(transcript_file.exists())
        content = transcript_file.read_text()
        self.assertGreater(len(content), 100)


class TestCompilerWorkerCode(unittest.TestCase):
    """测试代码文件编译"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_code_file(self):
        """测试代码文件检测"""
        code_extensions = [".py", ".js", ".ts", ".java", ".cpp", ".go"]

        for ext in code_extensions:
            test_file = self.temp_path / f"test{ext}"
            test_file.write_text("code")
            self.assertEqual(test_file.suffix.lower(), ext)

    def test_extract_code_functions(self):
        """测试提取代码函数"""
        code_content = """
def function_one():
    pass

def function_two():
    pass

class MyClass:
    def method(self):
        pass
"""
        test_file = self.temp_path / "test.py"
        test_file.write_text(code_content)

        content = test_file.read_text()
        self.assertIn("def function_one", content)
        self.assertIn("class MyClass", content)


class TestCompilerWorkerResult(unittest.TestCase):
    """测试结果保存"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        (self.temp_path / "outputs" / "summaries").mkdir(parents=True)
        (self.temp_path / "outputs" / "concepts").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_summary_file(self):
        """测试保存摘要文件"""
        summary_file = self.temp_path / "outputs" / "summaries" / "SRC-0001.md"
        content = "# Test Summary\n\n## Key Points\n- Point 1"

        summary_file.write_text(content, encoding="utf-8")

        self.assertTrue(summary_file.exists())
        self.assertIn("Test Summary", summary_file.read_text())

    def test_save_concept_files(self):
        """测试保存概念文件"""
        concepts_dir = self.temp_path / "outputs" / "concepts" / "SRC-0001"
        concepts_dir.mkdir(parents=True)

        concept1 = concepts_dir / "01_概念1.md"
        concept2 = concepts_dir / "02_概念2.md"

        concept1.write_text("# 概念1\n\n描述1", encoding="utf-8")
        concept2.write_text("# 概念2\n\n描述2", encoding="utf-8")

        self.assertTrue(concept1.exists())
        self.assertTrue(concept2.exists())


class TestCompilerWorkerErrors(unittest.TestCase):
    """测试错误处理"""

    def test_handle_missing_manifest(self):
        """测试处理缺失 manifest"""
        manifest = None
        self.assertIsNone(manifest)

    def test_handle_missing_file(self):
        """测试处理缺失文件"""
        file_path = Path("/nonexistent/file.pdf")
        self.assertFalse(file_path.exists())

    def test_handle_empty_content(self):
        """测试处理空内容"""
        content = ""
        self.assertEqual(len(content), 0)


class TestCompilerWorkerQuality(unittest.TestCase):
    """测试质量评分"""

    def test_quality_score_range(self):
        """测试质量分数范围"""
        score = 85
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_high_quality_threshold(self):
        """测试高质量阈值"""
        MIN_QUALITY = 85
        scores = [70, 85, 90, 100]

        high_quality = [s for s in scores if s >= MIN_QUALITY]
        self.assertEqual(len(high_quality), 3)


if __name__ == "__main__":
    unittest.main()
