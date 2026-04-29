"""CLI 命令：Phase 1 摄入"""

import argparse

from dochris.cli.cli_utils import error, info, success, warning


def cmd_ingest(args: argparse.Namespace) -> int:
    """Phase 1: 摄入文件"""
    from dochris.phases.phase1_ingestion import run_phase1, setup_logging

    logger = setup_logging()
    print(info("Phase 1: 开始摄入文件..."))

    try:
        stats = run_phase1(logger)
        print(f"\n{success('✓ Phase 1 完成!')}")
        print(f"  总计: {stats['total']} 文件")
        print(f"  本次新增: {stats['linked']} 文件")
        print(f"  跳过(重复): {stats['skipped']} 文件")
        return 0
    except Exception as e:
        print(f"\n{error('✗ Phase 1 失败')}: {e}")
        print(f"\n{warning('建议')}: 检查源目录配置和文件权限")
        return 1
