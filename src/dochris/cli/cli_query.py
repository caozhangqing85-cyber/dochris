"""CLI 命令：Phase 3 查询"""

import argparse

from dochris.cli.cli_utils import dim


def cmd_query(args: argparse.Namespace) -> int:
    """Phase 3: 查询"""
    from dochris.phases.phase3_query import print_result, query, setup_logging

    logger = setup_logging()

    if not args.query:
        # 交互模式
        from dochris.phases.phase3_query import interactive_mode

        interactive_mode(logger)
        return 0

    # 单次查询
    mode = args.mode or "combined"
    top_k = args.top_k or 5

    result = query(args.query, mode=mode, top_k=top_k, logger=logger)
    print_result(result)

    if result.get("answer"):
        return 0

    # 空结果友好提示
    if not result.get("results") and not result.get("answer"):
        print(
            f"\n{dim('💡 提示: 知识库为空。请先运行 kb ingest 添加文件，再运行 kb compile 编译。')}"
        )
    return 1
