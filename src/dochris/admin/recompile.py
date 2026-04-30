#!/usr/bin/env python3
"""
重新编译失败文档的统一入口

支持多种过滤模式：
- all: 所有可恢复的失败文档
- llm_failed: LLM 调用失败的文档
- text: 文本类型且可恢复的失败文档
- custom: 自定义错误类型过滤
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 添加路径
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from dochris.manifest import get_all_manifests
from dochris.settings import get_settings
from dochris.workers.compiler_worker import CompilerWorker


def setup_logging(mode: str = "recompile") -> logging.Logger:
    """设置日志系统

    Args:
        mode: 日志模式标识

    Returns:
        配置好的 logger 实例
    """
    settings = get_settings()
    log_dir = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"recompile_{mode}_{datetime.now().strftime(settings.log_date_format)}.log"

    logging.basicConfig(
        level=logging.INFO,
        format=settings.log_format,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def get_recoverable_failed_docs(
    workspace: Path, mode: str = "all", error_filter: str | None = None
) -> list[dict[str, Any]]:
    """获取可恢复的失败文档

    Args:
        workspace: 工作区路径
        mode: 过滤模式 (all, llm_failed, text, custom)
        error_filter: 自定义错误类型过滤

    Returns:
        可恢复的文档列表
    """
    all_manifests = get_all_manifests(workspace, status="failed")

    if mode == "llm_failed":
        # 只返回 llm_failed 的文档
        return [d for d in all_manifests if "llm_failed" in d.get("error_message", "")]

    if mode == "text":
        # 返回文本类型且可恢复的文档
        text_types = {"pdf", "article", "ebook", "other"}
        recoverable_errors = {
            "llm_failed",
            "Connection error",
            "timeout",
            "'dict' object has no attribute 'strip'",
            "'list' object has no attribute 'get'",
        }

        result = []
        for manifest in all_manifests:
            doc_type = manifest.get("type", "unknown")
            error_msg = manifest.get("error_message", "")

            if doc_type in text_types and any(err in error_msg for err in recoverable_errors):
                # 排除纯图片PDF
                if doc_type == "pdf" and error_msg == "no_text":
                    continue
                result.append(manifest)

        return result

    # 默认模式：所有可恢复的失败文档
    default_recoverable_errors: list[str] = [
        "llm_failed",
        "no_text",
        "Failed to process file",
        "Connection error",
        "timeout",
        "API error",
    ]

    if error_filter:
        return [d for d in all_manifests if error_filter in d.get("error_message", "")]

    return [
        d
        for d in all_manifests
        if any(err in d.get("error_message", "") for err in default_recoverable_errors)
    ]


async def recompile(
    mode: str = "all",
    error_filter: str | None = None,
    max_concurrent: int = 2,
    limit: int | None = None,
) -> None:
    """重新编译失败的文档

    Args:
        mode: 过滤模式 (all, llm_failed, text, custom)
        error_filter: 自定义错误类型过滤
        max_concurrent: 最大并发数
        limit: 限制编译数量
    """
    logger = logging.getLogger(__name__)
    settings = get_settings()
    workspace = settings.workspace

    # 获取失败文档
    failed_docs = get_recoverable_failed_docs(workspace, mode, error_filter)

    # 限制数量
    if limit:
        failed_docs = failed_docs[:limit]
        logger.info(f"⚠ 限制编译数量: {limit}")

    if not failed_docs:
        logger.info("✅ 没有可恢复的失败文档")
        return

    logger.info(f"📊 可恢复的失败文档: {len(failed_docs)} 个")

    # 统计错误类型
    from collections import Counter

    error_counter = Counter([d.get("error_message", "unknown") for d in failed_docs])

    logger.info("📦 错误类型分布:")
    for error, count in error_counter.most_common(10):
        error_short = error[:60] if len(error) > 60 else error
        logger.info(f"  [{count}个] {error_short}")

    # 创建 worker
    api_key = settings.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ OPENAI_API_KEY 未设置")
        sys.exit(1)

    worker = CompilerWorker(api_key=api_key, base_url=settings.api_base, model=settings.model)

    # 并发重编译
    semaphore = asyncio.Semaphore(max_concurrent)
    logger.info(f"🚀 开始重新编译 (并发数: {max_concurrent})")

    async def recompile_one(src_id: str) -> dict[str, Any] | None:
        async with semaphore:
            return await worker.compile_document(src_id)

    # 分批处理
    batch_size = settings.batch_size
    success_count = 0
    fail_count = 0

    for i in range(0, len(failed_docs), batch_size):
        batch = failed_docs[i : i + batch_size]
        logger.info(f"📦 处理批次 {i // batch_size + 1}: {len(batch)} 个文档")

        tasks = [recompile_one(m["id"]) for m in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        for result in results:
            if result and not isinstance(result, Exception):
                success_count += 1
            else:
                fail_count += 1

        # 打印进度
        completed = i + batch_size
        percentage = (completed / len(failed_docs)) * 100
        logger.info(f"📈 进度: {completed}/{len(failed_docs)} ({percentage:.1f}%)")

    # 打印最终报告
    logger.info(f"\n{'=' * 60}")
    logger.info("✅ 重新编译完成")
    logger.info(f"{'=' * 60}")
    logger.info(f"成功: {success_count} 个")
    logger.info(f"失败: {fail_count} 个")
    logger.info(f"总计: {len(failed_docs)} 个")


def main() -> None:
    """主函数入口"""
    parser = argparse.ArgumentParser(
        description="重新编译失败文档（统一入口）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
模式说明:
  all         - 所有可恢复的失败文档（默认）
  llm_failed  - 仅 LLM 调用失败的文档
  text        - 文本类型（pdf/article/ebook）的可恢复失败文档

示例:
  # 重新编译所有可恢复的失败文档
  python recompile.py

  # 仅重新编译 llm_failed 的文档
  python recompile.py --mode llm_failed

  # 仅重新编译文本类型的文档
  python recompile.py --mode text

  # 自定义错误类型过滤
  python recompile.py --error timeout

  # 限制编译数量
  python recompile.py --limit 10

  # 使用 4 个并发
  python recompile.py --concurrency 4
        """,
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="all",
        choices=["all", "llm_failed", "text"],
        help="过滤模式 (默认: all)",
    )

    parser.add_argument("--error", type=str, default=None, help="自定义错误类型过滤（覆盖 --mode）")

    parser.add_argument("--concurrency", type=int, default=2, help="并发数 (默认: 2)")

    parser.add_argument("--limit", type=int, default=None, help="限制编译数量")

    args = parser.parse_args()

    # 设置日志
    logger = setup_logging(args.mode)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"🔄 重新编译失败文档 (模式: {args.mode})")
    logger.info(f"{'=' * 60}\n")

    asyncio.run(
        recompile(
            mode=args.error and "custom" or args.mode,
            error_filter=args.error,
            max_concurrent=args.concurrency,
            limit=args.limit,
        )
    )

    logger.info(f"\n{'=' * 60}")
    logger.info("✅ 任务完成")
    logger.info(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
