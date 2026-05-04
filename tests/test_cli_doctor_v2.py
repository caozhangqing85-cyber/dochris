"""测试 cli_doctor.py 补充分支 — 覆盖磁盘不足、配置错误、依赖缺失等路径"""

import argparse
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    """模拟完整工作区"""
    workspace = tmp_path / "kb"
    workspace.mkdir()

    for d in [
        "raw",
        "wiki/summaries",
        "wiki/concepts",
        "outputs/summaries",
        "outputs/concepts",
        "manifests/sources",
        "data",
        "logs",
    ]:
        (workspace / d).mkdir(parents=True)

    (workspace / ".env").write_text("OPENAI_API_KEY=test-key-123456\n", encoding="utf-8")

    monkeypatch.setenv("WORKSPACE", str(workspace))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123456")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.test.com")
    monkeypatch.setenv("MODEL", "test-model")

    return workspace


class TestCmdDoctorDiskSpace:
    """覆盖磁盘空间检查的所有分支"""

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.print")
    def test_very_low_disk_space_under_1gb(self, mock_print, mock_disk, mock_workspace):
        """磁盘 < 1GB 触发 error 分支"""
        from dochris.cli.cli_doctor import cmd_doctor

        m = MagicMock()
        m.total = 100 * (1024**3)
        m.used = 99.5 * (1024**3)
        m.free = 0.5 * (1024**3)  # 500MB < 1GB
        mock_disk.return_value = m

        result = cmd_doctor(argparse.Namespace())
        assert result == 1
        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "不足" in output

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.print")
    def test_low_disk_space_under_5gb(self, mock_print, mock_disk, mock_workspace):
        """磁盘 1-5GB 触发 warning 分支"""
        from dochris.cli.cli_doctor import cmd_doctor

        m = MagicMock()
        m.total = 100 * (1024**3)
        m.used = 96 * (1024**3)
        m.free = 3 * (1024**3)  # 3GB < 5GB
        mock_disk.return_value = m

        cmd_doctor(argparse.Namespace())
        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "偏低" in output

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.print")
    def test_disk_check_oserror(self, mock_print, mock_disk, mock_workspace):
        """磁盘检查 OSError 分支"""
        from dochris.cli.cli_doctor import cmd_doctor

        mock_disk.side_effect = OSError("permission denied")

        cmd_doctor(argparse.Namespace())
        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "无法检查" in output


class TestCmdDoctorConfigError:
    """覆盖 ConfigurationError 分支"""

    def test_config_error_returns_1(self, capsys, monkeypatch):
        """配置加载失败返回 1"""
        from dochris.cli.cli_doctor import cmd_doctor
        from dochris.exceptions import ConfigurationError

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("WORKSPACE", raising=False)

        with patch(
            "dochris.cli.cli_doctor.get_settings", side_effect=ConfigurationError("bad config")
        ):
            result = cmd_doctor(argparse.Namespace())

        assert result == 1


class TestCmdDoctorDependency:
    """覆盖核心依赖检查"""

    @patch("dochris.cli.cli_doctor.print")
    def test_missing_core_dependency(self, mock_print, mock_workspace):
        """缺少核心依赖触发 issues"""
        from dochris.cli.cli_doctor import cmd_doctor

        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("no openai")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            cmd_doctor(argparse.Namespace())

        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "openai" in output


class TestCmdDoctorSummaryBranches:
    """覆盖总结部分的各种 issue 分支"""

    @patch("dochris.cli.cli_doctor.print")
    def test_no_issues_all_pass(self, mock_print, mock_workspace):
        """所有检查通过返回 0"""
        from dochris.cli.cli_doctor import cmd_doctor

        with patch("dochris.cli.cli_doctor.shutil.disk_usage") as mock_disk:
            m = MagicMock()
            m.total = 500 * (1024**3)
            m.used = 50 * (1024**3)
            m.free = 450 * (1024**3)
            mock_disk.return_value = m

            result = cmd_doctor(argparse.Namespace())

        assert result == 0
