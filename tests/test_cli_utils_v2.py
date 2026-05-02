"""补充测试 cli_utils.py — 覆盖 show_status 所有分支"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from dochris.cli.cli_utils import (
    format_error,
    format_warning,
    show_status,
)


class TestShowStatusSourcePath:
    """覆盖 show_status 中 source_path 相关分支"""

    def test_source_path_exists_with_files(self):
        """source_path 存在且有文件"""
        with patch("dochris.cli.cli_utils.get_settings") as mock_s:
            with patch("dochris.cli.cli_utils.get_raw_dir") as mock_raw:
                with patch("dochris.cli.cli_utils.get_outputs_dir") as mock_out:
                    with patch("dochris.cli.cli_utils.get_wiki_dir") as mock_wiki:
                        with patch("dochris.cli.cli_utils.get_manifests_dir") as mock_mf:
                            with patch("dochris.cli.cli_utils.get_logs_dir") as mock_log:
                                with patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]):
                                    with patch("builtins.print"):
                                        mock_src = MagicMock()
                                        mock_src.exists.return_value = True
                                        mock_src.is_dir.return_value = True
                                        mock_src.rglob.return_value = [MagicMock(is_file=lambda: True) for _ in range(3)]
                                        mock_s.return_value = MagicMock(
                                            source_path=mock_src,
                                            obsidian_vaults=[],
                                            api_key="test-key-long-value",
                                            api_base="https://api.test.com",
                                            model="test-model",
                                            max_concurrency=3,
                                            min_quality_score=85,
                                            max_content_chars=20000,
                                        )
                                        for p in [mock_raw, mock_out, mock_wiki, mock_mf, mock_log]:
                                            p.return_value = MagicMock(exists=lambda: True, is_dir=lambda: True, rglob=lambda pat: [])

                                        rc = show_status(Path("/test"))
        assert rc == 0

    def test_source_path_not_exists(self):
        """source_path 不存在"""
        with patch("dochris.cli.cli_utils.get_settings") as mock_s:
            with patch("dochris.cli.cli_utils.get_raw_dir") as mock_raw:
                with patch("dochris.cli.cli_utils.get_outputs_dir") as mock_out:
                    with patch("dochris.cli.cli_utils.get_wiki_dir") as mock_wiki:
                        with patch("dochris.cli.cli_utils.get_manifests_dir") as mock_mf:
                            with patch("dochris.cli.cli_utils.get_logs_dir") as mock_log:
                                with patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]):
                                    with patch("builtins.print"):
                                        mock_src = MagicMock()
                                        mock_src.exists.return_value = False
                                        mock_s.return_value = MagicMock(
                                            source_path=mock_src,
                                            obsidian_vaults=[],
                                            api_key=None,
                                            api_base="",
                                            model="",
                                            max_concurrency=1,
                                            min_quality_score=85,
                                            max_content_chars=20000,
                                        )
                                        for p in [mock_raw, mock_out, mock_wiki, mock_mf, mock_log]:
                                            p.return_value = MagicMock(exists=lambda: False, is_dir=lambda: False, rglob=lambda pat: [])

                                        rc = show_status(Path("/test"))
        assert rc == 0

    def test_source_path_not_dir(self):
        """source_path 存在但不是目录"""
        with patch("dochris.cli.cli_utils.get_settings") as mock_s:
            with patch("dochris.cli.cli_utils.get_raw_dir") as mock_raw:
                with patch("dochris.cli.cli_utils.get_outputs_dir") as mock_out:
                    with patch("dochris.cli.cli_utils.get_wiki_dir") as mock_wiki:
                        with patch("dochris.cli.cli_utils.get_manifests_dir") as mock_mf:
                            with patch("dochris.cli.cli_utils.get_logs_dir") as mock_log:
                                with patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]):
                                    with patch("builtins.print"):
                                        mock_src = MagicMock()
                                        mock_src.exists.return_value = True
                                        mock_src.is_dir.return_value = False
                                        mock_s.return_value = MagicMock(
                                            source_path=mock_src,
                                            obsidian_vaults=[],
                                            api_key=None,
                                            api_base="",
                                            model="",
                                            max_concurrency=1,
                                            min_quality_score=85,
                                            max_content_chars=20000,
                                        )
                                        for p in [mock_raw, mock_out, mock_wiki, mock_mf, mock_log]:
                                            p.return_value = MagicMock(exists=lambda: False, is_dir=lambda: False, rglob=lambda pat: [])

                                        rc = show_status(Path("/test"))
        assert rc == 0


class TestShowStatusObsidianVaults:
    """覆盖 obsidian_vaults 分支"""

    def test_with_existing_vaults(self):
        """有 obsidian vaults 配置"""
        mock_vault = MagicMock()
        mock_vault.exists.return_value = True

        with patch("dochris.cli.cli_utils.get_settings") as mock_s:
            with patch("dochris.cli.cli_utils.get_raw_dir") as mock_raw:
                with patch("dochris.cli.cli_utils.get_outputs_dir") as mock_out:
                    with patch("dochris.cli.cli_utils.get_wiki_dir") as mock_wiki:
                        with patch("dochris.cli.cli_utils.get_manifests_dir") as mock_mf:
                            with patch("dochris.cli.cli_utils.get_logs_dir") as mock_log:
                                with patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]):
                                    with patch("builtins.print"):
                                        mock_s.return_value = MagicMock(
                                            source_path=None,
                                            obsidian_vaults=[mock_vault],
                                            api_key="test-key-long-value",
                                            api_base="https://api.test.com",
                                            model="test-model",
                                            max_concurrency=3,
                                            min_quality_score=85,
                                            max_content_chars=20000,
                                        )
                                        for p in [mock_raw, mock_out, mock_wiki, mock_mf, mock_log]:
                                            p.return_value = MagicMock(exists=lambda: True, is_dir=lambda: True, rglob=lambda pat: [])

                                        rc = show_status(Path("/test"))
        assert rc == 0

    def test_with_nonexistent_vaults(self):
        """vaults 路径不存在"""
        mock_vault = MagicMock()
        mock_vault.exists.return_value = False

        with patch("dochris.cli.cli_utils.get_settings") as mock_s:
            with patch("dochris.cli.cli_utils.get_raw_dir") as mock_raw:
                with patch("dochris.cli.cli_utils.get_outputs_dir") as mock_out:
                    with patch("dochris.cli.cli_utils.get_wiki_dir") as mock_wiki:
                        with patch("dochris.cli.cli_utils.get_manifests_dir") as mock_mf:
                            with patch("dochris.cli.cli_utils.get_logs_dir") as mock_log:
                                with patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]):
                                    with patch("builtins.print"):
                                        mock_s.return_value = MagicMock(
                                            source_path=None,
                                            obsidian_vaults=[mock_vault],
                                            api_key="test-key-long-value",
                                            api_base="https://api.test.com",
                                            model="test-model",
                                            max_concurrency=3,
                                            min_quality_score=85,
                                            max_content_chars=20000,
                                        )
                                        for p in [mock_raw, mock_out, mock_wiki, mock_mf, mock_log]:
                                            p.return_value = MagicMock(exists=lambda: True, is_dir=lambda: True, rglob=lambda pat: [])

                                        rc = show_status(Path("/test"))
        assert rc == 0


class TestShowStatusManifestStats:
    """覆盖 manifest 统计分支"""

    def test_with_manifests_and_scores(self):
        """有 manifest 统计和质量分"""
        manifests = [
            {"status": "compiled", "quality_score": 90},
            {"status": "compiled", "quality_score": 85},
            {"status": "promoted_to_wiki", "quality_score": 95},
            {"status": "failed", "quality_score": 0},
        ]

        with patch("dochris.cli.cli_utils.get_settings") as mock_s:
            with patch("dochris.cli.cli_utils.get_raw_dir") as mock_raw:
                with patch("dochris.cli.cli_utils.get_outputs_dir") as mock_out:
                    with patch("dochris.cli.cli_utils.get_wiki_dir") as mock_wiki:
                        with patch("dochris.cli.cli_utils.get_manifests_dir") as mock_mf:
                            with patch("dochris.cli.cli_utils.get_logs_dir") as mock_log:
                                with patch("dochris.cli.cli_utils.get_all_manifests", return_value=manifests):
                                    with patch("builtins.print"):
                                        mock_s.return_value = MagicMock(
                                            source_path=None,
                                            obsidian_vaults=[],
                                            api_key="test-key-long-value",
                                            api_base="https://api.test.com",
                                            model="test-model",
                                            max_concurrency=3,
                                            min_quality_score=85,
                                            max_content_chars=20000,
                                        )
                                        for p in [mock_raw, mock_out, mock_wiki, mock_mf, mock_log]:
                                            p.return_value = MagicMock(exists=lambda: True, is_dir=lambda: True, rglob=lambda pat: [])

                                        rc = show_status(Path("/test"))
        assert rc == 0

    def test_with_existing_dirs_having_files(self):
        """目录存在且有 .md 文件"""
        mock_dir = MagicMock()
        mock_dir.exists.return_value = True
        mock_dir.is_dir.return_value = True
        mock_dir.rglob.return_value = [MagicMock(is_file=lambda: True)]

        with patch("dochris.cli.cli_utils.get_settings") as mock_s:
            with patch("dochris.cli.cli_utils.get_raw_dir", return_value=mock_dir):
                with patch("dochris.cli.cli_utils.get_outputs_dir", return_value=mock_dir):
                    with patch("dochris.cli.cli_utils.get_wiki_dir", return_value=mock_dir):
                        with patch("dochris.cli.cli_utils.get_manifests_dir", return_value=mock_dir):
                            with patch("dochris.cli.cli_utils.get_logs_dir", return_value=mock_dir):
                                with patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]):
                                    with patch("builtins.print"):
                                        mock_s.return_value = MagicMock(
                                            source_path=None,
                                            obsidian_vaults=[],
                                            api_key="test-key-long-value",
                                            api_base="https://api.test.com",
                                            model="test-model",
                                            max_concurrency=3,
                                            min_quality_score=85,
                                            max_content_chars=20000,
                                        )

                                        rc = show_status(Path("/test"))
        assert rc == 0


class TestFormatFunctions:
    """覆盖 format_error 和 format_warning"""

    def test_format_error_with_hint(self):
        result = format_error("ctx", "msg", "hint here")
        assert "msg" in result
        assert "hint here" in result

    def test_format_error_without_hint(self):
        result = format_error("ctx", "msg")
        assert "msg" in result
        assert "hint" not in result

    def test_format_warning_with_hint(self):
        result = format_warning("ctx", "msg", "fix this")
        assert "msg" in result
        assert "fix this" in result

    def test_format_warning_without_hint(self):
        result = format_warning("ctx", "msg")
        assert "msg" in result
