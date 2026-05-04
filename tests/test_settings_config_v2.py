"""Settings 配置管理测试"""

from __future__ import annotations

from pathlib import Path

import pytest

from dochris.settings.config import Settings, get_settings, reset_settings

# ── Settings 默认值 ────────────────────────────────────────────


class TestSettingsDefaults:
    """Settings 默认值"""

    def test_default_workspace(self):
        """默认工作区路径"""
        s = Settings()
        assert "knowledge-base" in str(s.workspace)

    def test_default_model(self):
        """默认模型"""
        s = Settings()
        assert s.model is not None
        assert isinstance(s.model, str)

    def test_default_max_retries(self):
        """默认最大重试次数"""
        s = Settings()
        assert s.max_retries == 3

    def test_default_batch_size(self):
        """默认批处理大小"""
        s = Settings()
        assert s.batch_size == 10

    def test_default_llm_temperature(self):
        """默认 LLM 温度"""
        s = Settings()
        assert s.llm_temperature == 0.1


# ── 路径访问器 ─────────────────────────────────────────────────


class TestPathAccessors:
    """路径访问器属性"""

    def _make_settings(self, tmp_path: Path) -> Settings:
        s = Settings()
        s.workspace = tmp_path
        return s

    def test_logs_dir(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.logs_dir == tmp_path / "logs"

    def test_cache_dir(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.cache_dir == tmp_path / "cache"

    def test_outputs_dir(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.outputs_dir == tmp_path / "outputs"

    def test_raw_dir(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.raw_dir == tmp_path / "raw"

    def test_wiki_dir(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.wiki_dir == tmp_path / "wiki"

    def test_wiki_summaries_dir(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.wiki_summaries_dir == tmp_path / "wiki" / "summaries"

    def test_manifests_dir(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.manifests_dir == tmp_path / "manifests" / "sources"

    def test_curated_promoted_dir(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.curated_promoted_dir == tmp_path / "curated" / "promoted"

    def test_data_dir(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.data_dir == tmp_path / "data"

    def test_progress_file(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.progress_file == tmp_path / "progress.json"

    def test_phase2_lock_file(self, tmp_path):
        s = self._make_settings(tmp_path)
        assert s.phase2_lock_file == tmp_path / "phase2.lock"


# ── from_env 环境变量 ──────────────────────────────────────────


class TestFromEnv:
    """从环境变量加载配置"""

    def test_workspace_from_env(self, monkeypatch):
        """WORKSPACE 环境变量覆盖默认值"""
        monkeypatch.setenv("WORKSPACE", "/tmp/custom_ws")
        s = Settings.from_env()
        assert str(s.workspace) == "/tmp/custom_ws"

    def test_model_from_env(self, monkeypatch):
        """MODEL 环境变量覆盖默认值"""
        monkeypatch.setenv("MODEL", "gpt-4")
        s = Settings.from_env()
        assert s.model == "gpt-4"

    def test_api_key_from_env(self, monkeypatch):
        """OPENAI_API_KEY 环境变量设置 api_key"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        s = Settings.from_env()
        assert s.api_key == "sk-test-key"

    def test_max_concurrency_from_env(self, monkeypatch):
        """MAX_CONCURRENCY 环境变量"""
        monkeypatch.setenv("MAX_CONCURRENCY", "5")
        s = Settings.from_env()
        assert s.max_concurrency == 5

    def test_min_quality_score_from_env(self, monkeypatch):
        """MIN_QUALITY_SCORE 环境变量"""
        monkeypatch.setenv("MIN_QUALITY_SCORE", "90")
        s = Settings.from_env()
        assert s.min_quality_score == 90

    def test_log_level_from_env(self, monkeypatch):
        """LOG_LEVEL 环境变量"""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = Settings.from_env()
        assert s.log_level == "DEBUG"

    def test_obsidian_vault_from_env(self, monkeypatch):
        """OBSIDIAN_VAULT 环境变量"""
        monkeypatch.setenv("OBSIDIAN_VAULT", "/home/user/vault")
        s = Settings.from_env()
        assert len(s.obsidian_vaults) == 1
        assert str(s.obsidian_vaults[0]) == "/home/user/vault"

    def test_plugins_enabled_from_env(self, monkeypatch):
        """PLUGINS_ENABLED 环境变量"""
        monkeypatch.setenv("PLUGINS_ENABLED", "plugin_a,plugin_b")
        s = Settings.from_env()
        assert s.plugins_enabled == ["plugin_a", "plugin_b"]


# ── validate_api_key ───────────────────────────────────────────


class TestValidateApiKey:
    """验证 API 密钥"""

    def test_returns_key_when_set(self):
        """api_key 已设置时直接返回"""
        s = Settings(api_key="sk-valid")
        assert s.validate_api_key() == "sk-valid"

    def test_raises_when_missing(self, monkeypatch):
        """api_key 未设置时抛出 ValueError"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = Settings(api_key=None)
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            s.validate_api_key()

    def test_falls_back_to_env(self, monkeypatch):
        """api_key 未设置时回退到环境变量"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        s = Settings(api_key=None)
        assert s.validate_api_key() == "sk-from-env"


# ── validate ───────────────────────────────────────────────────


class TestValidate:
    """验证配置"""

    def test_empty_api_base_raises(self, tmp_path, monkeypatch):
        """空 api_base 抛出 ValueError"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = Settings(api_base="", workspace=tmp_path)
        with pytest.raises(ValueError, match="api_base"):
            s.validate()

    def test_empty_model_raises(self, tmp_path, monkeypatch):
        """空 model 抛出 ValueError"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = Settings(model="", workspace=tmp_path, api_base="https://api.example.com/v1")
        with pytest.raises(ValueError, match="model"):
            s.validate()

    def test_no_api_key_warns(self, tmp_path, monkeypatch):
        """无 API key 时返回警告"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = Settings(
            workspace=tmp_path,
            api_base="https://api.example.com/v1",
            model="test-model",
            api_key=None,
        )
        warnings = s.validate()
        assert len(warnings) > 0

    def test_valid_config_no_warnings(self, tmp_path, monkeypatch):
        """有效配置无警告"""
        s = Settings(
            workspace=tmp_path,
            api_base="https://api.example.com/v1",
            model="test-model",
            api_key="sk-valid",
        )
        warnings = s.validate()
        assert warnings == []


# ── get_settings / reset_settings ──────────────────────────────


class TestGetSettings:
    """全局 Settings 单例"""

    def test_get_settings_returns_settings(self):
        """返回 Settings 实例"""
        reset_settings()
        s = get_settings()
        assert isinstance(s, Settings)

    def test_reload(self):
        """reload=True 重新加载"""
        reset_settings()
        get_settings()
        s2 = get_settings(reload=True)
        assert isinstance(s2, Settings)

    def test_reset(self):
        """reset 清除全局实例"""
        reset_settings()
        s = get_settings()
        assert s is not None
        reset_settings()
        # 下次调用会创建新实例
        s2 = get_settings()
        assert isinstance(s2, Settings)

    def teardown_method(self):
        """每个测试后重置全局状态"""
        reset_settings()
