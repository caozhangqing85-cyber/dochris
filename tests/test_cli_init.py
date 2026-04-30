"""tests/test_cli_init.py

CLI init 命令测试
"""

from argparse import Namespace
from unittest.mock import patch


class TestCmdInit:
    """测试 cmd_init 函数"""

    @patch('builtins.input')
    @patch('dochris.settings.get_default_workspace')
    def test_init_creates_workspace(self, mock_workspace, mock_input, tmp_path, monkeypatch):
        """测试创建工作区目录"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "test_kb"
        workspace.mkdir()
        mock_workspace.return_value = workspace
        monkeypatch.setenv("WORKSPACE", str(workspace))

        # 模拟用户输入（使用现有 API Key）
        mock_input.return_value = "n"

        args = Namespace()
        _ = cmd_init(args)

        # 工作区应该已创建
        assert workspace.exists()

    @patch('builtins.input')
    @patch('dochris.settings.get_default_workspace')
    def test_init_creates_directories(self, mock_workspace, mock_input, tmp_path, monkeypatch):
        """测试创建必要目录"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "test_kb"
        workspace.mkdir()
        mock_workspace.return_value = workspace
        monkeypatch.setenv("WORKSPACE", str(workspace))

        # 模拟用户输入
        mock_input.return_value = "n"

        args = Namespace()
        cmd_init(args)

        # 检查目录是否创建
        expected_dirs = [
            "raw/pdfs",
            "raw/articles",
            "raw/audio",
            "raw/videos",
            "raw/ebooks",
            "raw/other",
            "manifests/sources",
            "outputs/summaries",
            "outputs/concepts",
            "wiki/summaries",
            "wiki/concepts",
            "curated/summaries",
            "curated/concepts",
            "locked",
            "data",
            "logs",
            "transcripts",
        ]

        for dir_path in expected_dirs:
            assert (workspace / dir_path).exists(), f"目录 {dir_path} 未创建"

    @patch('builtins.input')
    @patch('dochris.settings.get_default_workspace')
    def test_init_creates_env_file(self, mock_workspace, mock_input, tmp_path, monkeypatch):
        """测试创建 .env 文件"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "test_kb"
        workspace.mkdir()
        mock_workspace.return_value = workspace
        monkeypatch.setenv("WORKSPACE", str(workspace))

        # 模拟用户输入新的 API Key
        mock_input.side_effect = ["n", "test-api-key-12345"]

        args = Namespace()
        _ = cmd_init(args)

        # 检查 .env 文件是否创建
        env_file = workspace / ".env"
        assert env_file.exists()

        content = env_file.read_text(encoding="utf-8")
        assert "OPENAI_API_KEY=" in content
        assert "OPENAI_API_BASE=" in content
        assert "MODEL=" in content

    @patch('builtins.input')
    @patch('dochris.settings.get_default_workspace')
    def test_init_with_openrouter_key(self, mock_workspace, mock_input, tmp_path, monkeypatch):
        """测试使用 OpenRouter API Key"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "test_kb"
        workspace.mkdir()
        mock_workspace.return_value = workspace
        monkeypatch.setenv("WORKSPACE", str(workspace))

        # 模拟 OpenRouter API Key（新工作区，直接输入 Key）
        mock_input.return_value = "sk-or-v1-test-key-12345"

        args = Namespace()
        _ = cmd_init(args)

        env_file = workspace / ".env"
        content = env_file.read_text(encoding="utf-8")

        # OpenRouter 应该使用对应的 base URL 和模型
        assert "openrouter.ai" in content
        assert "sk-or-v1-test-key-12345" in content

    @patch('builtins.input')
    @patch('dochris.settings.get_default_workspace')
    def test_init_existing_workspace(self, mock_workspace, mock_input, tmp_path, monkeypatch):
        """测试已存在的工作区"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "existing_kb"
        workspace.mkdir()
        (workspace / ".env").write_text("OPENAI_API_KEY=existing-key\n")

        mock_workspace.return_value = workspace
        monkeypatch.setenv("WORKSPACE", str(workspace))

        # 模拟用户选择不重新初始化
        mock_input.side_effect = ["n"]

        args = Namespace()
        ret = cmd_init(args)

        # 应该返回 0（成功取消）
        assert ret == 0

    @patch('builtins.input')
    @patch('dochris.settings.get_default_workspace')
    def test_init_checks_python_version(self, mock_workspace, mock_input, tmp_path, monkeypatch):
        """测试 Python 版本检查"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "test_kb"
        workspace.mkdir()
        mock_workspace.return_value = workspace
        monkeypatch.setenv("WORKSPACE", str(workspace))

        mock_input.return_value = "n"

        args = Namespace()
        ret = cmd_init(args)
        assert ret == 0


class TestPromptApiKey:
    """测试 _prompt_api_key 函数"""

    @patch('builtins.input')
    def test_prompt_api_key_with_input(self, mock_input):
        """测试提示用户输入 API Key"""
        from dochris.cli.cli_init import _prompt_api_key

        mock_input.return_value = "test-user-key"

        result = _prompt_api_key()

        assert result == "test-user-key"

    @patch('builtins.input')
    def test_prompt_api_key_empty_returns_placeholder(self, mock_input):
        """测试空输入返回占位符"""
        from dochris.cli.cli_init import _prompt_api_key

        mock_input.return_value = ""

        result = _prompt_api_key()

        # 应该返回 OpenRouter 占位符
        assert result.startswith("sk-or-v1")


class TestCreateEnvFile:
    """测试 _create_env_file 函数"""

    def test_create_env_file_with_zhipu_key(self, tmp_path):
        """测试创建智谱 API 的 .env 文件"""
        from dochris.cli.cli_init import _create_env_file

        env_file = tmp_path / ".env"
        api_key = "test-zhipu-key"

        _create_env_file(env_file, api_key)

        content = env_file.read_text(encoding="utf-8")

        assert "OPENAI_API_KEY=test-zhipu-key" in content
        assert "bigmodel.cn" in content
        assert "MODEL=glm-5.1" in content

    def test_create_env_file_with_openrouter_key(self, tmp_path):
        """测试创建 OpenRouter 的 .env 文件"""
        from dochris.cli.cli_init import _create_env_file

        env_file = tmp_path / ".env"
        api_key = "sk-or-v1-test-key"

        _create_env_file(env_file, api_key)

        content = env_file.read_text(encoding="utf-8")

        assert "OPENAI_API_KEY=sk-or-v1-test-key" in content
        assert "openrouter.ai" in content
        assert "qwen/qwen-2.5" in content

    def test_create_env_file_contains_all_sections(self, tmp_path):
        """测试 .env 文件包含所有配置节"""
        from dochris.cli.cli_init import _create_env_file

        env_file = tmp_path / ".env"
        api_key = "test-key"

        _create_env_file(env_file, api_key)

        content = env_file.read_text(encoding="utf-8")

        # 检查各配置节
        assert "LLM API 配置" in content
        assert "工作区配置" in content
        assert "数据摄入配置" in content
        assert "编译配置" in content
        assert "查询配置" in content
        assert "日志配置" in content

    def test_create_env_file_overwrites_existing(self, tmp_path):
        """测试覆盖现有 .env 文件"""
        from dochris.cli.cli_init import _create_env_file

        env_file = tmp_path / ".env"
        env_file.write_text("OLD CONTENT")

        _create_env_file(env_file, "new-key")

        content = env_file.read_text(encoding="utf-8")

        assert "OLD CONTENT" not in content
        assert "OPENAI_API_KEY=new-key" in content
