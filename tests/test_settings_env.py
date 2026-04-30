"""测试 settings/env.py 环境变量读取逻辑"""
import os
from pathlib import Path

import pytest

from dochris.settings import Settings, reset_settings
from dochris.settings.env import get_env_bool, get_env_int, get_env_list, get_env_path, get_env_str


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


class TestGetEnvPath:
    """测试从环境变量读取路径"""

    def test_existing_env_var(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量存在时返回路径"""
        monkeypatch.setenv("TEST_PATH", "/tmp/test_dir")
        result = get_env_path("TEST_PATH")
        assert result is not None
        assert isinstance(result, Path)

    def test_missing_env_var_no_default(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量不存在且无默认值返回 None"""
        monkeypatch.delenv("TEST_MISSING_PATH", raising=False)
        result = get_env_path("TEST_MISSING_PATH")
        assert result is None

    def test_missing_env_var_with_default(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量不存在但有默认值"""
        default = Path("/default/path")
        monkeypatch.delenv("TEST_MISSING_PATH", raising=False)
        result = get_env_path("TEST_MISSING_PATH", default=default)
        assert result == default

    def test_tilde_expansion(self, monkeypatch: pytest.MonkeyPatch):
        """~ 路径展开"""
        monkeypatch.setenv("TEST_HOME_PATH", "~/documents")
        result = get_env_path("TEST_HOME_PATH")
        assert result is not None
        assert "~" not in str(result)

    def test_empty_env_var(self, monkeypatch: pytest.MonkeyPatch):
        """空字符串环境变量返回 None"""
        monkeypatch.setenv("TEST_EMPTY_PATH", "")
        result = get_env_path("TEST_EMPTY_PATH")
        assert result is None


class TestGetEnvStr:
    """测试从环境变量读取字符串"""

    def test_existing_env_var(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量存在"""
        monkeypatch.setenv("TEST_STR", "hello")
        assert get_env_str("TEST_STR") == "hello"

    def test_missing_env_var_default(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量不存在使用默认值"""
        monkeypatch.delenv("TEST_MISSING_STR", raising=False)
        assert get_env_str("TEST_MISSING_STR", default="fallback") == "fallback"

    def test_missing_env_var_empty(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量不存在默认空字符串"""
        monkeypatch.delenv("TEST_MISSING_STR", raising=False)
        assert get_env_str("TEST_MISSING_STR") == ""


class TestGetEnvInt:
    """测试从环境变量读取整数"""

    def test_valid_integer(self, monkeypatch: pytest.MonkeyPatch):
        """有效整数"""
        monkeypatch.setenv("TEST_INT", "42")
        assert get_env_int("TEST_INT") == 42

    def test_negative_integer(self, monkeypatch: pytest.MonkeyPatch):
        """负整数"""
        monkeypatch.setenv("TEST_NEG_INT", "-10")
        assert get_env_int("TEST_NEG_INT") == -10

    def test_invalid_integer(self, monkeypatch: pytest.MonkeyPatch):
        """无效整数返回默认值"""
        monkeypatch.setenv("TEST_BAD_INT", "not_a_number")
        assert get_env_int("TEST_BAD_INT", default=99) == 99

    def test_missing_env_var(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量不存在返回默认值"""
        monkeypatch.delenv("TEST_MISSING_INT", raising=False)
        assert get_env_int("TEST_MISSING_INT", default=5) == 5

    def test_zero(self, monkeypatch: pytest.MonkeyPatch):
        """零"""
        monkeypatch.setenv("TEST_ZERO", "0")
        assert get_env_int("TEST_ZERO") == 0


class TestGetEnvBool:
    """测试从环境变量读取布尔值"""

    @pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "on", "ON"])
    def test_true_values(self, monkeypatch: pytest.MonkeyPatch, value: str):
        """各种 True 值"""
        monkeypatch.setenv("TEST_BOOL", value)
        assert get_env_bool("TEST_BOOL") is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "FALSE", "no", "off", "OFF"])
    def test_false_values(self, monkeypatch: pytest.MonkeyPatch, value: str):
        """各种 False 值"""
        monkeypatch.setenv("TEST_BOOL", value)
        assert get_env_bool("TEST_BOOL") is False

    def test_missing_default_true(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量不存在默认 True"""
        monkeypatch.delenv("TEST_MISSING_BOOL", raising=False)
        assert get_env_bool("TEST_MISSING_BOOL", default=True) is True

    def test_unrecognized_value(self, monkeypatch: pytest.MonkeyPatch):
        """无法识别的值返回默认值"""
        monkeypatch.setenv("TEST_WEIRD", "maybe")
        assert get_env_bool("TEST_WEIRD", default=True) is True


class TestGetEnvList:
    """测试从环境变量读取列表"""

    def test_comma_separated(self, monkeypatch: pytest.MonkeyPatch):
        """逗号分隔"""
        monkeypatch.setenv("TEST_LIST", "a,b,c")
        assert get_env_list("TEST_LIST") == ["a", "b", "c"]

    def test_custom_separator(self, monkeypatch: pytest.MonkeyPatch):
        """自定义分隔符"""
        monkeypatch.setenv("TEST_LIST_SEP", "a:b:c")
        assert get_env_list("TEST_LIST_SEP", separator=":") == ["a", "b", "c"]

    def test_with_spaces(self, monkeypatch: pytest.MonkeyPatch):
        """包含空格自动 trim"""
        monkeypatch.setenv("TEST_LIST_SPACES", " a , b , c ")
        assert get_env_list("TEST_LIST_SPACES") == ["a", "b", "c"]

    def test_empty_items_filtered(self, monkeypatch: pytest.MonkeyPatch):
        """空项被过滤"""
        monkeypatch.setenv("TEST_LIST_EMPTY", "a,,b,,,c")
        assert get_env_list("TEST_LIST_EMPTY") == ["a", "b", "c"]

    def test_missing_no_default(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量不存在无默认值返回空列表"""
        monkeypatch.delenv("TEST_MISSING_LIST", raising=False)
        assert get_env_list("TEST_MISSING_LIST") == []

    def test_missing_with_default(self, monkeypatch: pytest.MonkeyPatch):
        """环境变量不存在有默认值"""
        monkeypatch.delenv("TEST_MISSING_LIST", raising=False)
        assert get_env_list("TEST_MISSING_LIST", default=["x"]) == ["x"]

    def test_empty_value(self, monkeypatch: pytest.MonkeyPatch):
        """空字符串值返回空列表"""
        monkeypatch.setenv("TEST_EMPTY_LIST", "")
        assert get_env_list("TEST_EMPTY_LIST") == []
