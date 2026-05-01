"""补充测试 cli/cli_doctor.py — 覆盖 optional deps ImportError (lines 160-161)"""

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


class TestCmdDoctorOptionalDeps:
    """覆盖 optional deps ImportError 分支 (lines 160-161)"""

    @patch("dochris.cli.cli_doctor.print")
    def test_optional_dep_import_error(self, mock_print, mock_workspace):
        """faster_whisper 未安装时走 ImportError 分支"""
        from dochris.cli.cli_doctor import cmd_doctor

        real_import = __import__

        def selective_import(name, *args, **kwargs):
            if name == "faster_whisper":
                raise ImportError("faster_whisper not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=selective_import):
            with patch("dochris.cli.cli_doctor.get_settings") as mock_s:
                mock_settings = MagicMock()
                mock_settings.api_key = "test-key-123456"
                mock_settings.workspace = mock_workspace
                mock_s.return_value = mock_settings
                with patch("dochris.cli.cli_doctor.shutil.disk_usage") as mock_disk:
                    from collections import namedtuple

                    DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
                    mock_disk.return_value = DiskUsage(
                        total=100 * 1024**3,
                        used=50 * 1024**3,
                        free=50 * 1024**3,
                    )
                    result = cmd_doctor(argparse.Namespace())

        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "未安装" in output
        assert isinstance(result, int)
