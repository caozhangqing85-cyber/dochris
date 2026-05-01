"""覆盖率提升 v12 — cli/cli_doctor.py + cli/cli_init.py"""

import argparse
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# cli/cli_doctor.py
# ============================================================
class TestCmdDoctor:
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_config_error(self, mock_settings, tmp_path):
        from dochris.cli.cli_doctor import cmd_doctor
        from dochris.exceptions import ConfigurationError

        mock_settings.side_effect = ConfigurationError("bad config")
        args = argparse.Namespace()
        assert cmd_doctor(args) == 1

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_all_pass(self, mock_settings, mock_disk, tmp_path):
        from dochris.cli.cli_doctor import cmd_doctor

        s = MagicMock()
        s.api_key = "sk-test-api-key-123456"
        s.api_base = "https://api.example.com/v1"
        s.model = "glm-5.1"
        s.workspace = tmp_path
        # Create required subdirectories
        for d in ["raw", "wiki/summaries", "wiki/concepts", "outputs/summaries",
                   "outputs/concepts", "manifests/sources", "data", "logs"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        mock_settings.return_value = s
        mock_disk.return_value = MagicMock(free=10 * 1024**3, total=100 * 1024**3, used=90 * 1024**3)

        args = argparse.Namespace()
        result = cmd_doctor(args)
        assert result == 0

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_no_api_key(self, mock_settings, mock_disk, tmp_path):
        from dochris.cli.cli_doctor import cmd_doctor

        s = MagicMock()
        s.api_key = None
        s.api_base = "https://api.example.com/v1"
        s.model = "glm-5.1"
        s.workspace = tmp_path
        mock_settings.return_value = s
        mock_disk.return_value = MagicMock(free=10 * 1024**3, total=100 * 1024**3, used=90 * 1024**3)

        args = argparse.Namespace()
        result = cmd_doctor(args)
        assert result == 1  # has issues

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_workspace_not_exists(self, mock_settings, mock_disk, tmp_path):
        from dochris.cli.cli_doctor import cmd_doctor

        s = MagicMock()
        s.api_key = "sk-test-key-123456"
        s.api_base = "https://api.example.com/v1"
        s.model = "glm-5.1"
        s.workspace = tmp_path / "nonexistent"
        mock_settings.return_value = s
        mock_disk.return_value = MagicMock(free=10 * 1024**3, total=100 * 1024**3, used=90 * 1024**3)

        args = argparse.Namespace()
        result = cmd_doctor(args)
        assert result == 1

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_low_disk_space(self, mock_settings, mock_disk, tmp_path):
        from dochris.cli.cli_doctor import cmd_doctor

        s = MagicMock()
        s.api_key = "sk-test-key-123456"
        s.api_base = "https://api.example.com/v1"
        s.model = "glm-5.1"
        s.workspace = tmp_path
        for d in ["raw", "wiki/summaries", "wiki/concepts", "outputs/summaries",
                   "outputs/concepts", "manifests/sources", "data", "logs"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        mock_settings.return_value = s
        mock_disk.return_value = MagicMock(free=500 * 1024**2, total=100 * 1024**3, used=100 * 1024**3)

        args = argparse.Namespace()
        result = cmd_doctor(args)
        assert result == 1  # disk space issue

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_missing_dirs(self, mock_settings, mock_disk, tmp_path):
        from dochris.cli.cli_doctor import cmd_doctor

        s = MagicMock()
        s.api_key = "sk-test-key-123456"
        s.api_base = "https://api.example.com/v1"
        s.model = "glm-5.1"
        s.workspace = tmp_path
        tmp_path.mkdir(parents=True, exist_ok=True)
        mock_settings.return_value = s
        mock_disk.return_value = MagicMock(free=10 * 1024**3, total=100 * 1024**3, used=90 * 1024**3)

        args = argparse.Namespace()
        result = cmd_doctor(args)
        assert result == 0  # missing dirs are warnings only, not errors

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_disk_oserror(self, mock_settings, mock_disk, tmp_path):
        from dochris.cli.cli_doctor import cmd_doctor

        s = MagicMock()
        s.api_key = "sk-test-key-123456"
        s.api_base = "https://api.example.com/v1"
        s.model = "glm-5.1"
        s.workspace = tmp_path
        for d in ["raw", "wiki/summaries", "wiki/concepts", "outputs/summaries",
                   "outputs/concepts", "manifests/sources", "data", "logs"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        mock_settings.return_value = s
        mock_disk.side_effect = OSError("cannot check")

        args = argparse.Namespace()
        result = cmd_doctor(args)
        assert result == 0

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_no_base_url(self, mock_settings, mock_disk, tmp_path):
        from dochris.cli.cli_doctor import cmd_doctor

        s = MagicMock()
        s.api_key = "sk-test-key-123456"
        s.api_base = ""
        s.model = "glm-5.1"
        s.workspace = tmp_path
        for d in ["raw", "wiki/summaries", "wiki/concepts", "outputs/summaries",
                   "outputs/concepts", "manifests/sources", "data", "logs"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        mock_settings.return_value = s
        mock_disk.return_value = MagicMock(free=10 * 1024**3, total=100 * 1024**3, used=90 * 1024**3)

        args = argparse.Namespace()
        result = cmd_doctor(args)
        assert result == 0  # missing base_url is just a warning

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_no_model(self, mock_settings, mock_disk, tmp_path):
        from dochris.cli.cli_doctor import cmd_doctor

        s = MagicMock()
        s.api_key = "sk-test-key-123456"
        s.api_base = "https://api.example.com/v1"
        s.model = ""
        s.workspace = tmp_path
        for d in ["raw", "wiki/summaries", "wiki/concepts", "outputs/summaries",
                   "outputs/concepts", "manifests/sources", "data", "logs"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        mock_settings.return_value = s
        mock_disk.return_value = MagicMock(free=10 * 1024**3, total=100 * 1024**3, used=90 * 1024**3)

        args = argparse.Namespace()
        result = cmd_doctor(args)
        assert result == 0

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.get_settings")
    def test_doctor_env_vars_set(self, mock_settings, mock_disk, tmp_path, monkeypatch):
        from dochris.cli.cli_doctor import cmd_doctor

        s = MagicMock()
        s.api_key = "sk-test-key-123456"
        s.api_base = "https://api.example.com/v1"
        s.model = "glm-5.1"
        s.workspace = tmp_path
        for d in ["raw", "wiki/summaries", "wiki/concepts", "outputs/summaries",
                   "outputs/concepts", "manifests/sources", "data", "logs"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        mock_settings.return_value = s
        mock_disk.return_value = MagicMock(free=10 * 1024**3, total=100 * 1024**3, used=90 * 1024**3)

        monkeypatch.setenv("OPENAI_API_KEY", "test-key-from-env-123")
        monkeypatch.setenv("OPENAI_API_BASE", "https://test.example.com/v1")
        monkeypatch.setenv("MODEL", "test-model")
        monkeypatch.setenv("WORKSPACE", str(tmp_path))

        args = argparse.Namespace()
        result = cmd_doctor(args)
        assert result == 0


# ============================================================
# cli/cli_init.py
# ============================================================
class TestCreateEnvFile:
    def test_create_env_file_zhipu(self, tmp_path):
        from dochris.cli.cli_init import _create_env_file

        env_file = tmp_path / ".env"
        _create_env_file(env_file, "sk-abc123")
        content = env_file.read_text(encoding="utf-8")
        assert "OPENAI_API_KEY=sk-abc123" in content
        assert "open.bigmodel.cn" in content
        assert "glm-5.1" in content

    def test_create_env_file_openrouter(self, tmp_path):
        from dochris.cli.cli_init import _create_env_file

        env_file = tmp_path / ".env"
        _create_env_file(env_file, "sk-or-v1-testkey")
        content = env_file.read_text(encoding="utf-8")
        assert "openrouter.ai" in content
        assert "qwen" in content


class TestCmdInit:
    @patch("dochris.settings.get_default_workspace")
    def test_init_python_version_low(self, mock_workspace, tmp_path):
        """cmd_init checks python version first"""
        from dochris.cli.cli_init import cmd_init

        mock_workspace.return_value = tmp_path
        args = MagicMock()
        with patch("builtins.input", return_value="n"):
            result = cmd_init(args)
        assert isinstance(result, int)

    @patch("dochris.settings.get_default_workspace")
    @patch("builtins.input")
    def test_init_already_initialized_cancel(self, mock_input, mock_workspace, tmp_path):
        """Already initialized workspace, user cancels"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / ".env").write_text("OPENAI_API_KEY=test", encoding="utf-8")
        mock_workspace.return_value = workspace
        mock_input.return_value = "n"

        args = MagicMock()
        result = cmd_init(args)
        assert result == 0

    @patch("dochris.settings.get_default_workspace")
    @patch("builtins.input")
    def test_init_no_api_key(self, mock_input, mock_workspace, tmp_path):
        """User provides no API key"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "ws_new"
        mock_workspace.return_value = workspace
        mock_input.return_value = ""  # empty input → OpenRouter placeholder

        args = MagicMock()
        result = cmd_init(args)
        assert isinstance(result, int)

    @patch("dochris.settings.get_default_workspace")
    @patch("builtins.input")
    def test_init_full_flow(self, mock_input, mock_workspace, tmp_path, monkeypatch):
        """Full init flow with valid API key"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "ws_full"
        mock_workspace.return_value = workspace
        mock_input.return_value = "sk-test-valid-key-123"

        mock_s = MagicMock()
        mock_s.validate.return_value = []
        with patch("dochris.settings.get_settings", return_value=mock_s):
            monkeypatch.setenv("WORKSPACE", str(workspace))
            args = MagicMock()
            result = cmd_init(args)

        assert result == 0
        assert (workspace / ".env").exists()
        assert (workspace / "raw" / "pdfs").exists()
        assert (workspace / "manifests" / "sources").exists()

    @patch("dochris.settings.get_default_workspace")
    @patch("builtins.input")
    def test_init_write_failure(self, mock_input, mock_workspace, tmp_path):
        """Write .env file failure"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "ws_write"
        mock_workspace.return_value = workspace
        mock_input.return_value = "sk-test-key"

        # Patch _create_env_file to raise OSError
        with patch("dochris.cli.cli_init._create_env_file", side_effect=OSError("write failed")):
            args = MagicMock()
            result = cmd_init(args)
        assert result == 1

    @patch("dochris.settings.get_default_workspace")
    @patch("builtins.input")
    def test_init_config_validation_fails(self, mock_input, mock_workspace, tmp_path, monkeypatch):
        """Configuration validation failure"""
        from dochris.cli.cli_init import cmd_init
        from dochris.exceptions import ConfigurationError

        workspace = tmp_path / "ws_val"
        mock_workspace.return_value = workspace
        mock_input.return_value = "sk-test-key-123"

        mock_s = MagicMock()
        mock_s.validate.side_effect = ConfigurationError("bad")

        with patch("dochris.settings.get_settings", return_value=mock_s):
            monkeypatch.setenv("WORKSPACE", str(workspace))
            args = MagicMock()
            result = cmd_init(args)
        assert result == 1

    @patch("dochris.settings.get_default_workspace")
    @patch("builtins.input")
    def test_init_existing_key_reuse(self, mock_input, mock_workspace, tmp_path, monkeypatch):
        """Reuse existing API key from .env"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "ws_reuse"
        workspace.mkdir()
        (workspace / ".env").write_text("OPENAI_API_KEY=sk-existing-key-abc\n", encoding="utf-8")
        mock_workspace.return_value = workspace
        # First input "Y" for re-init question (appears because .env exists),
        # second input "Y" for reusing existing key
        mock_input.side_effect = ["y", "Y"]

        mock_s = MagicMock()
        mock_s.validate.return_value = []
        with patch("dochris.settings.get_settings", return_value=mock_s):
            monkeypatch.setenv("WORKSPACE", str(workspace))
            args = MagicMock()
            result = cmd_init(args)

        assert result == 0
