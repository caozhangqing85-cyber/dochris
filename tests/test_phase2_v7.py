"""
测试 phase2_compilation.py 模块
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def mock_workspace(tmp_path):
    """创建模拟工作区"""
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "manifests").mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    (workspace / "logs").mkdir()
    (workspace / "cache").mkdir()
    return workspace


@pytest.fixture
def sample_manifest(mock_workspace):
    """创建示例 manifest"""
    manifest = {
        "id": "SRC-0001",
        "status": "ingested",
        "title": "测试文档",
        "file_path": "raw/test.pdf",
        "type": "pdf",
        "created_at": "2026-04-16T10:00:00",
    }
    manifest_file = mock_workspace / "manifests" / "sources" / "SRC-0001.json"
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest


@pytest.fixture
def sample_manifests(mock_workspace):
    """创建多个示例 manifest"""
    manifests = []
    for i in range(5):
        manifest = {
            "id": f"SRC-{i+1:04d}",
            "status": "ingested",
            "title": f"测试文档 {i+1}",
            "file_path": f"raw/test{i}.pdf",
            "type": "pdf",
            "created_at": "2026-04-16T10:00:00",
        }
        manifest_file = mock_workspace / "manifests" / "sources" / f"SRC-{i+1:04d}.json"
        manifest_file.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        manifests.append(manifest)
    return manifests


@pytest.fixture
def mock_api_key(monkeypatch):
    """模拟 API 密钥"""
    api_key = "test-api-key-12345678"
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    return api_key


class TestPhase2V7SetupLogging:
    """测试日志设置功能"""

    @patch('dochris.phases.phase2_compilation.get_logs_dir')
    def test_setup_logging_creates_log_directory(self, mock_get_logs_dir, mock_workspace):
        """测试 setup_logging 创建日志目录"""
        from dochris.phases.phase2_compilation import setup_logging

        mock_get_logs_dir.return_value = mock_workspace / "logs"

        logger = setup_logging()

        assert logger is not None
        assert logger.name == "root"

    @patch('dochris.phases.phase2_compilation.get_logs_dir')
    def test_setup_logging_creates_log_file(self, mock_get_logs_dir, mock_workspace):
        """测试 setup_logging 创建日志文件"""
        from dochris.phases.phase2_compilation import setup_logging

        logs_dir = mock_workspace / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        mock_get_logs_dir.return_value = logs_dir

        setup_logging()

        # 验证日志文件被创建
        log_files = list(logs_dir.glob("phase2_*.log"))
        assert len(log_files) > 0


class TestPhase2V7CompileAll:
    """测试编译功能"""

    @pytest.mark.asyncio
    async def test_compile_all_with_no_manifests(self, mock_workspace, mock_api_key):
        """测试没有 manifest 时的编译"""
        from dochris.phases.phase2_compilation import compile_all

        # 不创建任何 manifest

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace):
            await compile_all(max_concurrent=1, limit=None, use_openrouter=False)
        # 应该不报错，直接返回

    @pytest.mark.asyncio
    async def test_compile_all_with_manifests(self, mock_workspace, sample_manifests, mock_api_key):
        """测试有 manifest 时的编译"""
        from dochris.phases.phase2_compilation import compile_all

        mock_worker = AsyncMock()
        mock_worker.compile_document.return_value = True

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker', return_value=mock_worker), \
             patch('dochris.phases.phase2_compilation.MonitorWorker') as mock_monitor_class:

            mock_monitor = MagicMock()
            mock_monitor_class.return_value = mock_monitor

            await compile_all(max_concurrent=1, limit=None, use_openrouter=False)

    @pytest.mark.asyncio
    async def test_compile_all_with_limit(self, mock_workspace, sample_manifests, mock_api_key):
        """测试限制编译数量"""
        from dochris.phases.phase2_compilation import compile_all

        mock_worker = AsyncMock()
        mock_worker.compile_document.return_value = True

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker', return_value=mock_worker), \
             patch('dochris.phases.phase2_compilation.MonitorWorker'):

            await compile_all(max_concurrent=1, limit=2, use_openrouter=False)

    @pytest.mark.asyncio
    async def test_compile_all_with_openrouter(self, mock_workspace, sample_manifests, mock_api_key):
        """测试使用 OpenRouter"""
        from dochris.phases.phase2_compilation import compile_all

        mock_worker = AsyncMock()
        mock_worker.compile_document.return_value = True

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker', return_value=mock_worker), \
             patch('dochris.phases.phase2_compilation.MonitorWorker'):

            await compile_all(max_concurrent=1, limit=None, use_openrouter=True)

    @pytest.mark.asyncio
    async def test_compile_all_concurrency(self, mock_workspace, sample_manifests, mock_api_key):
        """测试并发控制"""
        from dochris.phases.phase2_compilation import compile_all

        mock_worker = AsyncMock()
        mock_worker.compile_document.return_value = True

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker', return_value=mock_worker), \
             patch('dochris.phases.phase2_compilation.MonitorWorker'):

            await compile_all(max_concurrent=3, limit=None, use_openrouter=False)

    @pytest.mark.asyncio
    async def test_compile_all_handles_failures(self, mock_workspace, sample_manifests, mock_api_key):
        """测试处理编译失败"""
        from dochris.phases.phase2_compilation import compile_all

        mock_worker = AsyncMock()
        # 第一个成功，第二个失败
        mock_worker.compile_document.side_effect = [True, False, True, False, True]

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker', return_value=mock_worker), \
             patch('dochris.phases.phase2_compilation.MonitorWorker'):

            await compile_all(max_concurrent=1, limit=None, use_openrouter=False)


class TestPhase2V7Main:
    """测试主函数入口"""

    @patch('sys.argv', ['phase2_compilation.py', '--concurrency', '2', '--limit', '10'])
    @patch('dochris.phases.phase2_compilation.DEFAULT_API_KEY', 'test-key-12345')
    @patch('dochris.phases.phase2_compilation.setup_logging')
    @patch('dochris.phases.phase2_compilation.compile_all')
    def test_main_with_concurrency_and_limit(self, mock_compile, mock_logging):
        """测试带并发数和限制的主函数"""
        from dochris.phases.phase2_compilation import main

        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger
        mock_compile.return_value = None

        main()

        mock_compile.assert_called_once()

    @patch('sys.argv', ['phase2_compilation.py', '--openrouter'])
    @patch('dochris.phases.phase2_compilation.DEFAULT_API_KEY', 'test-key-12345')
    @patch('dochris.phases.phase2_compilation.setup_logging')
    @patch('dochris.phases.phase2_compilation.compile_all')
    def test_main_with_openrouter_flag(self, mock_compile, mock_logging):
        """测试使用 OpenRouter 标志的主函数"""
        from dochris.phases.phase2_compilation import main

        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger
        mock_compile.return_value = None

        main()

        # 验证调用参数
        call_kwargs = mock_compile.call_args[1]
        assert call_kwargs['use_openrouter'] is True

    @patch('sys.argv', ['phase2_compilation.py', '--clear-cache'])
    @patch('dochris.phases.phase2_compilation.setup_logging')
    @patch('dochris.phases.phase2_compilation.clear_cache')
    @patch('dochris.phases.phase2_compilation.cache_dir')
    @patch('dochris.phases.phase2_compilation.get_default_workspace')
    def test_main_clear_cache(self, mock_workspace, mock_cache_dir, mock_clear, mock_logging, monkeypatch):
        """测试清理缓存功能"""
        from dochris.phases.phase2_compilation import main

        # 使用 monkeypatch 设置环境变量
        monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")

        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger
        mock_clear.return_value = 5
        mock_workspace.return_value = Path("/tmp/test")
        mock_cache_dir.return_value = Path("/tmp/test/cache")

        main()

        mock_clear.assert_called_once()

    @patch('sys.argv', ['phase2_compilation.py'])
    @patch('dochris.phases.phase2_compilation.setup_logging')
    @patch('dochris.phases.phase2_compilation.compile_all')
    @patch('dochris.phases.phase2_compilation.DEFAULT_API_KEY', None)
    def test_main_without_api_key(self, mock_compile, mock_logging):
        """测试没有 API 密钥时的情况"""
        import sys

        from dochris.phases.phase2_compilation import main

        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger

        with patch.object(sys, 'exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(1)

    @patch('sys.argv', ['phase2_compilation.py', '--model', 'custom-model'])
    @patch('dochris.phases.phase2_compilation.DEFAULT_API_KEY', 'test-key-12345')
    @patch('dochris.phases.phase2_compilation.setup_logging')
    @patch('dochris.phases.phase2_compilation.compile_all')
    def test_main_with_custom_model(self, mock_compile, mock_logging):
        """测试自定义模型"""
        from dochris.phases.phase2_compilation import main

        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger
        mock_compile.return_value = None

        main()

        mock_compile.assert_called_once()

    @patch('sys.argv', ['phase2_compilation.py', '--api-base', 'https://custom.api/v1'])
    @patch('dochris.phases.phase2_compilation.DEFAULT_API_KEY', 'test-key-12345')
    @patch('dochris.phases.phase2_compilation.setup_logging')
    @patch('dochris.phases.phase2_compilation.compile_all')
    def test_main_with_custom_api_base(self, mock_compile, mock_logging):
        """测试自定义 API 基础 URL"""
        from dochris.phases.phase2_compilation import main

        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger
        mock_compile.return_value = None

        main()

        mock_compile.assert_called_once()


class TestPhase2V7BatchProcessing:
    """测试批处理功能"""

    @pytest.mark.asyncio
    async def test_batch_size_handling(self, mock_workspace, mock_api_key):
        """测试批处理大小"""
        from dochris.phases.phase2_compilation import compile_all

        # 创建 60 个 manifest (超过默认批大小)
        for i in range(60):
            manifest = {
                "id": f"SRC-{i+1:04d}",
                "status": "ingested",
                "title": f"测试文档 {i+1}",
                "file_path": f"raw/test{i}.pdf",
                "type": "pdf",
            }
            manifest_file = mock_workspace / "manifests" / "sources" / f"SRC-{i+1:04d}.json"
            manifest_file.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        mock_worker = AsyncMock()
        mock_worker.compile_document.return_value = True

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker', return_value=mock_worker), \
             patch('dochris.phases.phase2_compilation.MonitorWorker'):

            await compile_all(max_concurrent=1, limit=None, use_openrouter=False)

            # 验证所有文件都被处理
            assert mock_worker.compile_document.call_count == 60


class TestPhase2V7Reporting:
    """测试报告功能"""

    @pytest.mark.asyncio
    async def test_progress_reporting(self, mock_workspace, sample_manifests, mock_api_key):
        """测试进度报告"""
        from dochris.phases.phase2_compilation import compile_all

        mock_worker = AsyncMock()
        mock_worker.compile_document.return_value = True

        mock_monitor = MagicMock()
        mock_monitor.print_report = MagicMock()

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker', return_value=mock_worker), \
             patch('dochris.phases.phase2_compilation.MonitorWorker', return_value=mock_monitor), \
             patch('dochris.phases.phase2_compilation.clear_cache', return_value=0):

            await compile_all(max_concurrent=1, limit=None, use_openrouter=False)

            # 验证报告被打印
            mock_monitor.print_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_final_statistics(self, mock_workspace, sample_manifests, mock_api_key):
        """测试最终统计"""
        from dochris.phases.phase2_compilation import compile_all

        mock_worker = AsyncMock()
        mock_worker.compile_document.return_value = True

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker', return_value=mock_worker), \
             patch('dochris.phases.phase2_compilation.MonitorWorker'), \
             patch('dochris.phases.phase2_compilation.clear_cache', return_value=0):

            await compile_all(max_concurrent=1, limit=None, use_openrouter=False)


class TestPhase2V7ErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_handles_exception_in_compile(self, mock_workspace, sample_manifests, mock_api_key):
        """测试处理编译中的异常"""
        from dochris.phases.phase2_compilation import compile_all

        mock_worker = AsyncMock()
        mock_worker.compile_document.side_effect = Exception("测试异常")

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker', return_value=mock_worker), \
             patch('dochris.phases.phase2_compilation.MonitorWorker'), \
             patch('dochris.phases.phase2_compilation.clear_cache', return_value=0):

            # 应该不抛出异常
            await compile_all(max_concurrent=1, limit=None, use_openrouter=False)

    @pytest.mark.asyncio
    async def test_handles_manifest_read_errors(self, mock_workspace, mock_api_key):
        """测试处理 manifest 读取错误"""
        from dochris.phases.phase2_compilation import compile_all

        # 创建一个无效的 JSON 文件
        invalid_file = mock_workspace / "manifests" / "sources" / "SRC-0001.json"
        invalid_file.write_text("{ invalid json", encoding="utf-8")

        with patch('dochris.phases.phase2_compilation.get_default_workspace', return_value=mock_workspace), \
             patch('dochris.phases.phase2_compilation.CompilerWorker'), \
             patch('dochris.phases.phase2_compilation.MonitorWorker'), \
             patch('dochris.phases.phase2_compilation.clear_cache', return_value=0):

            # 应该不抛出异常
            await compile_all(max_concurrent=1, limit=None, use_openrouter=False)
