"""CLI 命令测试

测试 CLI 参数解析、命令分发逻辑。
使用 mock 隔离所有外部依赖（文件系统、LLM 调用等）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# TestCLIMain
# ============================================================


class TestCLIMain:
    """测试主入口 main() 函数"""

    def test_main_no_args_returns_zero(self):
        """无子命令时返回 0（显示帮助）"""
        from dochris.cli.main import main

        with patch("sys.argv", ["kb"]):
            rc = main()
        assert rc == 0

    def test_main_version_flag(self):
        """--version 标志打印版本并返回 0"""
        from dochris.cli.main import main

        with patch("sys.argv", ["kb", "--version"]), patch("builtins.print") as mock_print:
            rc = main()
        assert rc == 0
        mock_print.assert_called_once()
        assert "1.2.0" in mock_print.call_args[0][0]

    def test_main_verbose_flag(self):
        """-v 标志不影响命令路由"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_status", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "-v", "status"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()

    def test_main_status_subcommand(self):
        """status 子命令正确分发"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_status", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "status"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()

    def test_main_config_subcommand(self):
        """config 子命令正确分发"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_config", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "config"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()

    def test_main_version_subcommand(self):
        """version 子命令正确分发"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_version", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "version"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()

    def test_main_ingest_subcommand(self):
        """ingest 子命令正确分发"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_ingest", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "ingest"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()

    def test_main_ingest_with_path(self):
        """ingest 子命令接受路径参数"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_ingest", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "ingest", "/path/to/files"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.path == "/path/to/files"

    def test_main_compile_subcommand(self):
        """compile 子命令正确分发"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_compile", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "compile"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()

    def test_main_compile_with_limit(self):
        """compile 子命令接受 limit 参数"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_compile", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "compile", "10"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.limit == 10

    def test_main_compile_with_concurrency(self):
        """compile 子命令接受 --concurrency 参数"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_compile", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "compile", "--concurrency", "5"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.concurrency == 5

    def test_main_query_subcommand(self):
        """query 子命令正确分发"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_query", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "query", "费曼技巧"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()

    def test_main_query_with_mode(self):
        """query 子命令接受 --mode 参数"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_query", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "query", "测试", "--mode", "concept"]):
                rc = main()
        assert rc == 0
        args = mock_cmd.call_args[0][0]
        assert args.mode == "concept"

    def test_main_query_with_top_k(self):
        """query 子命令接受 --top-k 参数"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_query", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "query", "测试", "--top-k", "10"]):
                rc = main()
        assert rc == 0
        args = mock_cmd.call_args[0][0]
        assert args.top_k == 10

    def test_main_promote_subcommand(self):
        """promote 子命令正确分发"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_promote", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "promote", "SRC-0001", "--to", "wiki"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.src_id == "SRC-0001"
        assert args.to == "wiki"

    def test_main_promote_requires_to(self):
        """promote 子命令缺少 --to 参数时报错"""
        from dochris.cli.main import main

        with patch("sys.argv", ["kb", "promote", "SRC-0001"]), pytest.raises(SystemExit):
            main()

    def test_main_quality_subcommand(self):
        """quality 子命令正确分发"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_quality", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "quality"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()

    def test_main_quality_with_report(self):
        """quality 子命令接受 --report 参数"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_quality", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "quality", "--report"]):
                rc = main()
        assert rc == 0
        args = mock_cmd.call_args[0][0]
        assert args.report is True

    def test_main_vault_seed(self):
        """vault seed 子命令正确分发"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_vault", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "vault", "seed", "AI学习"]):
                rc = main()
        assert rc == 0
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.vault_command == "seed"
        assert args.topic == "AI学习"

    def test_main_vault_seed_with_limit(self):
        """vault seed 子命令接受 --limit 参数"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_vault", return_value=0) as mock_cmd:
            with patch("sys.argv", ["kb", "vault", "seed", "AI学习", "--limit", "10"]):
                rc = main()
        assert rc == 0
        args = mock_cmd.call_args[0][0]
        assert args.limit == 10

    def test_main_keyboard_interrupt(self):
        """KeyboardInterrupt 返回 130"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_status", side_effect=KeyboardInterrupt):
            with patch("sys.argv", ["kb", "status"]):
                rc = main()
        assert rc == 130

    def test_main_exception_returns_one(self):
        """命令执行异常时返回 1"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_status", side_effect=RuntimeError("test error")):
            with patch("sys.argv", ["kb", "status"]):
                rc = main()
        assert rc == 1

    def test_main_exception_verbose_shows_traceback(self):
        """verbose 模式下异常时打印 traceback"""
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_status", side_effect=RuntimeError("test")):
            with patch("sys.argv", ["kb", "-v", "status"]):
                with patch("traceback.print_exc") as mock_tb:
                    rc = main()
        assert rc == 1
        mock_tb.assert_called_once()


