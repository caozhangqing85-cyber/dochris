"""
测试 recompile.py 模块（统一的重新编译入口）
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
    return workspace


@pytest.fixture
def sample_failed_manifests(mock_workspace):
    """创建示例失败 manifests"""
    manifests_data = [
        {
            "id": "SRC-0001",
            "status": "failed",
            "title": "LLM 失败文档",
            "file_path": "raw/test1.pdf",
            "error_message": "llm_failed",
            "type": "pdf",
        },
        {
            "id": "SRC-0002",
            "status": "failed",
            "title": "无文本文档",
            "file_path": "raw/test2.pdf",
            "error_message": "no_text",
            "type": "pdf",
        },
        {
            "id": "SRC-0003",
            "status": "failed",
            "title": "连接失败文档",
            "file_path": "raw/test3.pdf",
            "error_message": "Connection error",
            "type": "article",
        },
        {
            "id": "SRC-0004",
            "status": "failed",
            "title": "超时文档",
            "file_path": "raw/test4.pdf",
            "error_message": "timeout",
            "type": "ebook",
        },
    ]

    for manifest in manifests_data:
        manifest_file = mock_workspace / "manifests" / "sources" / f"{manifest['id']}.json"
        manifest_file.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    return manifests_data


@pytest.fixture
def mock_settings(mock_workspace, monkeypatch):
    """模拟设置"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key-12345")
    return mock_workspace


class TestGetRecoverableFailedDocs:
    """测试获取可恢复失败文档功能"""

    @patch("dochris.admin.recompile.get_all_manifests")
    @patch("dochris.admin.recompile.get_settings")
    def test_get_recoverable_filters_all_mode(
        self, mock_get_settings, mock_get_all, sample_failed_manifests, mock_workspace
    ):
        """测试 all 模式正确过滤"""
        from dochris.admin.recompile import get_recoverable_failed_docs

        mock_settings = MagicMock()
        mock_settings.workspace = mock_workspace
        mock_get_settings.return_value = mock_settings
        mock_get_all.return_value = sample_failed_manifests

        recoverable = get_recoverable_failed_docs(mock_workspace, mode="all")

        # 所有四个都是可恢复的
        assert len(recoverable) == 4

    @patch("dochris.admin.recompile.get_all_manifests")
    @patch("dochris.admin.recompile.get_settings")
    def test_get_recoverable_filters_llm_failed_mode(
        self, mock_get_settings, mock_get_all, sample_failed_manifests, mock_workspace
    ):
        """测试 llm_failed 模式"""
        from dochris.admin.recompile import get_recoverable_failed_docs

        mock_settings = MagicMock()
        mock_settings.workspace = mock_workspace
        mock_get_settings.return_value = mock_settings
        mock_get_all.return_value = sample_failed_manifests

        recoverable = get_recoverable_failed_docs(mock_workspace, mode="llm_failed")

        # 只有 llm_failed
        assert len(recoverable) == 1
        assert recoverable[0]["id"] == "SRC-0001"

    @patch("dochris.admin.recompile.get_all_manifests")
    @patch("dochris.admin.recompile.get_settings")
    def test_get_recoverable_filters_text_mode(
        self, mock_get_settings, mock_get_all, sample_failed_manifests, mock_workspace
    ):
        """测试 text 模式"""
        from dochris.admin.recompile import get_recoverable_failed_docs

        mock_settings = MagicMock()
        mock_settings.workspace = mock_workspace
        mock_get_settings.return_value = mock_settings
        mock_get_all.return_value = sample_failed_manifests

        recoverable = get_recoverable_failed_docs(mock_workspace, mode="text")

        # pdf, article, ebook 都是文本类型（排除 no_text 的 pdf）
        assert len(recoverable) == 3

    @patch("dochris.admin.recompile.get_all_manifests")
    @patch("dochris.admin.recompile.get_settings")
    def test_get_recoverable_custom_error_filter(
        self, mock_get_settings, mock_get_all, sample_failed_manifests, mock_workspace
    ):
        """测试自定义错误过滤"""
        from dochris.admin.recompile import get_recoverable_failed_docs

        mock_settings = MagicMock()
        mock_settings.workspace = mock_workspace
        mock_get_settings.return_value = mock_settings
        mock_get_all.return_value = sample_failed_manifests

        recoverable = get_recoverable_failed_docs(
            mock_workspace, mode="custom", error_filter="timeout"
        )

        # 只有 timeout
        assert len(recoverable) == 1
        assert recoverable[0]["id"] == "SRC-0004"


