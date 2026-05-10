"""CLI 命令：Phase 1 摄入"""

import argparse
from pathlib import Path

from dochris.cli.cli_utils import error, info, success, warning


def cmd_ingest(args: argparse.Namespace) -> int:
    """Phase 1: 摄入文件"""
    from dochris.phases.phase1_ingestion import run_phase1, setup_logging

    logger = setup_logging()

    # 解析用户传入的路径参数
    source_path = None
    if hasattr(args, "path") and args.path:
        source_path = Path(args.path).resolve()
        if not source_path.exists():
            print(f"\n{error('✗ 路径不存在')}: {source_path}")
            return 1
        if source_path.is_file():
            # 单文件：创建临时目录，将文件复制进去
            import shutil
            import tempfile

            tmp_dir = Path(tempfile.mkdtemp(prefix="kb_ingest_"))
            shutil.copy2(source_path, tmp_dir / source_path.name)
            source_path = tmp_dir
            print(info(f"Phase 1: 开始摄入文件... (源文件: {args.path})"))
        else:
            print(info(f"Phase 1: 开始摄入文件... (源目录: {source_path})"))
    else:
        print(info("Phase 1: 开始摄入文件..."))

    try:
        stats = run_phase1(logger, dry_run=args.dry_run, source_path=source_path)
        if args.dry_run:
            print(f"\n{warning('⚠ Dry-run 模式')}: 未实际执行任何操作")
        print(f"\n{success('✓ Phase 1 完成!')}")
        print(f"  总计: {stats['total']} 文件")
        print(f"  本次新增: {stats['linked']} 文件")
        print(f"  跳过(重复): {stats['skipped']} 文件")
        return 0
    except Exception as e:
        print(f"\n{error('✗ Phase 1 失败')}: {e}")
        print(f"\n{warning('建议')}: 检查源目录配置和文件权限")
        return 1