# ============================================================
# TestCLIUtils
# ============================================================


class TestCLIUtils:
    """测试 CLI 工具函数"""

    def test_success_returns_string(self):
        """success() 返回字符串"""
        from dochris.cli.cli_utils import success

        result = success("ok")
        assert isinstance(result, str)

    def test_error_returns_string(self):
        """error() 返回字符串"""
        from dochris.cli.cli_utils import error

        result = error("fail")
        assert isinstance(result, str)

    def test_warning_returns_string(self):
        """warning() 返回字符串"""
        from dochris.cli.cli_utils import warning

        result = warning("caution")
        assert isinstance(result, str)

    def test_info_returns_string(self):
        """info() 返回字符串"""
        from dochris.cli.cli_utils import info

        result = info("info")
        assert isinstance(result, str)

    def test_bold_returns_string(self):
        """bold() 返回字符串"""
        from dochris.cli.cli_utils import bold

        result = bold("bold")
        assert isinstance(result, str)

    def test_dim_returns_string(self):
        """dim() 返回字符串"""
        from dochris.cli.cli_utils import dim

        result = dim("dim")
        assert isinstance(result, str)

    def test_style_non_tty_returns_plain(self):
        """非 TTY 模式下 style() 返回纯文本"""
        from dochris.cli.cli_utils import Colors, style

        with patch("sys.stdout.isatty", return_value=False):
            result = style("hello", Colors.GREEN)
        assert result == "hello"

    def test_style_tty_includes_color(self):
        """TTY 模式下 style() 包含 ANSI 颜色码"""
        from dochris.cli.cli_utils import Colors, style

        with patch("sys.stdout.isatty", return_value=True):
            result = style("hello", Colors.GREEN)
        assert Colors.GREEN in result
        assert Colors.RESET in result

    def test_show_status_no_workspace(self):
        """show_status 无 workspace 参数时使用默认值"""
        from dochris.cli.cli_utils import show_status

        with patch("dochris.cli.cli_utils.get_default_workspace") as mock_ws:
            with patch("dochris.cli.cli_utils.get_settings") as mock_s:
                with patch("dochris.cli.cli_utils.get_raw_dir") as mock_raw:
                    with patch("dochris.cli.cli_utils.get_outputs_dir") as mock_out:
                        with patch("dochris.cli.cli_utils.get_wiki_dir") as mock_wiki:
                            with patch("dochris.cli.cli_utils.get_manifests_dir") as mock_mf:
                                with patch("dochris.cli.cli_utils.get_logs_dir") as mock_log:
                                    with patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]):
                                        mock_ws.return_value = MagicMock(exists=lambda: True, is_dir=lambda: True, rglob=lambda p: [])
                                        mock_s.return_value = MagicMock(
                                            source_path=None, obsidian_vaults=[],
                                            api_key=None, api_base="http://test", model="test-model",
                                            max_concurrency=3, min_quality_score=85, max_content_chars=20000,
                                        )
                                        for p in [mock_raw, mock_out, mock_wiki, mock_mf, mock_log]:
                                            p.return_value = MagicMock(exists=lambda: True, is_dir=lambda: True, rglob=lambda p: [])
                                        rc = show_status()
        assert rc == 0

    def test_show_status_with_workspace(self):
        """show_status 接受显式 workspace 参数"""
        from pathlib import Path

        from dochris.cli.cli_utils import show_status

        with patch("dochris.cli.cli_utils.get_settings") as mock_s:
            with patch("dochris.cli.cli_utils.get_raw_dir") as mock_raw:
                with patch("dochris.cli.cli_utils.get_outputs_dir") as mock_out:
                    with patch("dochris.cli.cli_utils.get_wiki_dir") as mock_wiki:
                        with patch("dochris.cli.cli_utils.get_manifests_dir") as mock_mf:
                            with patch("dochris.cli.cli_utils.get_logs_dir") as mock_log:
                                with patch("dochris.cli.cli_utils.get_all_manifests", return_value=[]):
                                    mock_s.return_value = MagicMock(
                                        source_path=None, obsidian_vaults=[],
                                        api_key=None, api_base="http://test", model="test-model",
                                        max_concurrency=3, min_quality_score=85, max_content_chars=20000,
                                    )
                                    for p in [mock_raw, mock_out, mock_wiki, mock_mf, mock_log]:
                                        p.return_value = MagicMock(exists=lambda: True, is_dir=lambda: True, rglob=lambda p: [])
                                    ws = Path("/tmp/test-workspace")
                                    rc = show_status(ws)
        assert rc == 0


