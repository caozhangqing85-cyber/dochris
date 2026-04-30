#!/usr/bin/env python3
"""
失败文件补偿重试脚本
针对 phase2 编译失败的 manifest 进行补偿处理：

补偿策略：
1. ebook (.mobi): 用 Calibre ebook-convert 转文本
2. pdf (扫描件): 用 PyMuPDF 检测 + tesseract OCR
3. llm_failed: 带模型降级的智能重试
4. other (.mhtml/.pptx): 尝试 markitdown 或备用提取

使用方式：
    python scripts/compensate_failures.py [--type ebook|pdf|llm|all] [--max-files N] [--concurrency N]
"""

import argparse
import asyncio
import signal
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dochris.log import append_log
from dochris.manifest import (
    get_all_manifests,
    update_manifest_status,
)
from dochris.settings import get_settings

# 导入内容清洗模块
try:
    from dochris.admin.sanitize_sensitive_words import (
        sanitize_filename,
        sanitize_pdf_content,
        sanitize_prompt,
        should_skip_file,
    )
except ImportError:

    def sanitize_filename(filename: str) -> str:
        return Path(filename).stem

    def sanitize_pdf_content(content: str) -> str:
        return content

    def sanitize_prompt(prompt: str) -> str:
        return prompt

    def should_skip_file(filename: str) -> tuple[bool, str | None]:
        return False, None


import contextlib

from dochris.compensate.compensate_extractors import extract_text_compensated
from dochris.compensate.compensate_utils import (
    BATCH_DELAY,
    BATCH_SIZE,
    MAX_CONCURRENCY,
    MODEL_CHAIN,
    setup_logging,
)

_s = get_settings()
KB_PATH = _s.workspace
MAX_CONTENT_CHARS = _s.max_content_chars
MIN_AUDIO_TEXT_LENGTH = _s.min_text_length
from dochris.core.quality_scorer import score_summary_quality_v4 as score_summary_quality

# ============================================================
# 本地文本提取和 LLM 生成函数（替代不存在的 phase2 函数）
# ============================================================


