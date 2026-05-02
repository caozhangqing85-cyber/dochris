"""覆盖率提升 v18 — 最后冲刺 75%"""

from pathlib import Path
from unittest.mock import patch

import pytest

# ============================================================
# cli/cli_doctor.py — 15 miss
# ============================================================
# cli_doctor 内部函数不好直接测试，跳过


# ============================================================
# cli/cli_init.py — 10 miss
# ============================================================
class TestCliInit:
    def test_init_prompt_api_key_empty(self):
        from dochris.cli.cli_init import _prompt_api_key
        with patch("builtins.input", return_value=""):
            result = _prompt_api_key()
            assert result is not None  # returns placeholder

    def test_init_prompt_api_key_value(self):
        from dochris.cli.cli_init import _prompt_api_key
        with patch("builtins.input", return_value="sk-mykey"):
            result = _prompt_api_key()
            assert result == "sk-mykey"

    def test_init_create_env_file(self, tmp_path):
        from dochris.cli.cli_init import _create_env_file
        env_file = tmp_path / ".env"
        _create_env_file(env_file, "sk-test123")
        assert env_file.exists()
        content = env_file.read_text()
        assert "sk-test123" in content
        assert "glm-5.1" in content

    def test_init_create_env_openrouter(self, tmp_path):
        from dochris.cli.cli_init import _create_env_file
        env_file = tmp_path / ".env"
        _create_env_file(env_file, "sk-or-v1-test")
        content = env_file.read_text()
        assert "openrouter" in content.lower()


# ============================================================
# admin/recompile.py — 9 miss
# ============================================================
# recompile.py uses main() not cmd_recompile, skip


# ============================================================
# core/retry_manager.py — 5 miss
# ============================================================
class TestRetryManagerBranches:
    @pytest.mark.asyncio
    async def test_retry_content_filter(self):
        from dochris.core.retry_manager import RetryManager
        call_count = 0
        async def _content_filtered():
            nonlocal call_count
            call_count += 1
            raise Exception("contentfilter triggered")
        result = await RetryManager.llm_retry_with_filter(_content_filtered, max_retries=2)
        assert result is None
        assert call_count == 1  # content filter should not retry

    @pytest.mark.asyncio
    async def test_retry_success_on_second(self):
        from dochris.core.retry_manager import RetryManager
        call_count = 0
        async def _flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("timeout")
            return "ok"
        result = await RetryManager.llm_retry_with_filter(_flaky, max_retries=3)
        assert result == "ok"
        assert call_count == 2


# ============================================================
# settings/config.py — 12 miss
# ============================================================
class TestSettingsConfig:
    def test_settings_validate_warnings(self):
        from dochris.settings.config import Settings
        s = Settings()
        s.api_key = ""
        warnings = s.validate()
        assert isinstance(warnings, list)

    def test_settings_workspace_default(self):
        from dochris.settings.config import Settings
        s = Settings()
        assert s.workspace is not None
        assert isinstance(s.workspace, Path)

    def test_settings_defaults(self):
        from dochris.settings.config import Settings
        s = Settings()
        assert s.max_concurrency > 0
        assert s.min_quality_score > 0
        assert s.model is not None