# ============================================================
# TestCLIConfig
# ============================================================


class TestCLIConfig:
    """测试 config 和 version 命令"""

    def test_cmd_config_returns_zero(self):
        """cmd_config 返回 0"""
        from dochris.cli.cli_config import cmd_config

        with patch("dochris.cli.cli_config.get_settings") as mock_s:
            mock_s.return_value = MagicMock(
                workspace=MagicMock(),
                logs_dir=MagicMock(), wiki_dir=MagicMock(), outputs_dir=MagicMock(),
                source_path=None, obsidian_vaults=[], api_key=None,
                api_base="http://test", model="test-model",
                max_concurrency=3, min_quality_score=85, max_content_chars=20000,
            )
            args = MagicMock()
            rc = cmd_config(args)
        assert rc == 0

    def test_cmd_config_displays_configured_api_key(self):
        """cmd_config 显示已配置的 API Key（脱敏）"""
        from dochris.cli.cli_config import cmd_config

        with patch("dochris.cli.cli_config.get_settings") as mock_s:
            mock_s.return_value = MagicMock(
                workspace=MagicMock(), logs_dir=MagicMock(), wiki_dir=MagicMock(),
                outputs_dir=MagicMock(), source_path=None, obsidian_vaults=[],
                api_key="sk-1234567890abcdef",
                api_base="http://test", model="test-model",
                max_concurrency=3, min_quality_score=85, max_content_chars=20000,
            )
            args = MagicMock()
            with patch("builtins.print") as mock_print:
                rc = cmd_config(args)
        assert rc == 0
        # 验证打印了 API Key（脱敏形式）
        printed = "".join(str(c) for c in mock_print.call_args_list)
        assert "abcdef" in printed

    def test_cmd_version_returns_zero(self):
        """cmd_version 返回 0"""
        from dochris.cli.cli_config import cmd_version

        with patch("dochris.cli.cli_config.get_settings") as mock_s:
            mock_s.return_value = MagicMock(workspace=MagicMock())
            args = MagicMock()
            rc = cmd_version(args)
        assert rc == 0

    def test_cmd_config_with_obsidian_vaults(self):
        """cmd_config 显示 Obsidian Vaults 信息"""
        from pathlib import Path

        from dochris.cli.cli_config import cmd_config

        with patch("dochris.cli.cli_config.get_settings") as mock_s:
            mock_vault_path = Path("/test/vault")
            mock_s.return_value = MagicMock(
                workspace=MagicMock(),
                logs_dir=MagicMock(),
                wiki_dir=MagicMock(),
                outputs_dir=MagicMock(),
                source_path=None,
                obsidian_vaults=[mock_vault_path],  # 有 Obsidian vault
                api_key=None,
                api_base="http://test",
                model="test-model",
                max_concurrency=3,
                min_quality_score=85,
                max_content_chars=20000,
            )
            args = MagicMock()
            with patch("builtins.print") as mock_print:
                rc = cmd_config(args)

        assert rc == 0
        # 验证打印了 Obsidian Vault 信息
        printed = "".join(str(c) for c in mock_print.call_args_list)
        assert "Vault" in printed or "1 个" in printed


# ============================================================
# TestCLICompile
# ============================================================


