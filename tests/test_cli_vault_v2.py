"""测试 cli/cli_vault.py 模块"""

import argparse
from unittest.mock import patch


class TestCmdVault:
    """测试 cmd_vault 函数"""

    def _make_args(self, vault_command="seed", topic=None, src_id=None):
        return argparse.Namespace(vault_command=vault_command, topic=topic, src_id=src_id)

    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_seed_without_topic_returns_1(self, mock_print, mock_ws):
        """seed 缺少 topic 返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="seed", topic=None)
        result = cmd_vault(args)
        assert result == 1

    @patch("dochris.vault.bridge.seed_from_obsidian", return_value=["note1", "note2"])
    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_seed_with_results(self, mock_print, mock_ws, mock_seed):
        """seed 有结果返回 0"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="seed", topic="Python")
        result = cmd_vault(args)
        assert result == 0
        mock_seed.assert_called_once_with("/fake/ws", "Python")

    @patch("dochris.vault.bridge.seed_from_obsidian", return_value=[])
    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_seed_no_results(self, mock_print, mock_ws, mock_seed):
        """seed 无结果返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="seed", topic="unknown")
        result = cmd_vault(args)
        assert result == 1

    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_promote_without_src_id(self, mock_print, mock_ws):
        """promote 缺少 src_id 返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="promote", src_id=None)
        result = cmd_vault(args)
        assert result == 1

    @patch("dochris.vault.bridge.promote_to_obsidian", return_value=True)
    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_promote_success(self, mock_print, mock_ws, mock_promote):
        """promote 成功返回 0"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="promote", src_id="SRC-0001")
        result = cmd_vault(args)
        assert result == 0

    @patch("dochris.vault.bridge.promote_to_obsidian", return_value=False)
    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_promote_failure(self, mock_print, mock_ws, mock_promote):
        """promote 失败返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="promote", src_id="SRC-0001")
        result = cmd_vault(args)
        assert result == 1

    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_list_without_src_id(self, mock_print, mock_ws):
        """list 缺少 src_id 返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="list", src_id=None)
        result = cmd_vault(args)
        assert result == 1

    @patch("dochris.vault.bridge.list_associated_notes", return_value=["note1"])
    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_list_with_notes(self, mock_print, mock_ws, mock_list):
        """list 有笔记返回 0"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="list", src_id="SRC-0001")
        result = cmd_vault(args)
        assert result == 0

    @patch("dochris.vault.bridge.list_associated_notes", return_value=[])
    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_list_empty(self, mock_print, mock_ws, mock_list):
        """list 无笔记返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="list", src_id="SRC-0001")
        result = cmd_vault(args)
        assert result == 1

    @patch("dochris.cli.cli_vault.get_default_workspace", return_value="/fake/ws")
    @patch("dochris.cli.cli_vault.print")
    def test_unknown_command(self, mock_print, mock_ws):
        """未知子命令返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = self._make_args(vault_command="invalid_cmd")
        result = cmd_vault(args)
        assert result == 1
