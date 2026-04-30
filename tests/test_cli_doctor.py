"""
测试 cli_doctor.py 模块
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    """模拟工作区"""
    workspace = tmp_path / "kb"
    workspace.mkdir()

    # 创建必要的目录
    (workspace / "raw").mkdir()
    (workspace / "wiki" / "summaries").mkdir(parents=True)
    (workspace / "wiki" / "concepts").mkdir(parents=True)
    (workspace / "outputs" / "summaries").mkdir(parents=True)
    (workspace / "outputs" / "concepts").mkdir(parents=True)
    (workspace / "manifests" / "sources").mkdir(parents=True)
    (workspace / "data").mkdir()
    (workspace / "logs").mkdir()

    # 创建 .env 文件
    (workspace / ".env").write_text("OPENAI_API_KEY=test-key-123456\n", encoding="utf-8")

    monkeypatch.setenv("WORKSPACE", str(workspace))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123456")

    return workspace


class TestCmdDoctor:
    """测试 cmd_doctor 函数"""

    def test_cmd_doctor_exists(self):
        """测试 cmd_doctor 函数存在"""
        from dochris.cli.cli_doctor import cmd_doctor

        assert callable(cmd_doctor)

    @patch("dochris.cli.cli_doctor.print")
    def test_cmd_doctor_with_valid_config(self, mock_print, mock_workspace):
        """测试配置正常的诊断"""
        from dochris.cli.cli_doctor import cmd_doctor

        args = argparse.Namespace()

        result = cmd_doctor(args)

        # 应该能正常执行（可能因为可选依赖返回 1，但不应该抛异常）
        assert result in (0, 1)

    @patch("dochris.cli.cli_doctor.print")
    def test_cmd_doctor_without_workspace(self, mock_print, tmp_path, monkeypatch):
        """测试工作区不存在的诊断"""
        from dochris.cli.cli_doctor import cmd_doctor

        # 设置不存在的路径
        nonexistent = tmp_path / "nonexistent_kb"
        monkeypatch.setenv("WORKSPACE", str(nonexistent))
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        args = argparse.Namespace()

        result = cmd_doctor(args)

        # 应该返回 1（有问题）
        assert result == 1

    @patch("dochris.cli.cli_doctor.print")
    def test_cmd_doctor_without_api_key(self, mock_print, tmp_path, monkeypatch):
        """测试 API Key 未配置的诊断"""
        from dochris.cli.cli_doctor import cmd_doctor

        # 移除 API key
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        args = argparse.Namespace()

        result = cmd_doctor(args)

        # 应该返回 1（有问题）
        assert result == 1

    @patch("dochris.cli.cli_doctor.print")
    def test_cmd_doctor_checks_python_version(self, mock_print):
        """测试 Python 版本检查"""
        from dochris.cli.cli_doctor import cmd_doctor

        args = argparse.Namespace()

        # 这个测试确保函数能正常执行而不崩溃
        result = cmd_doctor(args)
        assert result in (0, 1)  # 可能因为其他检查失败

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.print")
    def test_cmd_doctor_disk_space_check(self, mock_print, mock_disk_usage, mock_workspace):
        """测试磁盘空间检查"""
        from dochris.cli.cli_doctor import cmd_doctor

        # 模拟磁盘空间充足
        mock_usage = MagicMock()
        mock_usage.total = 100 * (1024**3)  # 100GB
        mock_usage.used = 20 * (1024**3)  # 20GB
        mock_usage.free = 80 * (1024**3)  # 80GB
        mock_disk_usage.return_value = mock_usage

        args = argparse.Namespace()

        result = cmd_doctor(args)

        # 磁盘空间充足，应该能正常执行
        assert result in (0, 1)

    @patch("dochris.cli.cli_doctor.shutil.disk_usage")
    @patch("dochris.cli.cli_doctor.print")
    def test_cmd_doctor_low_disk_space(self, mock_print, mock_disk_usage, mock_workspace):
        """测试磁盘空间不足"""
        from dochris.cli.cli_doctor import cmd_doctor

        # 模拟磁盘空间不足
        mock_usage = MagicMock()
        mock_usage.total = 100 * (1024**3)
        mock_usage.used = 99 * (1024**3)
        mock_usage.free = 0.5 * (1024**3)  # 500MB
        mock_disk_usage.return_value = mock_usage

        args = argparse.Namespace()

        result = cmd_doctor(args)

        # 磁盘空间不足，应该返回错误
        assert result == 1

    @patch("dochris.cli.cli_doctor.print")
    def test_cmd_doctor_dependency_check(self, mock_print, mock_workspace):
        """测试核心依赖检查"""
        from dochris.cli.cli_doctor import cmd_doctor

        args = argparse.Namespace()

        # 这个测试确保依赖检查能正常运行
        # openai, chromadb, markitdown 应该都已安装
        result = cmd_doctor(args)
        assert result in (0, 1)


class TestDoctorOutput:
    """测试 doctor 命令输出"""

    def test_doctor_prints_header(self):
        """测试打印诊断头部"""
        from dochris.cli.cli_doctor import cmd_doctor

        args = argparse.Namespace()

        with patch("dochris.cli.cli_doctor.print") as mock_print:
            cmd_doctor(args)

            # 验证打印了头部信息
            calls = [str(call) for call in mock_print.call_args_list]
            printed_text = " ".join(calls)
            assert "诊断" in printed_text or "=" in printed_text

    def test_doctor_checks_workspace_dirs(self, mock_workspace):
        """测试检查工作区目录"""
        from dochris.cli.cli_doctor import cmd_doctor

        args = argparse.Namespace()

        with patch("dochris.cli.cli_doctor.print") as mock_print:
            cmd_doctor(args)

            # 验证打印了目录检查信息
            calls = [str(call) for call in mock_print.call_args_list]
            printed_text = " ".join(calls)
            # 应该有目录相关的输出
            assert any(keyword in printed_text for keyword in ["目录", "summaries", "manifests"])
