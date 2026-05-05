"""
CLI 命令：Phase 2 编译
"""

import argparse
import time

from dochris.cli.cli_utils import bold, dim, error, info, success, warning


def cmd_compile(args: argparse.Namespace) -> int:
    """Phase 2: 编译"""
    import asyncio

    from dochris.manifest import get_all_manifests
    from dochris.phases.phase2_compilation import compile_all, setup_logging
    from dochris.settings import get_default_workspace

    setup_logging()
    # 优先使用命名参数 --limit，否则使用位置参数
    limit = args.named_limit if args.named_limit is not None else args.limit
    concurrency = args.concurrency

    # 显示待编译数量
    workspace = get_default_workspace()
    pending = get_all_manifests(workspace, status="ingested")
    if limit:
        pending = pending[:limit]

    if not pending:
        print(f"\n{info('✅ 没有待编译的文档')}")
        print(f"{dim('💡 运行 kb ingest 添加文件')}")
        return 0

    print(info(f"Phase 2: 开始编译... ({len(pending)} 个文档)"))

    start_time = time.time()

    try:
        asyncio.run(
            compile_all(
                max_concurrent=concurrency,
                limit=limit,
                use_openrouter=args.openrouter,
                dry_run=args.dry_run,
            )
        )
        elapsed = time.time() - start_time

        if args.dry_run:
            print(f"\n{warning('⚠ Dry-run 模式')}: 未实际执行任何操作")
            return 0

        # 编译完成摘要统计
        elapsed_str = _format_duration(elapsed)
        compiled = get_all_manifests(workspace, status="compiled")
        failed = get_all_manifests(workspace, status="compile_failed")

        # 计算本次编译数量（compiled + failed 中时间在 start_time 之后的）
        # 简化处理：直接用总数
        total_compiled = len(compiled)
        total_failed = len(failed)

        # 计算平均质量分
        score_total = 0
        score_count = 0
        for m in compiled:
            score = m.get("quality_score", 0)
            if score > 0:
                score_total += score
                score_count += 1
        avg_score = round(score_total / score_count, 1) if score_count > 0 else 0

        print(f"\n{success('✓ 编译完成!')}")
        print(f"  成功: {bold(str(total_compiled))} 个")
        if total_failed > 0:
            failed_ids = [m["id"] for m in failed[:5]]
            print(
                f"  失败: {error(str(total_failed))} 个 ({', '.join(failed_ids)}{'...' if total_failed > 5 else ''})"
            )
        if score_count > 0:
            print(f"  平均质量分: {info(str(avg_score))}")
        print(f"  用时: {dim(elapsed_str)}")
        return 0
    except Exception as e:
        print(f"\n{error('✗ Phase 2 失败')}: {e}")
        print(f"\n{warning('建议')}: 检查 API 配置和网络连接")
        return 1


def _format_duration(seconds: float) -> str:
    """格式化持续时间"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = int(minutes // 60)
    mins = minutes % 60
    return f"{hours}h {mins}m"
