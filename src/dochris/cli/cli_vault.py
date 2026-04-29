"""CLI 命令：Obsidian 联动"""

import argparse

from dochris.cli.cli_utils import error, success
from dochris.settings import get_default_workspace


def cmd_vault(args: argparse.Namespace) -> int:
    """Obsidian 联动"""
    from dochris.vault.bridge import (
        list_associated_notes,
        promote_to_obsidian,
        seed_from_obsidian,
    )

    workspace = get_default_workspace()

    if args.vault_command == "seed":
        if not args.topic:
            print(f"{error('✗ seed 命令需要 topic 参数')}")
            print('  用法: kb vault seed "<topic>"')
            return 1

        results = seed_from_obsidian(workspace, args.topic)
        if results:
            print(f"{success(f'✓ 导入 {len(results)} 个笔记')}")
            return 0
        return 1

    elif args.vault_command == "promote":
        if not args.src_id:
            print(f"{error('✗ promote 命令需要 src_id 参数')}")
            print("  用法: kb vault promote <src-id>")
            return 1

        ok = promote_to_obsidian(workspace, args.src_id)
        if ok:
            print(f"{success('✓ 推送成功')}")
            return 0
        return 1

    elif args.vault_command == "list":
        if not args.src_id:
            print(f"{error('✗ list 命令需要 src_id 参数')}")
            print("  用法: kb vault list <src-id>")
            return 1

        notes = list_associated_notes(workspace, args.src_id)
        return 0 if notes else 1

    else:
        print(f"{error('✗ 未知 vault 子命令')}: {args.vault_command}")
        print("  支持: seed, promote, list")
        return 1