def extract_text_from_file(file_path: Path, logger: Any) -> str | None:
    """从文件提取文本，根据扩展名选择解析器

    Args:
        file_path: 文件路径
        logger: 日志记录器

    Returns:
        提取的文本，失败返回 None
    """
    ext = file_path.suffix.lower()

    # PDF 使用 markitdown
    if ext == ".pdf":
        from dochris.parsers.pdf_parser import parse_pdf

        try:
            text = parse_pdf(file_path)
            if text:
                logger.debug(f"PDF 提取成功: {file_path.name}")
                return text[:MAX_CONTENT_CHARS]
        except Exception as e:
            logger.warning(f"PDF 提取失败 {file_path.name}: {e}")

    # 文档文件
    elif ext in (".md", ".txt", ".rst", ".html", ".htm", ".docx", ".doc", ".pptx", ".ppt", ".xlsx"):
        from dochris.parsers.doc_parser import parse_document

        try:
            text = parse_document(file_path)  # type: ignore[assignment]
            if text:
                logger.debug(f"文档提取成功: {file_path.name}")
                return text[:MAX_CONTENT_CHARS]
        except Exception as e:
            logger.warning(f"文档提取失败 {file_path.name}: {e}")

    # 代码文件（直接读取）
    elif ext in (".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".css", ".json", ".xml"):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            return text[:MAX_CONTENT_CHARS]
        except Exception as e:
            logger.warning(f"代码文件读取失败 {file_path.name}: {e}")

    # 默认尝试直接读取
    else:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 100:
                return text[:MAX_CONTENT_CHARS]
        except Exception:
            pass

    return None


async def generate_summary_with_llm(
    text: str, title: str, logger: Any, rate_limiter: Any = None, adaptive_delay: float | None = None
) -> dict[str, Any] | None:
    """使用 LLM 生成摘要

    Args:
        text: 待摘要文本
        title: 文档标题
        logger: 日志记录器
        rate_limiter: 速率限制器（未使用，保留兼容）
        adaptive_delay: 自适应延迟值（未使用，保留兼容）

    Returns:
        摘要字典，失败返回 None
    """
    from dochris.core.llm_client import LLMClient
    from dochris.settings import get_settings

    settings = get_settings()

    # 检查 api_key
    if not settings.api_key:
        logger.error("未配置 API Key，无法创建 LLMClient")
        return None

    # 创建 LLMClient
    client = LLMClient(
        api_key=settings.api_key,
        base_url=settings.api_base,
        model=settings.model,
    )

    try:
        result = await client.generate_summary(text, title)
        return result
    except Exception as e:
        logger.error(f"LLM 生成摘要失败: {e}")
        return None

# ============================================================
# 智能重试 + 模型降级
# ============================================================


async def compile_with_model_fallback(
    text: str,
    title: str,
    logger: Any,
    model_chain: list[str],
    adaptive_delay: float,
) -> dict[str, Any] | None:
    """带模型降级的编译

    依次尝试模型链中的每个模型，直到成功或全部失败

    Args:
        text: 待摘要文本
        title: 文档标题
        logger: 日志记录器
        model_chain: 模型链（依次尝试）
        adaptive_delay: 自适应延迟值

    Returns:
        摘要字典，失败返回 None
    """
    from dochris.core.llm_client import LLMClient
    from dochris.settings import get_settings

    settings = get_settings()

    # 检查 api_key
    if not settings.api_key:
        logger.error("未配置 API Key，无法创建 LLMClient")
        return None

    for model_name in model_chain:
        logger.info(f"尝试模型: {model_name}")

        # 创建使用指定模型的 LLMClient
        client = LLMClient(
            api_key=settings.api_key,
            base_url=settings.api_base,
            model=model_name,
        )

        try:
            result = await client.generate_summary(text, title)
            if result:
                logger.info(f"模型 {model_name} 编译成功")
                return result
            else:
                logger.warning(f"模型 {model_name} 编译返回空")
        except (RuntimeError, ValueError, KeyError, OSError) as e:
            logger.warning(f"模型 {model_name} 编译异常: {e}")

        # 模型切换间等待
        await asyncio.sleep(3)

    return None


async def retry_llm_failed(
    manifest: dict,
    async_client: Any,
    logger: Any,
    adaptive_delay: float,
    model_chain: list[str],
) -> tuple[str, bool, str, str]:
    """重试 llm_failed 的文件

    Returns:
        (src_id, success, status, compensation_used)
    """
    src_id = manifest["id"]
    file_path = KB_PATH / manifest["file_path"]
    title = manifest["title"]

    if not file_path.exists():
        return src_id, False, "file_not_found", "none"

    # 文本提取
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, extract_text_from_file, file_path, logger)

    if text:
        with contextlib.suppress(ValueError, AttributeError):
            text = sanitize_pdf_content(text)

    if not text or not text.strip() or len(text.strip()) < MIN_AUDIO_TEXT_LENGTH:
        return src_id, False, "no_text", "none"

    # 清洗标题
    try:
        clean_title = sanitize_filename(title)
    except (ValueError, AttributeError):
        clean_title = Path(title).stem

    # 带模型降级的编译
    summary = await compile_with_model_fallback(
        text,
        clean_title,
        logger,
        model_chain,
        adaptive_delay,
    )

    if not summary:
        return src_id, False, "llm_failed", "model_fallback"

    # 质量评分
    score = score_summary_quality(summary)
    concepts = summary.get("concepts", [])
    concepts_names = [c.get("name", "") for c in concepts]

    one_line = summary.get("one_line", "")
    key_points = summary.get("key_points", [])
    detailed_summary = summary.get("detailed_summary", "")

    # 更新 manifest
    update_manifest_status(
        KB_PATH,
        src_id,
        status="compiled",
        quality_score=score,
        summary={
            "one_line": one_line,
            "key_points": key_points,
            "detailed_summary": detailed_summary,
        },
        compiled_summary={
            "concepts": concepts_names,
            "concepts_data": concepts,
        },
    )

    logger.info(f"补偿编译成功: {clean_title[:60]} [{src_id}] 质量={score}")
    return src_id, True, "success", "model_fallback"


# ============================================================
# 补偿编译单个文件
# ============================================================


