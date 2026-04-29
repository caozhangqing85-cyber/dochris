"""
CLI 命令：Phase 2 编译
"""

import argparse

from dochris.cli.cli_utils import error, info, success, warning


def cmd_compile(args: argparse.Namespace) -> int:
    """Phase 2: 编译"""
    import asyncio

    from dochris.phases.phase2_compilation import compile_all, setup_logging

    setup_logging()
    limit = args.limit
    concurrency = args.concurrency

    print(info("Phase 2: 开始编译..."))

    try:
        asyncio.run(
            compile_all(max_concurrent=concurrency, limit=limit, use_openrouter=args.openrouter)
        )
        print(f"\n{success('✓ Phase 2 完成!')}")
        return 0
    except Exception as e:
        print(f"\n{error('✗ Phase 2 失败')}: {e}")
        print(f"\n{warning('建议')}: 检查 API 配置和网络连接")
        return 1
