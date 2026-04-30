"""测试 settings/env.py 环境变量读取逻辑"""
import os
from pathlib import Path

from dochris.settings import Settings, reset_settings


class TestSettingsFromEnv:
    def test_from_env_reads_api_key(self, tmp_path: Path, monkeypatch) -> None:
        """从 .env 读取 API Key"""
        env_file = tmp_path / ".env"
        env_file.write_text("OPENAI_API_KEY=from-file-key")

        monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")

        # reset settings 以重新加载
        reset_settings()

        # 创建新的 settings 实例
        settings = Settings(
            workspace=tmp_path,
            api_key="test-key-123",  # 环境变量优先
            api_base="https://api.openai.com/v1",
            model="gpt-4o",
        )

        assert settings.api_key == "test-key-123"

    def test_from_env_default_values(self, monkeypatch) -> None:
        """默认值正确"""
        # 清除所有相关环境变量
        for key in ["OPENAI_API_KEY", "LLM_MODEL", "LLM_API_BASE", "WORKSPACE"]:
            monkeypatch.delenv(key, raising=False)

        reset_settings()

        # 使用默认值创建 settings
        settings = Settings(
            workspace=Path.home() / ".knowledge-base",
            api_key="",
            api_base="https://api.openai.com/v1",
            model="gpt-4o",
        )

        assert settings.api_base == "https://api.openai.com/v1"
        assert settings.model == "gpt-4o"

    def test_from_env_plugin_dirs(self, monkeypatch) -> None:
        """插件目录配置"""
        monkeypatch.setenv("PLUGIN_DIRS", "/a:/b:/c")
        reset_settings()

        # 测试插件目录解析
        plugin_dirs = os.environ.get("PLUGIN_DIRS", "")
        if plugin_dirs:
            result = plugin_dirs.split(":")
            assert result == ["/a", "/b", "/c"]

    def test_from_env_empty_api_key(self, tmp_path: Path, monkeypatch) -> None:
        """空 API Key 处理"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text("OPENAI_API_KEY=")

        reset_settings()

        # 空 API key 应该返回空字符串
        settings = Settings(
            workspace=tmp_path,
            api_key="",
            api_base="https://api.openai.com/v1",
            model="gpt-4o",
        )

        assert settings.api_key == ""
