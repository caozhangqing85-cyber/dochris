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

    # 并发数验证
    if concurrency is not None and concurrency < 1:
        print(error("✗ 并发数必须 >= 1"))
        return 1

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

        # 本次编译统计：比较编译前后的 manifest 数量差异
        total_compiled = len(compiled)
        total_failed = len(failed)
        this_compiled = max(0, total_compiled - len([m for m in compiled if _was_before(m, start_time)]))
        this_failed = max(0, total_failed - len([m for m in failed if _was_before(m, start_time)]))

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
        print(f"  本次成功: {bold(str(this_compiled))} 个 (累计 {total_compiled})")
        if this_failed > 0:
            failed_ids = [m["id"] for m in failed[:5]]
            print(
                f"  本次失败: {error(str(this_failed))} 个 ({', '.join(failed_ids)}{'...' if total_failed > 5 else ''})"
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


def _was_before(manifest: dict, timestamp: float) -> bool:
    """检查 manifest 的编译时间是否早于给定时间戳"""
    ts = manifest.get("compiled_at") or manifest.get("updated_at") or ""
    if not ts:
        return True  # 无时间信息的视为编译前已有
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(ts)
        return dt.timestamp() < timestamp
    except (ValueError, TypeError):
        return True