class TestCLICompile:
    """测试 compile 命令"""

    def test_cmd_compile_success(self):
        """编译成功返回 0"""
        from dochris.cli.cli_compile import cmd_compile

        args = MagicMock(limit=None, concurrency=3, openrouter=False)

        with patch("dochris.phases.phase2_compilation.setup_logging"):
            with patch("asyncio.run", return_value=None):
                with patch("builtins.print"):
                    rc = cmd_compile(args)
        assert rc == 0

    def test_cmd_compile_failure(self):
        """编译失败返回 1"""
        from dochris.cli.cli_compile import cmd_compile

        args = MagicMock(limit=None, concurrency=3, openrouter=False)

        with patch("dochris.phases.phase2_compilation.setup_logging"):
            with patch("asyncio.run", side_effect=Exception("API error")):
                rc = cmd_compile(args)
        assert rc == 1

    def test_cmd_compile_with_limit(self):
        """compile 命令传递 limit 参数"""
        from dochris.cli.cli_compile import cmd_compile

        args = MagicMock(limit=5, concurrency=3, openrouter=False)

        with patch("dochris.phases.phase2_compilation.setup_logging"):
            with patch("asyncio.run") as mock_run:
                with patch("builtins.print"):
                    mock_run.return_value = None
                    rc = cmd_compile(args)
        assert rc == 0
        mock_run.assert_called_once()

    def test_cmd_compile_openrouter(self):
        """compile 命令传递 openrouter 参数"""
        from dochris.cli.cli_compile import cmd_compile

        args = MagicMock(limit=None, concurrency=3, openrouter=True)

        with patch("dochris.phases.phase2_compilation.setup_logging"):
            with patch("asyncio.run") as mock_run:
                with patch("builtins.print"):
                    mock_run.return_value = None
                    rc = cmd_compile(args)
        assert rc == 0


# ============================================================
# TestCLIIngest
# ============================================================


class TestCLIIngest:
    """测试 ingest 命令"""

    def test_cmd_ingest_success(self):
        """摄入成功返回 0"""
        from dochris.cli.cli_ingest import cmd_ingest

        args = MagicMock()

        with patch("dochris.phases.phase1_ingestion.setup_logging"):
            with patch("dochris.phases.phase1_ingestion.run_phase1", return_value={
                "total": 10, "linked": 5, "skipped": 5,
            }) as mock_run:
                with patch("builtins.print"):
                    rc = cmd_ingest(args)
        assert rc == 0
        mock_run.assert_called_once()

    def test_cmd_ingest_failure(self):
        """摄入失败返回 1"""
        from dochris.cli.cli_ingest import cmd_ingest

        args = MagicMock()

        with patch("dochris.phases.phase1_ingestion.setup_logging"):
            with patch("dochris.phases.phase1_ingestion.run_phase1", side_effect=Exception("fail")):
                rc = cmd_ingest(args)
        assert rc == 1


# ============================================================
# TestCLIQuery
# ============================================================


class TestCLIQuery:
    """测试 query 命令"""

    def test_cmd_query_single_returns_zero_with_answer(self):
        """单次查询有结果时返回 0"""
        from dochris.cli.cli_query import cmd_query

        args = MagicMock(query="测试", mode="combined", top_k=5)

        mock_logger = MagicMock()
        with patch("dochris.phases.phase3_query.setup_logging", return_value=mock_logger):
            with patch("dochris.phases.phase3_query.query", return_value={
                "answer": "结果内容",
            }) as mock_query:
                with patch("dochris.phases.phase3_query.print_result"):
                    rc = cmd_query(args)
        assert rc == 0
        mock_query.assert_called_once_with("测试", mode="combined", top_k=5, logger=mock_logger)

    def test_cmd_query_single_returns_one_without_answer(self):
        """单次查询无结果时返回 1"""
        from dochris.cli.cli_query import cmd_query

        args = MagicMock(query="测试", mode="combined", top_k=5)

        with patch("dochris.phases.phase3_query.setup_logging"):
            with patch("dochris.phases.phase3_query.query", return_value={}):
                with patch("dochris.phases.phase3_query.print_result"):
                    rc = cmd_query(args)
        assert rc == 1

    def test_cmd_query_interactive_mode(self):
        """无查询关键词时进入交互模式"""
        from dochris.cli.cli_query import cmd_query

        args = MagicMock(query=None, mode=None, top_k=5)

        with patch("dochris.phases.phase3_query.setup_logging"):
            with patch("dochris.phases.phase3_query.interactive_mode") as mock_interactive:
                rc = cmd_query(args)
        assert rc == 0
        mock_interactive.assert_called_once()


# ============================================================
# TestCLIReview
# ============================================================


