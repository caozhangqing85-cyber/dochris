"""CLI 命令：配置、版本"""

import argparse

from dochris.cli.cli_utils import bold, dim, error, info, success
from dochris.settings import get_settings


def cmd_config(args: argparse.Namespace) -> int:
    """显示当前配置"""
    print(f"\n{info('知识库配置')}")
    print(f"{'=' * 40}")

    _s = get_settings()
    print(f"\n{bold('路径配置:')}")
    print(f"  工作区: {_s.workspace}")
    print(f"  日志目录: {_s.logs_dir}")
    print(f"  Wiki 目录: {_s.wiki_dir}")
    print(f"  输出目录: {_s.outputs_dir}")

    print(f"\n{bold('源配置:')}")
    print(f"  主源目录: {_s.source_path or dim('未配置')}")
    print(f"  Obsidian Vaults: {len(_s.obsidian_vaults) if _s.obsidian_vaults else 0} 个")
    if _s.obsidian_vaults:
        print(f"    主 Vault: {_s.obsidian_vaults[0]}")

    print(f"\n{bold('API 配置:')}")
    if _s.api_key:
        masked = f"...{_s.api_key[-6:]}" if len(_s.api_key) > 6 else "***"
        print(f"  API Key: {success('已配置')} ({masked})")
    else:
        print(f"  API Key: {error('未配置')}")
    print(f"  Base URL: {_s.api_base}")
    print(f"  模型: {_s.model}")

    print(f"\n{bold('编译配置:')}")
    print(f"  并发数: {_s.max_concurrency}")
    print(f"  质量门槛: {_s.min_quality_score}")
    print(f"  最大内容: {_s.max_content_chars} 字符")

    print()
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """显示版本"""
    print("\n知识库编译系统 v1.0.0")
    print("统一 CLI 入口")
    print(f"工作区: {get_settings().workspace}")
    print()
    return 0
