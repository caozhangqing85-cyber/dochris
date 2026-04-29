"""CLI 命令：Phase 3 查询"""

import argparse


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
    return 1