class TestCLIReview:
    """测试 status、promote、quality 命令"""

    def test_cmd_status_returns_zero(self):
        """status 命令返回 0"""
        from dochris.cli.cli_review import cmd_status

        args = MagicMock()
        with patch("dochris.cli.cli_utils.show_status", return_value=0):
            rc = cmd_status(args)
        assert rc == 0

    def test_cmd_promote_to_wiki_success(self):
        """promote to wiki 成功返回 0"""
        from dochris.cli.cli_review import cmd_promote

        args = MagicMock(src_id="SRC-001", to="wiki")
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": True, "quality_score": 90}),
            patch("dochris.promote.promote_to_wiki", return_value=True),
            patch("builtins.print"),
        ):
            rc = cmd_promote(args)
        assert rc == 0

    def test_cmd_promote_quality_gate_fails(self):
        """质量门禁未通过返回 1"""
        from dochris.cli.cli_review import cmd_promote

        args = MagicMock(src_id="SRC-001", to="wiki")
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": False, "reason": "低质量"}),
            patch("builtins.print"),
        ):
            rc = cmd_promote(args)
        assert rc == 1

    def test_cmd_promote_to_curated(self):
        """promote to curated"""
        from dochris.cli.cli_review import cmd_promote

        args = MagicMock(src_id="SRC-001", to="curated")
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": True, "quality_score": 90}),
            patch("dochris.promote.promote_to_curated", return_value=True),
            patch("builtins.print"),
        ):
            rc = cmd_promote(args)
        assert rc == 0

    def test_cmd_promote_to_obsidian(self):
        """promote to obsidian"""
        from dochris.cli.cli_review import cmd_promote

        args = MagicMock(src_id="SRC-001", to="obsidian")
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.quality_gate", return_value={"passed": True, "quality_score": 90}),
            patch("dochris.vault.bridge.promote_to_obsidian", return_value=True),
            patch("builtins.print"),
        ):
            rc = cmd_promote(args)
        assert rc == 0

    def test_cmd_quality_scan_wiki(self):
        """quality 默认扫描 wiki"""
        from dochris.cli.cli_review import cmd_quality

        args = MagicMock(report=False, check_pollution=False, src_id=None)
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.scan_wiki", return_value={"wiki_summaries": 10, "wiki_concepts": 5, "wiki_total": 15}),
            patch("builtins.print"),
        ):
            rc = cmd_quality(args)
        assert rc == 0

    def test_cmd_quality_with_src_id_passed(self):
        """quality 带 src_id 参数，质量门禁通过"""
        from dochris.cli.cli_review import cmd_quality

        args = MagicMock(report=False, check_pollution=False, src_id="SRC-0001")
        mock_gate_result = {
            "passed": True,
            "src_id": "SRC-0001",
            "title": "Test Document",
            "quality_score": 90,
        }
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.quality_gate", return_value=mock_gate_result),
            patch("builtins.print"),
        ):
            rc = cmd_quality(args)
        assert rc == 0

    def test_cmd_quality_with_src_id_failed(self):
        """quality 带 src_id 参数，质量门禁未通过"""
        from dochris.cli.cli_review import cmd_quality

        args = MagicMock(report=False, check_pollution=False, src_id="SRC-0001")
        mock_gate_result = {
            "passed": False,
            "reason": "质量分数不足",
        }
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.quality_gate", return_value=mock_gate_result),
            patch("builtins.print"),
        ):
            rc = cmd_quality(args)
        assert rc == 1