async def compensate_single(
    manifest: dict,
    logger: Any,
    semaphore: asyncio.Semaphore,
    adaptive_delay: float,
    model_chain: list[str],
    compensate_type: str,
) -> tuple[str, bool, str, str]:
    """补偿编译单个文件

    Returns:
        (src_id, success, status, compensation_method)
    """
    src_id = manifest["id"]
    file_path = KB_PATH / manifest["file_path"]
    title = manifest["title"]
    manifest.get("type", "")

    async with semaphore:
        if not file_path.exists():
            return src_id, False, "file_not_found", "none"

        # 高风险文件跳过
        should_skip, risk_word = should_skip_file(file_path.name)
        if should_skip:
            logger.warning(f"高风险敏感词 '{risk_word}'，跳过: {file_path.name} [{src_id}]")
            return src_id, True, "skipped", "none"

        # 1. 补偿文本提取（在 executor 中运行）
        loop = asyncio.get_event_loop()
        text, extraction_method = await loop.run_in_executor(
            None, extract_text_compensated, file_path, manifest, logger
        )

        if not text or len(text.strip()) < MIN_AUDIO_TEXT_LENGTH:
            logger.warning(f"补偿文本提取失败: {title[:60]} [{src_id}] method={extraction_method}")
            return src_id, False, "no_text", extraction_method

        # 清洗
        with contextlib.suppress(ValueError, AttributeError):
            text = sanitize_pdf_content(text)

        # 清洗标题
        try:
            clean_title = sanitize_filename(title)
        except (ValueError, AttributeError):
            clean_title = Path(title).stem

        # 2. LLM 编译（带模型降级）
        logger.info(f"补偿编译: {clean_title[:60]} [{src_id}] extract={extraction_method}")
        summary = await compile_with_model_fallback(
            text,
            clean_title,
            logger,
            model_chain,
            adaptive_delay,
        )

        if not summary:
            logger.error(f"补偿 LLM 编译失败: {title[:60]} [{src_id}]")
            return src_id, False, "llm_failed", extraction_method

        # 3. 质量评分 + 更新 manifest
        score = score_summary_quality(summary)
        concepts = summary.get("concepts", [])
        concepts_names = [c.get("name", "") for c in concepts]

        one_line = summary.get("one_line", "")
        key_points = summary.get("key_points", [])
        detailed_summary = summary.get("detailed_summary", "")

        update_manifest_status(
            KB_PATH,
            src_id,
            status="compiled",
            quality_score=score,
            summary={
                "one_line": one_line,
                "key_points": key_points,
                "detailed_summary": detailed_summary,
            },
            compiled_summary={
                "concepts": concepts_names,
                "concepts_data": concepts,
            },
        )

        logger.info(
            f"补偿成功: {clean_title[:60]} [{src_id}] extract={extraction_method} 质量={score}"
        )
        return src_id, True, "success", extraction_method


# ============================================================
# 筛选失败的 manifest
# ============================================================


def find_failed_manifests(compensate_type: str, logger: Any) -> list[dict]:
    """筛选需要补偿的失败 manifest"""
    failed = get_all_manifests(KB_PATH, status="failed")
    logger.info(f"失败 manifest 总数: {len(failed)}")

    filtered = []
    for m in failed:
        error = m.get("error_message", "unknown")
        file_type = m.get("type", "")
        fp = KB_PATH / m.get("file_path", "")
        ext = fp.suffix.lower() if fp.exists() else ""

        if compensate_type == "ebook":
            # .mobi / .azw3 的 ebook
            if file_type == "ebook" and ext in (".mobi", ".azw3") and "no_text" in error:
                filtered.append(m)
        elif compensate_type == "pdf":
            # PDF 的 no_text
            if file_type == "pdf" and "no_text" in error:
                filtered.append(m)
        elif compensate_type == "llm":
            # LLM 编译失败
            if "llm_failed" in error:
                filtered.append(m)
        elif compensate_type == "other":
            # .mhtml / .pptx 等可处理的 other 类型
            if file_type == "other" and ext in (".mhtml", ".pptx", ".ppt") and "no_text" in error:
                filtered.append(m)
        elif compensate_type == "all":
            # 所有可补偿的
            if "no_text" in error:
                if file_type == "ebook" and ext in (".mobi", ".azw3") or file_type == "pdf" or file_type == "other" and ext in (".mhtml", ".pptx", ".ppt"):
                    filtered.append(m)
            elif "llm_failed" in error:
                filtered.append(m)

    return filtered


# ============================================================
# 主流程
# ============================================================


