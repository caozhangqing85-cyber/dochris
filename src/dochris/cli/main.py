#!/usr/bin/env python3
"""
dochris CLI 主入口

提供统一的命令行接口访问所有知识库功能。

Usage:
    kb init                       # 初始化工作区
    kb doctor                     # 环境诊断
    kb ingest [path]              # Phase 1: 摄入文件
    kb compile [limit]            # Phase 2: 编译
    kb query "关键词" [options]    # Phase 3: 查询
    kb status                     # 显示状态概览
    kb promote <src_id> --to <target>  # Promote 操作
    kb quality [--report]         # 质量检查
    kb vault <subcommand>         # Obsidian 联动
    kb config                     # 显示当前配置
    kb version                    # 显示版本
    kb --completion bash          # 生成 shell 补全脚本
"""

import argparse
import atexit
import logging
import sys
import traceback
from typing import Literal

from dochris import __version__

# 导入命令模块
from dochris.cli.cli_compile import cmd_compile
from dochris.cli.cli_config import cmd_config, cmd_version
from dochris.cli.cli_doctor import cmd_doctor
from dochris.cli.cli_ingest import cmd_ingest
from dochris.cli.cli_init import cmd_init
from dochris.cli.cli_query import cmd_query
from dochris.cli.cli_review import cmd_promote, cmd_quality, cmd_status
from dochris.cli.cli_utils import (
    EXIT_CONFIG_ERROR,
    EXIT_FAILURE,
    EXIT_NETWORK_ERROR,
    EXIT_USAGE_ERROR,
    format_error,
)
from dochris.cli.cli_vault import cmd_vault
from dochris.exceptions import (
    APIKeyError,
    ConfigurationError,
    FileProcessingError,
    KnowledgeBaseError,
    LLMConnectionError,
    LLMContentFilterError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from dochris.settings import get_settings

logger = logging.getLogger(__name__)


def completion_script(shell: Literal["bash", "zsh", "fish"]) -> str:
    """生成 shell 补全脚本

    Args:
        shell: shell 类型（bash/zsh/fish）

    Returns:
        补全脚本内容
    """
    if shell == "bash":
        return """# kb bash 补全脚本
_kb_completion() {
    local cur prev words cword
    _init_completion || return

    # 一级命令
    local commands="init doctor ingest compile query status promote quality vault config version"

    # vault 子命令
    local vault_commands="seed push status"

    # promote --to 选项
    local promote_targets="wiki curated obsidian"

    # query --mode 选项
    local query_modes="concept summary vector combined all"

    case "${prev}" in
        kb)
            COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
            ;;
        vault)
            COMPREPLY=($(compgen -W "${vault_commands}" -- "${cur}"))
            ;;
        promote)
            COMPREPLY=($(compgen -W "SRC-" -- "${cur}"))
            _kb_complete_src_ids
            ;;
        --to)
            if __kb_is_promote_command; then
                COMPREPLY=($(compgen -W "${promote_targets}" -- "${cur}"))
            fi
            ;;
        --mode)
            COMPREPLY=($(compgen -W "${query_modes}" -- "${cur}"))
            ;;
        *)
            case "${words[1]}" in
                promote)
                    if [[ "${cur}" == --* ]]; then
                        COMPREPLY=($(compgen -W "--to" -- "${cur}"))
                    fi
                    ;;
                compile)
                    COMPREPLY=($(compgen -W "--limit --concurrency --openrouter --dry-run" -- "${cur}"))
                    ;;
                query)
                    COMPREPLY=($(compgen -W "--mode --top-k" -- "${cur}"))
                    ;;
                quality)
                    COMPREPLY=($(compgen -W "--report --fix" -- "${cur}"))
                    ;;
                vault)
                    case "${words[2]}" in
                        seed)
                            COMPREPLY=($(compgen -W "--limit" -- "${cur}"))
                            ;;
                    esac
                    ;;
                ingest)
                    COMPREPLY=($(compgen -W "--dry-run" -- "${cur}"))
                    COMPREPLY+=($(compgen -f -- "${cur}"))
                    ;;
            esac
            ;;
    esac
}

_kb_is_promote_command() {
    local i
    for ((i=1; i<COMP_CWORD; i++)); do
        if [[ "${COMP_WORDS[i]}" == "promote" ]]; then
            return 0
        fi
    done
    return 1
}

_kb_complete_src_ids() {
    local workspace="${WORKSPACE:-${HOME}/.knowledge-base}"
    local manifest_dir="${workspace}/manifests/sources"
    if [[ -d "${manifest_dir}" ]]; then
        local ids=($(compgen -W "$(ls ${manifest_dir} 2>/dev/null | grep -o 'SRC-[0-9]*')" -- "${cur}"))
        COMPREPLY+=("${ids[@]}")
    fi
}

complete -F _kb_completion kb
"""
    elif shell == "zsh":
        return """# kb zsh 补全脚本
#compdef kb

_kb() {
    local -a commands subcommands vault_commands promote_targets query_modes

    commands=(
        'init:初始化工作区'
        'doctor:环境诊断'
        'ingest:Phase 1 摄入文件'
        'compile:Phase 2 编译文档'
        'query:Phase 3 查询知识库'
        'status:显示系统状态'
        'promote:Promote 操作'
        'quality:质量管理'
        'vault:Obsidian 联动'
        'config:显示配置'
        'version:显示版本'
    )

    vault_commands=(
        'seed:从 Obsidian 拉取笔记'
        'push:推送知识到 Obsidian'
        'status:显示同步状态'
    )

    promote_targets=(wiki curated obsidian)
    query_modes=(concept summary vector combined all)

    case $state in
        command)
            _describe 'command' commands
            ;;
        vault_command)
            _describe 'vault command' vault_commands
            ;;
        promote_target)
            _describe 'target' promote_targets
            ;;
        query_mode)
            _describe 'mode' query_modes
            ;;
    esac
}

_kb "$@"
"""
    else:  # fish
        return """# kb fish 补全脚本
complete -c kb -f

complete -c kb -n __fish_use_subcommand -a init -d "初始化工作区"
complete -c kb -n __fish_use_subcommand -a doctor -d "环境诊断"
complete -c kb -n __fish_use_subcommand -a ingest -d "Phase 1: 摄入文件"
complete -c kb -n __fish_use_subcommand -a compile -d "Phase 2: 编译文档"
complete -c kb -n __fish_use_subcommand -a query -d "Phase 3: 查询知识库"
complete -c kb -n __fish_use_subcommand -a status -d "显示系统状态"
complete -c kb -n __fish_use_subcommand -a promote -d "Promote 操作"
complete -c kb -n __fish_use_subcommand -a quality -d "质量管理"
complete -c kb -n __fish_use_subcommand -a config -d "显示配置"
complete -c kb -n __fish_use_subcommand -a version -d "显示版本"

# vault 子命令
complete -c kb -n "__fish_seen_subcommand_from vault" -a seed -d "从 Obsidian 拉取笔记"
complete -c kb -n "__fish_seen_subcommand_from vault" -a push -d "推送知识到 Obsidian"
complete -c kb -n "__fish_seen_subcommand_from vault" -a status -d "显示同步状态"

# promote 选项
complete -c kb -n "__fish_seen_subcommand_from promote" -l to -k -a "wiki curated obsidian"

# query 选项
complete -c kb -n "__fish_seen_subcommand_from query" -l mode -k -a "concept summary vector combined all"
complete -c kb -n "__fish_seen_subcommand_from query" -l top-k

# compile 选项
complete -c kb -n "__fish_seen_subcommand_from compile" -l limit
complete -c kb -n "__fish_seen_subcommand_from compile" -l concurrency
complete -c kb -n "__fish_seen_subcommand_from compile" -l openrouter
complete -c kb -n "__fish_seen_subcommand_from compile" -l dry-run

# quality 选项
complete -c kb -n "__fish_seen_subcommand_from quality" -l report
complete -c kb -n "__fish_seen_subcommand_from quality" -l fix

# ingest 选项
complete -c kb -n "__fish_seen_subcommand_from ingest" -l dry-run
"""


def _setup_logging(settings) -> None:
    """配置统一的日志格式和级别

    Args:
        settings: Settings 实例
    """
    # 获取日志级别
    log_level_str = settings.log_level.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # 设置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有处理器
    root_logger.handlers.clear()

    # 创建控制台处理器
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(log_level)

    # 设置格式
    formatter = logging.Formatter(
        settings.log_format,
        datefmt=settings.log_date_format,
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)


def main() -> int:
    """主入口函数

    Returns:
        退出码（0 表示成功，非 0 表示错误）
    """
    # 注册资源清理函数（在程序退出时自动调用）
    from dochris.core.llm_client import cleanup_all_clients

    atexit.register(cleanup_all_clients)

    # 获取配置
    settings = get_settings()

    # 配置日志
    _setup_logging(settings)

    # 验证配置
    try:
        warnings = settings.validate()
        for warning in warnings:
            logger.warning(f"配置警告: {warning}")
    except ValueError as e:
        print(format_error("配置验证", str(e), hint="运行 'kb init' 重新配置"))
        return EXIT_CONFIG_ERROR

    parser = argparse.ArgumentParser(
        prog="kb",
        description="dochris: 个人知识库编译系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  kb init                             # 初始化工作区
  kb ingest                           # 摄入文件（使用默认源目录）
  kb ingest /path/to/materials        # 从指定目录摄入
  kb compile                          # 编译所有待编译文档
  kb compile 10                       # 编译前 10 个
  kb compile --concurrency 4          # 使用 4 个并发编译
  kb query "费曼技巧"                 # 查询知识库
  kb query "深度学习" --mode concept  # 仅搜索概念
  kb status                           # 显示系统状态
  kb promote SRC-0001 --to wiki       # 晋升到 wiki
  kb quality --report                 # 生成质量报告
  kb vault seed "财富自由"            # 从 Obsidian 拉取笔记
  kb config                           # 显示当前配置
  kb version                          # 显示版本
        """,
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细输出")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式，仅输出错误信息")
    parser.add_argument("--version", action="store_true", help="显示版本信息")
    parser.add_argument(
        "--completion",
        choices=["bash", "zsh", "fish"],
        help="生成 shell 补全脚本",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="可用命令",
        description="知识库管理命令",
        help="使用 <command> -h 查看具体帮助",
    )

    # init 命令
    subparsers.add_parser(
        "init",
        help="初始化工作区",
        description="交互式初始化知识库工作区，创建目录结构和配置文件",
    )

    # doctor 命令
    subparsers.add_parser(
        "doctor",
        help="环境诊断",
        description="检查系统环境、配置和依赖，诊断潜在问题",
    )

    # ingest 命令
    parser_ingest = subparsers.add_parser(
        "ingest",
        help="Phase 1: 摄入文件",
        description="扫描源目录，创建 manifest，将文件链接到 raw/",
    )
    parser_ingest.add_argument(
        "path", nargs="?", default=None, help="源目录路径（默认使用配置中的 SOURCE_PATH）"
    )
    parser_ingest.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行，只显示将要执行的操作",
    )

    # compile 命令
    parser_compile = subparsers.add_parser(
        "compile",
        help="Phase 2: 编译文档",
        description="使用 LLM 编译已摄入的文档，输出到 outputs/",
    )
    parser_compile.add_argument(
        "limit",
        nargs="?",
        type=int,
        default=None,
        help="[已弃用，请使用 --limit] 编译数量限制（默认编译所有）",
    )
    parser_compile.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        dest="named_limit",
        help="编译数量限制（默认编译所有）",
    )
    parser_compile.add_argument(
        "--concurrency",
        type=int,
        default=settings.max_concurrency,
        help=f"并发数（默认: {settings.max_concurrency}）",
    )
    parser_compile.add_argument(
        "--openrouter", action="store_true", help="使用 OpenRouter 免费模型"
    )
    parser_compile.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行，只显示将要执行的操作",
    )

    # query 命令
    parser_query = subparsers.add_parser(
        "query", help="Phase 3: 查询知识库", description="在 wiki/ 和 outputs/ 中搜索相关内容"
    )
    parser_query.add_argument("query", nargs="?", help="查询关键词（不提供则进入交互模式）")
    parser_query.add_argument(
        "--mode",
        choices=["concept", "summary", "vector", "combined", "all"],
        default="combined",
        help="查询模式（默认: combined）",
    )
    parser_query.add_argument("--top-k", type=int, default=5, help="返回结果数量（默认: 5）")

    # status 命令
    subparsers.add_parser(
        "status", help="显示系统状态", description="显示工作区、manifest、API 配置等状态概览"
    )

    # promote 命令
    parser_promote = subparsers.add_parser(
        "promote", help="Promote 操作", description="将内容晋升到更高信任层级"
    )
    parser_promote.add_argument("src_id", help="来源 ID（如 SRC-0001）")
    parser_promote.add_argument(
        "--to", choices=["wiki", "curated", "obsidian"], required=True, help="目标层级"
    )

    # quality 命令
    parser_quality = subparsers.add_parser(
        "quality", help="质量管理", description="检查和报告知识库质量"
    )
    parser_quality.add_argument("--report", action="store_true", help="生成详细报告")
    parser_quality.add_argument("--fix", action="store_true", help="自动修复可修复的问题")

    # vault 命令
    parser_vault = subparsers.add_parser(
        "vault", help="Obsidian 联动", description="与 Obsidian vault 同步"
    )
    vault_subparsers = parser_vault.add_subparsers(dest="vault_command")
    parser_vault_seed = vault_subparsers.add_parser("seed", help="从 Obsidian 拉取笔记")
    parser_vault_seed.add_argument("topic", help="主题关键词")
    parser_vault_seed.add_argument("--limit", type=int, default=5, help="拉取数量")
    vault_subparsers.add_parser("push", help="推送知识到 Obsidian")
    vault_subparsers.add_parser("status", help="显示同步状态")

    # config 命令
    subparsers.add_parser("config", help="显示配置", description="显示当前配置信息")

    # version 命令
    subparsers.add_parser("version", help="显示版本", description="显示版本信息")

    # 解析参数
    args = parser.parse_args()

    # 处理 --completion 参数（在 --version 之前，因为这会直接退出）
    if hasattr(args, "completion") and args.completion:
        print(completion_script(args.completion))
        return 0

    # 处理 --version 参数
    if args.version:
        print(f"dochris {__version__}")
        return 0

    # 如果没有提供命令，显示帮助
    if not args.command:
        parser.print_help()
        return 0

    # 路由到对应的命令处理器
    try:
        if args.command == "init":
            return cmd_init(args)
        elif args.command == "doctor":
            return cmd_doctor(args)
        elif args.command == "ingest":
            return cmd_ingest(args)
        elif args.command == "compile":
            return cmd_compile(args)
        elif args.command == "query":
            return cmd_query(args)
        elif args.command == "status":
            return cmd_status(args)
        elif args.command == "promote":
            return cmd_promote(args)
        elif args.command == "quality":
            return cmd_quality(args)
        elif args.command == "vault":
            return cmd_vault(args)
        elif args.command == "config":
            return cmd_config(args)
        elif args.command == "version":
            return cmd_version(args)
        else:
            print(
                format_error(
                    "命令", f"未知命令: {args.command}", hint="运行 'kb --help' 查看所有可用命令"
                )
            )
            return EXIT_USAGE_ERROR
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except APIKeyError as e:
        print(
            format_error(
                "API 配置", str(e), hint="请检查 OPENAI_API_KEY 环境变量或运行 'kb init' 重新配置"
            )
        )
        return EXIT_CONFIG_ERROR
    except ConfigurationError as e:
        print(
            format_error(
                "配置错误", str(e), hint="运行 'kb config' 查看当前配置，或 'kb init' 重新配置"
            )
        )
        return EXIT_CONFIG_ERROR
    except (LLMConnectionError, LLMTimeoutError) as e:
        print(format_error("网络连接", str(e), hint="请检查网络连接和 API_BASE 配置"))
        return EXIT_NETWORK_ERROR
    except LLMRateLimitError as e:
        print(format_error("API 限流", str(e), hint="请稍后重试或调整并发数"))
        return EXIT_NETWORK_ERROR
    except LLMContentFilterError as e:
        print(format_error("内容过滤", str(e), hint="源内容可能包含敏感词，请检查源文件"))
        return EXIT_FAILURE
    except LLMError as e:
        print(format_error("LLM 调用", str(e), hint="请检查 API 配置和网络连接"))
        return EXIT_FAILURE
    except FileProcessingError as e:
        print(format_error("文件处理", str(e), hint="请检查文件是否存在且可读"))
        return EXIT_FAILURE
    except KnowledgeBaseError as e:
        print(format_error("知识库系统", str(e)))
        return EXIT_FAILURE
    except Exception as e:
        print(format_error("未知错误", str(e)))
        if args.verbose:
            traceback.print_exc()
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
