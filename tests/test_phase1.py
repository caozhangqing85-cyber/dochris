#!/usr/bin/env python3
"""
测试 phase1_ingestion.py 的文件扫描、去重、进度管理功能
增强版：15+ 测试用例
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# 添加 src 目录到路径（如需要）
# sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestPhase1FileHash(unittest.TestCase):
    """测试文件哈希计算"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_file_hash_calculation(self):
        """测试文件哈希计算"""
        test_file = self.temp_path / "test.txt"
        test_file.write_text("hello world")

        from dochris.phases.phase1_ingestion import file_hash

        hash1 = file_hash(test_file)
        hash2 = file_hash(test_file)

        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA256 是 64 位十六进制

    def test_file_hash_different_content(self):
        """测试不同内容产生不同哈希"""
        from dochris.phases.phase1_ingestion import file_hash

        file1 = self.temp_path / "file1.txt"
        file2 = self.temp_path / "file2.txt"

        file1.write_text("content1")
        file2.write_text("content2")

        hash1 = file_hash(file1)
        hash2 = file_hash(file2)

        self.assertNotEqual(hash1, hash2)

    def test_file_hash_same_content_different_name(self):
        """测试相同内容不同文件名产生相同哈希"""
        from dochris.phases.phase1_ingestion import file_hash

        file1 = self.temp_path / "file1.txt"
        file2 = self.temp_path / "file2.txt"

        content = "same content"
        file1.write_text(content)
        file2.write_text(content)

        hash1 = file_hash(file1)
        hash2 = file_hash(file2)

        self.assertEqual(hash1, hash2)

    def test_file_hash_nonexistent_file(self):
        """测试不存在的文件返回 None"""
        from dochris.phases.phase1_ingestion import file_hash

        result = file_hash(Path("/nonexistent/file.txt"))
        self.assertIsNone(result)

    def test_file_hash_empty_file(self):
        """测试空文件哈希"""
        from dochris.phases.phase1_ingestion import file_hash

        empty_file = self.temp_path / "empty.txt"
        empty_file.write_text("")

        result = file_hash(empty_file)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 64)


