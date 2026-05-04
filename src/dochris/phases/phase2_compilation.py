#!/usr/bin/env python3
"""
PDF 编译系统 - v7 (模块化重构版)
Dochris 知识库编译系统的核心模块

优化版本：v7
优化日期：2026-04-08

核心改进：
- 引入 SHA256 缓存 (避免重复编译相同内容)
- 设置 temperature=0.1 (确保稳定输出)
- 模块化设计 (职责分离)
- 分类文件处理 (代码/PDF/文档)
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

# 导入核心模块
sys.path.insert(0, str(Path(__file__).parent))

from dochris.core.cache import cache_dir, clear_cache
from dochris.manifest import get_all_manifests
from dochris.settings import (
    BATCH_SIZE,
    CACHE_RETENTION_DAYS,
    DEFAULT_API_BASE,
    DEFAULT_API_KEY,
    DEFAULT_CONCURRENCY,
    DEFAULT_MODEL,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    OPENROUTER_API_BASE,
    OPENROUTER_MODEL,
    get_default_workspace,
    get_logs_dir,
)
from dochris.workers.compiler_worker import CompilerWorker
from dochris.workers.monitor_worker import MonitorWorker

# ============================================================
# 日志设置
# ============================================================


def setup_logging() -> logging.Logger:
    """设置日志系统

    Returns:
        配置好的 logger 实例
    """
    log_dir = get_logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"phase2_{datetime.now().strftime(LOG_DATE_FORMAT)}.log"

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    return logging.getLogger()


# ============================================================
# 主编译函数
# ============================================================


async def compile_all(
    max_concurrent: int = DEFAULT_CONCURRENCY,
    limit: int | None = None,
    use_openrouter: bool = False,
    dry_run: bool = False,
) -> None:
    """编译所有待编译的文档

    Args:
        max_concurrent: 最大并发数
        limit: 限制编译数量（用于测试）
        use_openrouter: 是否使用 OpenRouter API
        dry_run: 模拟运行，只显示将要执行的操作
    """
    workspace = get_default_workspace()
    logger = logging.getLogger(__name__)

    # 检测是否使用 OpenRouter
    if use_openrouter:
        api_base = OPENROUTER_API_BASE
        model = OPENROUTER_MODEL
        logger.info(f"✓ 使用 OpenRouter (免费模型: {model})")
    else:
        api_base = DEFAULT_API_BASE
        model = DEFAULT_MODEL
        logger.info(f"✓ 使用默认 API ({model})")

    # 获取待编译的 manifest
    all_manifests = get_all_manifests(workspace, status="ingested")

    if limit:
        all_manifests = all_manifests[:limit]
        logger.info(f"⚠ 限制编译数量: {limit}")

    logger.info(f"📊 待编译文档: {len(all_manifests)} 个")

    if not all_manifests:
        logger.info("✅ 没有待编译的文档")
        return

    # Dry-run 模式
    if dry_run:
        logger.info("=" * 60)
        logger.info("⚠ DRY-RUN 模式: 不会实际执行任何操作")
        logger.info("=" * 60)
        logger.info("将要编译的文档:")
        total_estimated_calls = 0
        for i, m in enumerate(all_manifests, 1):
            file_size = m.get("size_bytes", 0)
            # 估算 API 调用次数（基于文件大小）
            if file_size > 100000:  # > 100KB 可能需要多次调用
                estimated_calls = 3
            elif file_size > 50000:  # > 50KB 可能需要 2 次
                estimated_calls = 2
            else:
                estimated_calls = 1
            total_estimated_calls += estimated_calls
            logger.info(
                f"  [{i}] {m['id']}: {m.get('title', 'N/A')} "
                f"({file_size} bytes, ~{estimated_calls} API calls)"
            )
        logger.info("=" * 60)
        logger.info(f"总计: {len(all_manifests)} 个文档")
        logger.info(f"预估 API 调用次数: ~{total_estimated_calls} 次")
        # 粗略估算费用（假设每次调用 0.001 元）
        estimated_cost = total_estimated_calls * 0.001
        logger.info(f"预估费用: ~¥{estimated_cost:.2f}")
        logger.info("=" * 60)
        return

    # 创建 worker
    worker = CompilerWorker(api_key=DEFAULT_API_KEY, base_url=api_base, model=model)

    # 创建监控
    monitor = MonitorWorker()

    # 并发编译
    semaphore = asyncio.Semaphore(max_concurrent)

    logger.info(f"🚀 开始编译 (并发数: {max_concurrent})")

    async def compile_one(src_id: str) -> dict[str, Any] | None:
        async with semaphore:
            return await worker.compile_document(src_id)

    # 分批处理 (避免一次性创建太多任务)
    batch_size = BATCH_SIZE
    success_count = 0
    fail_count = 0

    # 使用 rich 进度条（仅在交互模式时）
    console = Console()
    if sys.stdout.isatty():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as pbar:
            task = pbar.add_task("[cyan]编译文档...", total=len(all_manifests))

            for i in range(0, len(all_manifests), batch_size):
                batch = all_manifests[i : i + batch_size]

                tasks = [compile_one(m["id"]) for m in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 统计结果
                for j, result in enumerate(results):
                    if isinstance(result, Exception):
                        fail_count += 1
                        logger.error(
                            f"文档 {batch[j]['id']} 编译异常: {type(result).__name__}: {result}"
                        )
                    elif result:
                        success_count += 1
                    else:
                        fail_count += 1

                # 更新进度条
                completed = min(i + batch_size, len(all_manifests))
                pbar.update(task, completed=completed)
    else:
        # 非交互模式：使用简单日志
        for i in range(0, len(all_manifests), batch_size):
            batch = all_manifests[i : i + batch_size]
            logger.info(f"📦 处理批次 {i // batch_size + 1}: {len(batch)} 个文档")

            tasks = [compile_one(m["id"]) for m in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 统计结果
            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    fail_count += 1
                    logger.error(
                        f"文档 {batch[j]['id']} 编译异常: {type(result).__name__}: {result}"
                    )
                elif result:
                    success_count += 1
                else:
                    fail_count += 1

            # 打印进度
            completed = i + batch_size
            percentage = (completed / len(all_manifests)) * 100
            logger.info(f"📈 进度: {completed}/{len(all_manifests)} ({percentage:.1f}%)")

    # 打印最终报告
    logger.info(f"\n{'=' * 60}")
    logger.info("✅ 编译完成")
    logger.info(f"{'=' * 60}")
    logger.info(f"成功: {success_count} 个")
    logger.info(f"失败: {fail_count} 个")
    logger.info(f"总计: {len(all_manifests)} 个")

    # 打印详细报告
    monitor.print_report()

    # 清理旧缓存
    logger.info("🧹 清理旧缓存...")
    cleaned = clear_cache(cache_dir(workspace), older_than_days=CACHE_RETENTION_DAYS)
    logger.info(f"✓ 清理了 {cleaned} 个缓存文件")


# ============================================================
# 主函数
# ============================================================


def main() -> None:
    """主函数入口"""
    setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(
        description="知识库编译系统 v7 (模块化重构版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置编译所有文档
  python phase2_compilation.py

  # 编译前 10 个文档
  python phase2_compilation.py --limit 10

  # 使用 OpenRouter 免费模型
  python phase2_compilation.py --openrouter

  # 使用 4 个并发编译
  python phase2_compilation.py --concurrency 4

  # 清理缓存
  python phase2_compilation.py --clear-cache
        """,
    )

    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"并发数 (默认: {DEFAULT_CONCURRENCY})",
    )

    parser.add_argument("--limit", type=int, default=None, help="限制编译数量")

    parser.add_argument("--openrouter", action="store_true", help="使用 OpenRouter 免费模型 (推荐)")

    parser.add_argument("--clear-cache", action="store_true", help="清理旧缓存 (保留最近 30 天)")

    parser.add_argument("--clear-all-cache", action="store_true", help="清理所有缓存")

    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="指定模型名称")

    parser.add_argument("--api-base", type=str, default=DEFAULT_API_BASE, help="指定 API 基础 URL")

    args = parser.parse_args()

    # 验证 API 密钥（编译命令需要）
    if not args.clear_cache and not args.clear_all_cache and not DEFAULT_API_KEY:
        logger.error("❌ 错误: OPENAI_API_KEY 环境变量未设置")
        logger.error("请设置: export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

    # 清理缓存命令
    if args.clear_cache or args.clear_all_cache:
        workspace = get_default_workspace()
        if args.clear_all_cache:
            logger.info("🗑️ 清理所有缓存...")
            cleared = clear_cache(cache_dir(workspace), older_than_days=0)
            logger.info(f"✓ 清理了 {cleared} 个缓存文件")
        else:
            logger.info(f"🧹 清理旧缓存 (保留最近 {CACHE_RETENTION_DAYS} 天)...")
            cleared = clear_cache(cache_dir(workspace), older_than_days=CACHE_RETENTION_DAYS)
            logger.info(f"✓ 清理了 {cleared} 个缓存文件")
        return

    # 编译命令
    logger.info(f"\n{'=' * 60}")
    logger.info("🚀 知识库编译系统 v7 启动")
    logger.info(f"{'=' * 60}")

    asyncio.run(
        compile_all(
            max_concurrent=args.concurrency, limit=args.limit, use_openrouter=args.openrouter
        )
    )

    logger.info(f"\n{'=' * 60}")
    logger.info("✅ 任务完成")
    logger.info(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
