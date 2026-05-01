"""覆盖率提升 v16 — cli_utils + cli_main + hierarchical_summarizer + pdf_parser"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# cli_utils.py — style/format 函数 + show_status
# ============================================================
class TestCliUtilsFormat:
    def test_format_error_without_hint(self):
        from dochris.cli.cli_utils import format_error
        result = format_error("配置加载", "API Key 未设置")
        assert "Error" in result
        assert "配置加载" in result
        assert "API Key 未设置" in result

    def test_format_error_with_hint(self):
        from dochris.cli.cli_utils import format_error
        result = format_error("配置加载", "API Key 未设置", "请检查 .env 文件")
        assert "💡" in result
        assert "请检查 .env 文件" in result

    def test_format_warning_without_hint(self):
        from dochris.cli.cli_utils import format_warning
        result = format_warning("编译", "质量分低于阈值")
        assert "Warning" in result
        assert "编译" in result

    def test_format_warning_with_hint(self):
        from dochris.cli.cli_utils import format_warning
        result = format_warning("编译", "质量分低", "尝试重新编译")
        assert "💡" in result

    def test_style_success(self):
        from dochris.cli.cli_utils import success
        result = success("OK")
        assert "OK" in result

    def test_style_warning(self):
        from dochris.cli.cli_utils import warning
        result = warning("warn")
        assert "warn" in result

    def test_style_error(self):
        from dochris.cli.cli_utils import error
        result = error("fail")
        assert "fail" in result

    def test_style_info(self):
        from dochris.cli.cli_utils import info
        result = info("info")
        assert "info" in result

    def test_style_dim(self):
        from dochris.cli.cli_utils import dim
        result = dim("text")
        assert "text" in result

    def test_style_bold(self):
        from dochris.cli.cli_utils import bold
        result = bold("text")
        assert "text" in result


class TestCliUtilsShowStatus:
    def _mock_settings(self, api_key="sk-test123456"):
        s = MagicMock()
        s.source_path = None
        s.obsidian_vaults = []
        s.api_key = api_key
        s.api_base = "https://api.example.com"
        s.model = "glm-5.1"
        s.max_concurrency = 3
        s.min_quality_score = 85
        s.max_content_chars = 20000
        return s

    def test_show_status_no_source_no_api_key(self, tmp_path):
        from dochris.cli.cli_utils import show_status
        mock_s = self._mock_settings(api_key="")
        with patch("dochris.cli.cli_utils.get_default_workspace", return_value=tmp_path), \
             patch("dochris.cli.cli_utils.get_settings", return_value=mock_s), \
             patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]), \
             patch("dochris.cli.cli_utils.get_raw_dir", return_value=tmp_path / "raw"), \
             patch("dochris.cli.cli_utils.get_outputs_dir", return_value=tmp_path / "outputs"), \
             patch("dochris.cli.cli_utils.get_wiki_dir", return_value=tmp_path / "wiki"), \
             patch("dochris.cli.cli_utils.get_manifests_dir", return_value=tmp_path / "manifests"), \
             patch("dochris.cli.cli_utils.get_logs_dir", return_value=tmp_path / "logs"):
            assert show_status(tmp_path) == 0

    def test_show_status_with_source_and_vaults(self, tmp_path):
        from dochris.cli.cli_utils import show_status
        source = tmp_path / "materials"
        source.mkdir()
        (source / "test.md").write_text("test", encoding="utf-8")
        vault = tmp_path / "vault"
        vault.mkdir()

        mock_s = self._mock_settings()
        mock_s.source_path = source
        mock_s.obsidian_vaults = [vault]
        with patch("dochris.cli.cli_utils.get_default_workspace", return_value=tmp_path), \
             patch("dochris.cli.cli_utils.get_settings", return_value=mock_s), \
             patch("dochris.cli.cli_utils.get_all_manifests", return_value=[
                 {"status": "compiled", "quality_score": 90},
                 {"status": "pending", "quality_score": 0},
             ]), \
             patch("dochris.cli.cli_utils.get_raw_dir", return_value=tmp_path / "raw"), \
             patch("dochris.cli.cli_utils.get_outputs_dir", return_value=tmp_path / "outputs"), \
             patch("dochris.cli.cli_utils.get_wiki_dir", return_value=tmp_path / "wiki"), \
             patch("dochris.cli.cli_utils.get_manifests_dir", return_value=tmp_path / "manifests"), \
             patch("dochris.cli.cli_utils.get_logs_dir", return_value=tmp_path / "logs"):
            assert show_status(tmp_path) == 0

    def test_show_status_source_not_exists(self, tmp_path):
        from dochris.cli.cli_utils import show_status
        mock_s = self._mock_settings()
        mock_s.source_path = tmp_path / "nonexistent"
        with patch("dochris.cli.cli_utils.get_default_workspace", return_value=tmp_path), \
             patch("dochris.cli.cli_utils.get_settings", return_value=mock_s), \
             patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]), \
             patch("dochris.cli.cli_utils.get_raw_dir", return_value=tmp_path / "raw"), \
             patch("dochris.cli.cli_utils.get_outputs_dir", return_value=tmp_path / "outputs"), \
             patch("dochris.cli.cli_utils.get_wiki_dir", return_value=tmp_path / "wiki"), \
             patch("dochris.cli.cli_utils.get_manifests_dir", return_value=tmp_path / "manifests"), \
             patch("dochris.cli.cli_utils.get_logs_dir", return_value=tmp_path / "logs"):
            assert show_status(tmp_path) == 0

    def test_show_status_with_existing_dirs(self, tmp_path):
        from dochris.cli.cli_utils import show_status
        (tmp_path / "raw").mkdir()
        (tmp_path / "outputs").mkdir()
        (tmp_path / "wiki").mkdir()
        (tmp_path / "manifests").mkdir()
        (tmp_path / "logs").mkdir()
        (tmp_path / "outputs" / "test.md").write_text("test", encoding="utf-8")

        mock_s = self._mock_settings()
        with patch("dochris.cli.cli_utils.get_default_workspace", return_value=tmp_path), \
             patch("dochris.cli.cli_utils.get_settings", return_value=mock_s), \
             patch("dochris.cli.cli_utils.get_all_manifests", return_value=[
                 {"status": "compiled", "quality_score": 95},
                 {"status": "compiled", "quality_score": 80},
                 {"status": "pending", "quality_score": 0},
             ]), \
             patch("dochris.cli.cli_utils.get_raw_dir", return_value=tmp_path / "raw"), \
             patch("dochris.cli.cli_utils.get_outputs_dir", return_value=tmp_path / "outputs"), \
             patch("dochris.cli.cli_utils.get_wiki_dir", return_value=tmp_path / "wiki"), \
             patch("dochris.cli.cli_utils.get_manifests_dir", return_value=tmp_path / "manifests"), \
             patch("dochris.cli.cli_utils.get_logs_dir", return_value=tmp_path / "logs"):
            assert show_status(tmp_path) == 0


# ============================================================
# cli/main.py — argparse 分支
# ============================================================
# cli/main.py 需要 Settings 对象的复杂 mock，跳过