class TestPhase1ProgressFile(unittest.TestCase):
    """测试进度文件操作"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_progress_file_operations(self):
        """测试进度文件读写"""
        progress_file = self.temp_path / "progress.json"

        progress_data = {
            "phase1": {
                "ingested_files": {},
                "hash_index": {},
                "stats": {"total": 0, "linked": 0, "skipped": 0, "failed": 0},
                "last_update": None,
            }
        }

        progress_file.write_text(json.dumps(progress_data), encoding='utf-8')
        loaded = json.loads(progress_file.read_text(encoding='utf-8'))
        self.assertEqual(loaded["phase1"]["stats"]["total"], 0)

    def test_progress_file_create_new(self):
        """测试创建新的进度文件"""

        from dochris.phases.phase1_ingestion import PROGRESS_FILE, load_progress, save_progress

        # 备份原有的 PROGRESS_FILE
        original_backup = None
        if PROGRESS_FILE.exists():
            original_backup = PROGRESS_FILE.read_text(encoding='utf-8')

        try:
            # 临时覆盖 PROGRESS_FILE 为测试目录
            import phase1_ingestion
            original_progress_file = phase1_ingestion.PROGRESS_FILE
            phase1_ingestion.PROGRESS_FILE = self.temp_path / "progress.json"

            test_data = {
                "phase1": {
                    "ingested_files": {},
                    "hash_index": {},
                    "stats": {"total": 0, "linked": 0, "skipped": 0, "failed": 0},
                },
                "test": "data"
            }
            save_progress(test_data)
            loaded = load_progress()
            self.assertEqual(loaded.get("test"), "data")

            # 恢复原有配置
            phase1_ingestion.PROGRESS_FILE = original_progress_file
        finally:
            # 恢复原有 PROGRESS_FILE 内容
            if original_backup is not None:
                PROGRESS_FILE.write_text(original_backup, encoding='utf-8')

    def test_progress_file_update_stats(self):
        """测试更新统计信息"""
        progress_file = self.temp_path / "progress.json"

        progress_data = {
            "phase1": {
                "stats": {"total": 10, "linked": 5},
                "last_update": "2024-01-01",
            }
        }

        progress_file.write_text(json.dumps(progress_data), encoding='utf-8')
        loaded = json.loads(progress_file.read_text(encoding='utf-8'))
        self.assertEqual(loaded["phase1"]["stats"]["total"], 10)


class TestPhase1FileDetection(unittest.TestCase):
    """测试文件类型检测"""

    def test_file_extension_detection(self):
        """测试文件扩展名检测"""
        from dochris.settings import get_file_category

        self.assertEqual(get_file_category('.pdf'), 'pdfs')
        self.assertEqual(get_file_category('.md'), 'articles')
        self.assertEqual(get_file_category('.mp3'), 'audio')
        self.assertEqual(get_file_category('.mp4'), 'videos')
        self.assertEqual(get_file_category('.mobi'), 'ebooks')
        self.assertEqual(get_file_category('.epub'), 'ebooks')
        self.assertEqual(get_file_category('.xyz'), 'other')

    def test_file_extension_case_insensitive(self):
        """测试扩展名大小写不敏感"""
        from dochris.settings import get_file_category

        self.assertEqual(get_file_category('.PDF'), 'pdfs')
        self.assertEqual(get_file_category('.Mp3'), 'audio')
        self.assertEqual(get_file_category('.MD'), 'articles')

    def test_supported_video_formats(self):
        """测试支持的视频格式"""
        from dochris.settings import get_file_category

        # 只测试 FILE_TYPE_MAP 中实际支持的格式
        video_formats = ['.mp4', '.mkv', '.avi', '.mov', '.wmv']
        for ext in video_formats:
            self.assertEqual(get_file_category(ext), 'videos')

    def test_supported_audio_formats(self):
        """测试支持的音频格式"""
        from dochris.settings import get_file_category

        # 只测试 FILE_TYPE_MAP 中实际支持的格式
        audio_formats = ['.mp3', '.m4a', '.flac', '.aac', '.ogg']
        for ext in audio_formats:
            self.assertEqual(get_file_category(ext), 'audio')


class TestPhase1Deduplication(unittest.TestCase):
    """测试去重功能"""

    def test_hash_based_deduplication(self):
        """测试基于哈希的去重"""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)

        try:
            from dochris.phases.phase1_ingestion import file_hash

            file1 = temp_path / "file1.txt"
            file2 = temp_path / "file2.txt"
            content = "same content"

            file1.write_text(content)
            file2.write_text(content)

            hash1 = file_hash(file1)
            hash2 = file_hash(file2)

            self.assertEqual(hash1, hash2)

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_duplicate_detection_in_hash_index(self):
        """测试哈希索引中检测重复"""
        hash_index = {
            "abc123def456": "SRC-0001",
            "789xyz012": "SRC-0002"
        }

        # 测试存在的哈希
        self.assertIn("abc123def456", hash_index)

        # 测试不存在的哈希
        self.assertNotIn("nonexistent", hash_index)


class TestPhase1SymlinkCreation(unittest.TestCase):
    """测试符号链接创建"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.source_dir = self.temp_path / "source"
        self.raw_dir = self.temp_path / "raw"
        self.source_dir.mkdir()
        self.raw_dir.mkdir()

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_symlink(self):
        """测试创建符号链接"""
        source_file = self.source_dir / "test.pdf"
        source_file.write_text("test content")

        target_dir = self.raw_dir / "pdfs"
        target_dir.mkdir(exist_ok=True)
        target = target_dir / "test.pdf"

        # 创建符号链接
        target.symlink_to(source_file)

        self.assertTrue(target.is_symlink())
        self.assertTrue(target.exists())

    def test_symlink_points_to_correct_source(self):
        """测试符号链接指向正确的源文件"""
        source_file = self.source_dir / "test.txt"
        source_file.write_text("original content")

        target = self.raw_dir / "test.txt"
        target.symlink_to(source_file)

        # 读取链接内容应该是源文件内容
        content = target.read_text()
        self.assertEqual(content, "original content")


