"""测试 cli/cli_ingest.py 模块"""

import argparse
from unittest.mock import MagicMock, patch


class TestCmdIngest:
    """测试 cmd_ingest 函数"""

    def _make_args(self, dry_run=False):
        """构造 argparse.Namespace"""
        return argparse.Namespace(dry_run=dry_run)

    def _mock_stats(self):
        return {"total": 10, "linked": 3, "skipped": 7}

    @patch("dochris.cli.cli_ingest.print")
    @patch(
        "dochris.phases.phase1_ingestion.run_phase1",
        return_value={"total": 10, "linked": 3, "skipped": 7},
    )
    @patch("dochris.phases.phase1_ingestion.setup_logging", return_value=MagicMock())
    def test_ingest_success(self, mock_setup, mock_run, mock_print):
        """正常摄入返回 0"""
        from dochris.cli.cli_ingest import cmd_ingest

        args = self._make_args()
        result = cmd_ingest(args)
        assert result == 0
        mock_run.assert_called_once()

    @patch("dochris.cli.cli_ingest.print")
    @patch(
        "dochris.phases.phase1_ingestion.run_phase1",
        return_value={"total": 5, "linked": 5, "skipped": 0},
    )
    @patch("dochris.phases.phase1_ingestion.setup_logging", return_value=MagicMock())
    def test_ingest_dry_run(self, mock_setup, mock_run, mock_print):
        """dry-run 模式"""
        from dochris.cli.cli_ingest import cmd_ingest

        args = self._make_args(dry_run=True)
        result = cmd_ingest(args)
        assert result == 0
        _, kwargs = mock_run.call_args
        assert kwargs["dry_run"] is True

    @patch("dochris.cli.cli_ingest.print")
    @patch(
        "dochris.phases.phase1_ingestion.run_phase1",
        side_effect=FileNotFoundError("source dir not found"),
    )
    @patch("dochris.phases.phase1_ingestion.setup_logging", return_value=MagicMock())
    def test_ingest_failure_returns_1(self, mock_setup, mock_run, mock_print):
        """摄入异常返回 1"""
        from dochris.cli.cli_ingest import cmd_ingest

        args = self._make_args()
        result = cmd_ingest(args)
        assert result == 1

    @patch("dochris.cli.cli_ingest.print")
    @patch(
        "dochris.phases.phase1_ingestion.run_phase1",
        side_effect=PermissionError("no access"),
    )
    @patch("dochris.phases.phase1_ingestion.setup_logging", return_value=MagicMock())
    def test_ingest_permission_error(self, mock_setup, mock_run, mock_print):
        """权限错误返回 1"""
        from dochris.cli.cli_ingest import cmd_ingest

        args = self._make_args()
        result = cmd_ingest(args)
        assert result == 1

    @patch("dochris.cli.cli_ingest.print")
    @patch(
        "dochris.phases.phase1_ingestion.run_phase1",
        return_value={"total": 0, "linked": 0, "skipped": 0},
    )
    @patch("dochris.phases.phase1_ingestion.setup_logging", return_value=MagicMock())
    def test_ingest_empty_stats(self, mock_setup, mock_run, mock_print):
        """空统计"""
        from dochris.cli.cli_ingest import cmd_ingest

        args = self._make_args()
        result = cmd_ingest(args)
        assert result == 0