class TestCLIVault:
    """测试 vault 命令"""

    def test_cmd_vault_seed_success(self):
        """vault seed 成功返回 0"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="seed", topic="AI")

        mock_seed = MagicMock(return_value=[{"title": "t1"}])
        mock_settings = MagicMock(return_value=MagicMock())

        with patch("dochris.cli.cli_vault.get_default_workspace", mock_settings):
            with patch.dict("sys.modules", {
                "dochris.vault.bridge": MagicMock(seed_from_obsidian=mock_seed),
            }):
                with patch("builtins.print"):
                    rc = cmd_vault(args)
        assert rc == 0

    def test_cmd_vault_seed_no_results(self):
        """vault seed 无结果返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="seed", topic="AI")

        mock_seed = MagicMock(return_value=[])
        mock_settings = MagicMock(return_value=MagicMock())

        with patch("dochris.cli.cli_vault.get_default_workspace", mock_settings):
            with patch.dict("sys.modules", {
                "dochris.vault.bridge": MagicMock(seed_from_obsidian=mock_seed),
            }):
                with patch("builtins.print"):
                    rc = cmd_vault(args)
        assert rc == 1

    def test_cmd_vault_seed_no_topic(self):
        """vault seed 缺少 topic 参数返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="seed", topic=None)

        with patch("builtins.print"):
            rc = cmd_vault(args)
        assert rc == 1

    def test_cmd_vault_promote_success(self):
        """vault promote 成功返回 0"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="promote", src_id="SRC-0001")

        mock_promote = MagicMock(return_value=True)
        mock_settings = MagicMock(return_value=MagicMock())

        with patch("dochris.cli.cli_vault.get_default_workspace", mock_settings):
            with patch.dict("sys.modules", {
                "dochris.vault.bridge": MagicMock(promote_to_obsidian=mock_promote),
            }):
                with patch("builtins.print"):
                    rc = cmd_vault(args)
        assert rc == 0

    def test_cmd_vault_promote_no_src_id(self):
        """vault promote 缺少 src_id 返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="promote", src_id=None)

        with patch("builtins.print"):
            rc = cmd_vault(args)
        assert rc == 1

    def test_cmd_vault_promote_failed(self):
        """vault promote 失败返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="promote", src_id="SRC-0001")

        mock_promote = MagicMock(return_value=False)
        mock_settings = MagicMock(return_value=MagicMock())

        with patch("dochris.cli.cli_vault.get_default_workspace", mock_settings):
            with patch.dict("sys.modules", {
                "dochris.vault.bridge": MagicMock(promote_to_obsidian=mock_promote),
            }):
                with patch("builtins.print"):
                    rc = cmd_vault(args)
        assert rc == 1

    def test_cmd_vault_list_success(self):
        """vault list 成功返回 0"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="list", src_id="SRC-0001")

        mock_list = MagicMock(return_value=[{"title": "t1"}])
        mock_settings = MagicMock(return_value=MagicMock())

        with patch("dochris.cli.cli_vault.get_default_workspace", mock_settings):
            with patch.dict("sys.modules", {
                "dochris.vault.bridge": MagicMock(list_associated_notes=mock_list),
            }):
                with patch("builtins.print"):
                    rc = cmd_vault(args)
        assert rc == 0

    def test_cmd_vault_list_no_notes(self):
        """vault list 无关联笔记返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="list", src_id="SRC-0001")

        mock_list = MagicMock(return_value=[])
        mock_settings = MagicMock(return_value=MagicMock())

        with patch("dochris.cli.cli_vault.get_default_workspace", mock_settings):
            with patch.dict("sys.modules", {
                "dochris.vault.bridge": MagicMock(list_associated_notes=mock_list),
            }):
                with patch("builtins.print"):
                    rc = cmd_vault(args)
        assert rc == 1

    def test_cmd_vault_list_no_src_id(self):
        """vault list 缺少 src_id 返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="list", src_id=None)

        with patch("builtins.print"):
            rc = cmd_vault(args)
        assert rc == 1

    def test_cmd_vault_unknown_subcommand(self):
        """未知 vault 子命令返回 1"""
        from dochris.cli.cli_vault import cmd_vault

        args = MagicMock(vault_command="unknown")

        with patch("builtins.print"):
            rc = cmd_vault(args)
        assert rc == 1


class TestCLIQualityPollution:
    """测试 quality 命令污染检查"""

    def test_cmd_quality_check_pollution_clean(self):
        """quality 检查污染，干净返回 0"""
        from dochris.cli.cli_review import cmd_quality

        args = MagicMock(report=False, check_pollution=True, src_id=None)
        mock_result = {"polluted": False}
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.check_pollution", return_value=mock_result),
            patch("builtins.print"),
        ):
            rc = cmd_quality(args)
        assert rc == 0

    def test_cmd_quality_check_pollution_dirty(self):
        """quality 检查污染，发现污染返回 1"""
        from dochris.cli.cli_review import cmd_quality

        args = MagicMock(report=False, check_pollution=True, src_id=None)
        mock_result = {"polluted": True, "details": "发现重复文件"}
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.check_pollution", return_value=mock_result),
            patch("builtins.print"),
        ):
            rc = cmd_quality(args)
        assert rc == 1
        """quality 检查污染，发现污染返回 1"""
        from dochris.cli.cli_review import cmd_quality

        args = MagicMock(report=False, check_pollution=True, src_id=None)
        mock_result = {"polluted": True, "details": "发现重复文件"}
        with (
            patch("dochris.cli.cli_review.get_default_workspace", return_value=MagicMock()),
            patch("dochris.quality.quality_gate.check_pollution", return_value=mock_result),
            patch("builtins.print"),
        ):
            rc = cmd_quality(args)
        assert rc == 1