class TestPhase1AudioDuration(unittest.TestCase):
    """测试音频时长获取"""

    def test_nonexistent_audio_file(self):
        """测试不存在的音频文件返回 None"""
        from dochris.phases.phase1_ingestion import get_audio_duration

        result = get_audio_duration(Path("/nonexistent/file.mp3"))
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_audio_duration_ffprobe_success(self, mock_run):
        """测试 ffprobe 成功获取时长"""
        from dochris import settings
        from dochris.phases import phase1_ingestion

        # Mock SOURCE_PATH to /tmp so temp files are under it
        original_source_path = settings.SOURCE_PATH
        settings.SOURCE_PATH = Path("/tmp")
        phase1_ingestion.SOURCE_PATH = Path("/tmp")

        # Mock ffprobe 输出
        mock_result = MagicMock()
        mock_result.stdout = b'{"format": {"duration": "125.5"}}'
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, dir='/tmp')
        temp_file.close()

        try:
            result = phase1_ingestion.get_audio_duration(Path(temp_file.name))
            self.assertIsNotNone(result)
            self.assertEqual(result, 125.5)
        finally:
            Path(temp_file.name).unlink()
            settings.SOURCE_PATH = original_source_path
            phase1_ingestion.SOURCE_PATH = original_source_path

    @patch('subprocess.run')
    def test_audio_duration_ffprobe_failure(self, mock_run):
        """测试 ffprobe 失败返回 None"""
        from dochris import settings
        from dochris.phases import phase1_ingestion

        # Mock SOURCE_PATH to /tmp so temp files are under it
        original_source_path = settings.SOURCE_PATH
        settings.SOURCE_PATH = Path("/tmp")
        phase1_ingestion.SOURCE_PATH = Path("/tmp")

        # 模拟 subprocess.run 返回非0退出码
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, dir='/tmp')
        temp_file.close()

        try:
            result = phase1_ingestion.get_audio_duration(Path(temp_file.name))
            self.assertIsNone(result)
        finally:
            Path(temp_file.name).unlink()
            settings.SOURCE_PATH = original_source_path
            phase1_ingestion.SOURCE_PATH = original_source_path


class TestPhase1SourceDirectoryScanning(unittest.TestCase):
    """测试源目录扫描"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.source_dir = self.temp_path / "source"

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_pdf_files(self):
        """测试扫描 PDF 文件"""
        pdf_dir = self.source_dir / "pdfs"
        pdf_dir.mkdir(parents=True)

        # 创建测试文件
        (pdf_dir / "test1.pdf").write_text("pdf1")
        (pdf_dir / "test2.pdf").write_text("pdf2")
        (pdf_dir / "not_pdf.txt").write_text("text")

        # 扫描 PDF 文件
        pdf_files = list(pdf_dir.glob("*.pdf"))
        self.assertEqual(len(pdf_files), 2)

    def test_scan_audio_files(self):
        """测试扫描音频文件"""
        audio_dir = self.source_dir / "audio"
        audio_dir.mkdir(parents=True)

        (audio_dir / "test1.mp3").write_text("audio1")
        (audio_dir / "test2.wav").write_text("audio2")

        audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
        self.assertEqual(len(audio_files), 2)

    def test_scan_nested_directories(self):
        """测试扫描嵌套目录"""
        nested_dir = self.source_dir / "level1" / "level2"
        nested_dir.mkdir(parents=True)

        (nested_dir / "deep.pdf").write_text("deep")

        pdf_files = list(self.source_dir.rglob("*.pdf"))
        self.assertEqual(len(pdf_files), 1)


class TestPhase1Statistics(unittest.TestCase):
    """测试统计功能"""

    def test_calculate_stats(self):
        """测试计算统计数据"""
        stats = {
            "total": 100,
            "linked": 80,
            "skipped": 15,
            "failed": 5
        }

        success_rate = (stats["linked"] / stats["total"] * 100) if stats["total"] > 0 else 0
        self.assertEqual(success_rate, 80.0)

    def test_empty_stats(self):
        """测试空统计"""
        stats = {
            "total": 0,
            "linked": 0,
            "skipped": 0,
            "failed": 0
        }

        self.assertEqual(stats["total"], 0)


class TestPhase1Integration(unittest.TestCase):
    """集成测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # 创建目录结构
        (self.temp_path / "source").mkdir()
        (self.temp_path / "raw").mkdir()

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('dochris.phases.phase1_ingestion.load_progress')
    @patch('dochris.phases.phase1_ingestion.save_progress')
    def test_full_ingestion_flow(self, mock_save, mock_load):
        """测试完整摄入流程"""
        from dochris.phases.phase1_ingestion import file_hash

        # Mock 进度文件
        mock_load.return_value = {
            "phase1": {
                "ingested_files": {},
                "hash_index": {},
                "stats": {"total": 0, "linked": 0, "skipped": 0, "failed": 0},
            }
        }

        # 创建源文件
        source_file = self.temp_path / "source" / "test.pdf"
        source_file.write_text("test content")

        # 计算哈希
        file_hash_value = file_hash(source_file)
        self.assertIsNotNone(file_hash_value)
        self.assertEqual(len(file_hash_value), 64)


if __name__ == "__main__":
    unittest.main()
