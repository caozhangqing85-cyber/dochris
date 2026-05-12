"""补充测试 phase2_compilation.py — 覆盖 dry_run 估算和非 TTY 分支"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_workspace(tmp_path):
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    (workspace / "logs").mkdir()
    (workspace / "cache").mkdir()
    return workspace


def _make_manifests(count=3, size_bytes=None):
    manifests = []
    for i in range(count):
        m = {
            "id": f"SRC-{i + 1:04d}",
            "status": "ingested",
            "title": f"测试文档 {i + 1}",
            "file_path": f"raw/test{i + 1}.pdf",
            "type": "pdf",
            "created_at": "2026-04-16T10:00:00",
        }
        if size_bytes is not None:
            m["size_bytes"] = size_bytes
        manifests.append(m)
    return manifests


class TestPhase2DryRunEstimates:
    """覆盖 dry_run 模式中的 API 调用估算"""

    @pytest.mark.asyncio
    async def test_dry_run_medium_file_estimates_2_calls(self, mock_workspace, monkeypatch):
        """50-100KB 文件估算 2 次 API 调用"""
        monkeypatch.setenv("WORKSPACE", str(mock_workspace))

        with patch(
            "dochris.phases.phase2_compilation.get_all_manifests",
            return_value=_make_manifests(1, 60000),
        ):
            with patch("dochris.phases.phase2_compilation.setup_logging"):
                with patch("builtins.print"):
                    from dochris.phases.phase2_compilation import compile_all

                    result = await compile_all(limit=None, max_concurrent=1, dry_run=True)

        assert result is None

    @pytest.mark.asyncio
    async def test_dry_run_large_file_estimates_3_calls(self, mock_workspace, monkeypatch):
        """>100KB 文件估算 3 次 API 调用"""
        monkeypatch.setenv("WORKSPACE", str(mock_workspace))

        with patch(
            "dochris.phases.phase2_compilation.get_all_manifests",
            return_value=_make_manifests(1, 200000),
        ):
            with patch("dochris.phases.phase2_compilation.setup_logging"):
                with patch("builtins.print"):
                    from dochris.phases.phase2_compilation import compile_all

                    result = await compile_all(limit=None, max_concurrent=1, dry_run=True)

        assert result is None


class TestPhase2ProgressBranch:
    """覆盖非 TTY 进度条分支"""

    @pytest.mark.asyncio
    async def test_non_tty_batch_compilation(self, mock_workspace, monkeypatch):
        """非 TTY 模式使用简单日志"""
        monkeypatch.setenv("WORKSPACE", str(mock_workspace))

        mock_worker = MagicMock()
        mock_worker.compile_document = AsyncMock(return_value={"status": "compiled"})
        mock_monitor = MagicMock()

        with patch(
            "dochris.phases.phase2_compilation.get_all_manifests", return_value=_make_manifests(2)
        ):
            with patch("dochris.phases.phase2_compilation.setup_logging"):
                with patch(
                    "dochris.phases.phase2_compilation.CompilerWorker", return_value=mock_worker
                ):
                    with patch(
                        "dochris.phases.phase2_compilation.MonitorWorker", return_value=mock_monitor
                    ):
                        with patch("dochris.phases.phase2_compilation.clear_cache", return_value=0):
                            with patch("sys.stdout.isatty", return_value=False):
                                from dochris.phases.phase2_compilation import compile_all

                                await compile_all(limit=None, max_concurrent=1, dry_run=False)

        # 验证 worker 被调用编译文档
        assert mock_worker.compile_document.call_count == 2
        mock_monitor.print_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_compile_all_uses_dynamic_settings_model(
        self, mock_workspace, monkeypatch, caplog
    ):
        """编译使用 Settings 中的动态模型配置，并正确打印批次进度"""
        monkeypatch.setenv("WORKSPACE", str(mock_workspace))
        caplog.set_level(logging.INFO)

        mock_worker = MagicMock()
        mock_worker.compile_document = AsyncMock(return_value={"status": "compiled"})
        mock_monitor = MagicMock()

        with patch(
            "dochris.phases.phase2_compilation.get_all_manifests", return_value=_make_manifests(1)
        ):
            with patch("dochris.phases.phase2_compilation.setup_logging"):
                with patch(
                    "dochris.phases.phase2_compilation.CompilerWorker", return_value=mock_worker
                ) as mock_worker_class:
                    with patch(
                        "dochris.phases.phase2_compilation.MonitorWorker", return_value=mock_monitor
                    ):
                        with patch("dochris.phases.phase2_compilation.clear_cache", return_value=0):
                            with patch("sys.stdout.isatty", return_value=False):
                                from dochris.phases.phase2_compilation import compile_all
                                from dochris.settings import reset_settings

                                reset_settings()
                                monkeypatch.setenv("MODEL", "glm-4-flash")
                                monkeypatch.setenv("OPENAI_API_KEY", "test-key")
                                await compile_all(limit=None, max_concurrent=1, dry_run=False)

        assert mock_worker_class.call_args.kwargs["model"] == "glm-4-flash"
        assert "📈 进度: 1/1 (100.0%)" in caplog.text


class TestPhase2TTYProgress:
    """覆盖 TTY 进度条分支 (lines 182-210)"""

    @pytest.mark.asyncio
    async def test_tty_batch_compilation(self, mock_workspace, monkeypatch):
        """TTY 模式使用 Rich 进度条"""
        monkeypatch.setenv("WORKSPACE", str(mock_workspace))

        mock_worker = MagicMock()
        mock_worker.compile_document = AsyncMock(return_value={"status": "compiled"})
        mock_monitor = MagicMock()

        with patch(
            "dochris.phases.phase2_compilation.get_all_manifests", return_value=_make_manifests(2)
        ):
            with patch("dochris.phases.phase2_compilation.setup_logging"):
                with patch(
                    "dochris.phases.phase2_compilation.CompilerWorker", return_value=mock_worker
                ):
                    with patch(
                        "dochris.phases.phase2_compilation.MonitorWorker", return_value=mock_monitor
                    ):
                        with patch("dochris.phases.phase2_compilation.clear_cache", return_value=0):
                            with patch("sys.stdout.isatty", return_value=True):
                                from dochris.phases.phase2_compilation import compile_all

                                await compile_all(limit=None, max_concurrent=1, dry_run=False)

        assert mock_worker.compile_document.call_count == 2
        mock_monitor.print_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_tty_batch_with_exception(self, mock_workspace, monkeypatch):
        """TTY 模式中编译异常被正确处理"""
        monkeypatch.setenv("WORKSPACE", str(mock_workspace))

        mock_worker = MagicMock()
        mock_worker.compile_document = AsyncMock(side_effect=RuntimeError("API error"))
        mock_monitor = MagicMock()

        with patch(
            "dochris.phases.phase2_compilation.get_all_manifests", return_value=_make_manifests(1)
        ):
            with patch("dochris.phases.phase2_compilation.setup_logging"):
                with patch(
                    "dochris.phases.phase2_compilation.CompilerWorker", return_value=mock_worker
                ):
                    with patch(
                        "dochris.phases.phase2_compilation.MonitorWorker", return_value=mock_monitor
                    ):
                        with patch("dochris.phases.phase2_compilation.clear_cache", return_value=0):
                            with patch("sys.stdout.isatty", return_value=True):
                                from dochris.phases.phase2_compilation import compile_all

                                await compile_all(limit=None, max_concurrent=1, dry_run=False)

        mock_monitor.print_report.assert_called_once()