async def run_compensate(logger: Any, compensate_type: str, max_files: int = 0) -> None:
    """主补偿流程"""
    manifests = find_failed_manifests(compensate_type, logger)

    if not manifests:
        logger.info("没有需要补偿的文件")
        return

    logger.info(f"需要补偿的文件: {len(manifests)} 个")
    type_counts = Counter(m.get("type", "unknown") for m in manifests)
    for t, c in type_counts.most_common():
        logger.info(f"  {t}: {c}")

    if max_files > 0:
        manifests = manifests[:max_files]
        logger.info(f"限制数量: {max_files}")

    # 验证 API 配置
    import os

    api_key = os.environ.get("OPENAI_API_KEY") or get_settings().api_key
    if not api_key:
        logger.error("OPENAI_API_KEY 未设置（环境变量或 settings）")
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    adaptive_delay = 2.0
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("收到中断信号，正在安全退出...")
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(shutdown_event.set)
        except RuntimeError:
            shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, signal_handler)

    # 统计
    success = 0
    failed = 0
    skipped = 0
    compensation_stats: Counter[str] = Counter()
    total = len(manifests)

    # 分批
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(f"分批: {total_batches} 批, 每批 {BATCH_SIZE} 个, 并发 {MAX_CONCURRENCY}")

    for batch_idx in range(total_batches):
        if shutdown_event.is_set():
            break

        batch_start = batch_idx * BATCH_SIZE
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = manifests[batch_start:batch_end]
        batch_num = batch_idx + 1

        logger.info(f"\n{'=' * 40}")
        logger.info(f"第 {batch_num}/{total_batches} 批 ({len(batch)} 个文件)")
        logger.info(f"{'=' * 40}")

        batch_success = 0
        batch_failed = 0

        tasks = []
        for m in batch:
            if shutdown_event.is_set():
                break
            tasks.append(
                compensate_single(
                    m,
                    logger,
                    semaphore,
                    adaptive_delay,
                    MODEL_CHAIN,
                    compensate_type,
                )
            )

        for future in asyncio.as_completed(tasks):
            if shutdown_event.is_set():
                break
            src_id, ok, status, method = await future

            if status == "skipped":
                skipped += 1
            elif ok:
                success += 1
                batch_success += 1
            else:
                failed += 1
                batch_failed += 1

            compensation_stats[method] += 1

            done = success + failed + skipped
            logger.info(f"  进度: {done}/{total} (成功={success}, 失败={failed}, 跳过={skipped})")

        logger.info(
            f"第 {batch_num}/{total_batches} 批完成: 成功={batch_success}, 失败={batch_failed}"
        )

        if batch_num < total_batches and not shutdown_event.is_set():
            await asyncio.sleep(BATCH_DELAY)

    # 报告
    logger.info(f"\n{'=' * 60}")
    logger.info(f"补偿完成 (type={compensate_type})")
    logger.info(f"  成功: {success}, 失败: {failed}, 跳过: {skipped}")
    logger.info("  补偿方法统计:")
    for method, count in compensation_stats.most_common():
        logger.info(f"    {method}: {count}")
    logger.info(f"{'=' * 60}")

    append_log(
        KB_PATH,
        "compensate",
        f"补偿完成 (type={compensate_type}): 成功={success}, 失败={failed}, 跳过={skipped}",
    )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    logger = setup_logging()

    parser = argparse.ArgumentParser(description="失败文件补偿重试")
    parser.add_argument(
        "--type", choices=["ebook", "pdf", "llm", "other", "all"], default="all", help="补偿类型"
    )
    parser.add_argument("--max-files", type=int, default=0, help="最大文件数")
    parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY, help="并发数")
    parser.add_argument("--dry-run", action="store_true", help="只分析不执行")
    args = parser.parse_args()

    if args.concurrency != MAX_CONCURRENCY:
        MAX_CONCURRENCY = args.concurrency

    if args.dry_run:
        manifests = find_failed_manifests(args.type, logger)
        logger.info(f"[DRY RUN] 需要补偿的文件: {len(manifests)} 个")
        type_counts = Counter(m.get("type", "unknown") for m in manifests)
        for t, c in type_counts.most_common():
            logger.info(f"  {t}: {c}")
        for m in manifests[:20]:
            logger.info(f"  {m['id']} ({m.get('type')}) {m.get('title', '')[:50]}")
        if len(manifests) > 20:
            logger.info(f"  ... 还有 {len(manifests) - 20} 个")
    else:
        asyncio.run(run_compensate(logger, args.type, max_files=args.max_files))