class TestRecompileFunction:
    """测试重新编译功能"""

    @pytest.mark.asyncio
    async def test_recompile_with_limit(
        self, sample_failed_manifests, mock_workspace, mock_settings
    ):
        """测试限制重编译数量"""
        from dochris.admin.recompile import recompile

        mock_worker = AsyncMock()
        mock_worker.compile_document.return_value = True

        with (
            patch("dochris.admin.recompile.get_settings") as mock_get_settings,
            patch(
                "dochris.admin.recompile.get_all_manifests", return_value=sample_failed_manifests
            ),
            patch("dochris.admin.recompile.CompilerWorker", return_value=mock_worker),
        ):
            mock_settings_obj = MagicMock()
            mock_settings_obj.workspace = mock_workspace
            mock_settings_obj.api_key = "test-key"
            mock_settings_obj.api_base = "https://api.test"
            mock_settings_obj.model = "test-model"
            mock_settings_obj.batch_size = 10
            mock_get_settings.return_value = mock_settings_obj

            await recompile(mode="all", error_filter=None, max_concurrent=1, limit=2)

    @pytest.mark.asyncio
    async def test_recompile_no_docs(self, mock_workspace, mock_settings):
        """测试没有可恢复文档"""
        from dochris.admin.recompile import recompile

        with (
            patch("dochris.admin.recompile.get_settings") as mock_get_settings,
            patch("dochris.admin.recompile.get_all_manifests", return_value=[]),
        ):
            mock_settings_obj = MagicMock()
            mock_settings_obj.workspace = mock_workspace
            mock_settings_obj.api_key = "test-key"
            mock_get_settings.return_value = mock_settings_obj

            await recompile(mode="all", error_filter=None, max_concurrent=1, limit=None)

    @pytest.mark.asyncio
    async def test_recompile_handles_exceptions(
        self, sample_failed_manifests, mock_workspace, mock_settings
    ):
        """测试处理异常"""
        from dochris.admin.recompile import recompile

        mock_worker = AsyncMock()
        mock_worker.compile_document.side_effect = Exception("测试异常")

        with (
            patch("dochris.admin.recompile.get_settings") as mock_get_settings,
            patch(
                "dochris.admin.recompile.get_all_manifests", return_value=sample_failed_manifests
            ),
            patch("dochris.admin.recompile.CompilerWorker", return_value=mock_worker),
        ):
            mock_settings_obj = MagicMock()
            mock_settings_obj.workspace = mock_workspace
            mock_settings_obj.api_key = "test-key"
            mock_settings_obj.api_base = "https://api.test"
            mock_settings_obj.model = "test-model"
            mock_settings_obj.batch_size = 10
            mock_get_settings.return_value = mock_settings_obj

            # 应该不抛出异常
            await recompile(mode="all", error_filter=None, max_concurrent=1, limit=None)


class TestRecompileCLI:
    """测试命令行接口"""

    @patch("sys.argv", ["recompile.py", "--mode", "all", "--concurrency", "4", "--limit", "10"])
    @patch("dochris.admin.recompile.setup_logging")
    @patch("dochris.admin.recompile.recompile")
    def test_main_with_args(self, mock_recompile, mock_logging):
        """测试带参数的主函数"""
        from dochris.admin.recompile import main

        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger

        main()

        mock_recompile.assert_called_once()

    @patch("sys.argv", ["recompile.py", "--mode", "llm_failed"])
    @patch("dochris.admin.recompile.setup_logging")
    @patch("dochris.admin.recompile.recompile")
    def test_main_with_llm_failed_mode(self, mock_recompile, mock_logging):
        """测试 llm_failed 模式"""
        from dochris.admin.recompile import main

        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger

        main()

        call_kwargs = mock_recompile.call_args[1]
        assert call_kwargs["mode"] == "llm_failed"

    @patch("sys.argv", ["recompile.py", "--error", "timeout"])
    @patch("dochris.admin.recompile.setup_logging")
    @patch("dochris.admin.recompile.recompile")
    def test_main_with_custom_error(self, mock_recompile, mock_logging):
        """测试自定义错误过滤"""
        from dochris.admin.recompile import main

        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger

        main()

        call_kwargs = mock_recompile.call_args[1]
        assert call_kwargs["mode"] == "custom"
        assert call_kwargs["error_filter"] == "timeout"
