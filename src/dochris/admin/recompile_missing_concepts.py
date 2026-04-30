#!/usr/bin/env python3
"""
重新编译缺少 concepts_data 的 manifest
- 筛选 status=="compiled" 但 compiled_summary 缺少 concepts_data 的文件
- 按类型优先级排序（article > pdf > 其他）
- 分批编译（50 个/批），并发 8
- 生成优化报告
"""

import argparse
import asyncio
import datetime
import json
import logging
import os
import signal
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dochris.log import append_log
from dochris.manifest import (
    update_manifest_status,
)

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

    def should_skip_file(filename: str) -> tuple[bool, None]:
        return False, None


import contextlib

from dochris.core.quality_scorer import score_summary_quality_v4
from dochris.settings import Settings, get_settings
from dochris.workers.compiler_worker import CompilerWorker

# ============================================================
# 配置
# ============================================================

BATCH_SIZE = 50
MAX_CONCURRENCY = 8
BATCH_DELAY = 5  # 批间延迟秒数
MAX_FILES = 0  # 0 = 不限

# 从 settings 获取配置
_settings = get_settings()
KB_PATH = _settings.workspace
MIN_AUDIO_TEXT_LENGTH = _settings.min_text_length
MAX_CONTENT_CHARS = _settings.max_content_chars
MAX_RETRIES = _settings.max_retries

# ============================================================
# 日志
# ============================================================


def get_settings_cached() -> "Settings":
    """获取 settings（避免重复加载）"""
    return get_settings()


def setup_logging() -> logging.Logger:
    log_dir = KB_PATH / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = (
        log_dir / f"recompile_concepts_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d [%(levelname)-8s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger()


# ============================================================
# 数据收集
# ============================================================


class CompileStats:
    """编译统计数据收集器"""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.batch_stats: list[dict] = []
        self.file_records: list[dict] = []
        self.total_success = 0
        self.total_failed = 0
        self.total_skipped = 0
        self.total_retries = 0
        self.api_calls = 0
        self.api_success = 0

    def add_record(self, src_id, file_type, status, duration, error=None, quality_score=0) -> None:
        self.file_records.append(
            {
                "src_id": src_id,
                "type": file_type,
                "status": status,
                "duration": round(duration, 2),
                "error": error,
                "quality_score": quality_score,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )
        if status == "success":
            self.total_success += 1
        elif status == "skipped":
            self.total_skipped += 1
        else:
            self.total_failed += 1

    def add_batch(self, batch_num, total_batches, files, success, failed, skipped, duration) -> None:
        self.batch_stats.append(
            {
                "batch_num": batch_num,
                "total_batches": total_batches,
                "file_count": len(files),
                "success": success,
                "failed": failed,
                "skipped": skipped,
                "duration": round(duration, 2),
                "files": [f["id"] for f in files],
            }
        )

    @property
    def elapsed(self) -> float:
        return round(time.time() - self.start_time, 2)

    @property
    def throughput(self) -> float:
        elapsed_min = self.elapsed / 60
        if elapsed_min < 0.1:
            return 0
        return round(self.total_success / elapsed_min, 2)


# ============================================================
# 筛选与排序
# ============================================================


def find_missing_concepts_data(logger) -> list[dict]:
    """筛选缺少 concepts_data 的已编译 manifest"""
    sources_dir = KB_PATH / "manifests" / "sources"
    missing = []

    for f in sorted(sources_dir.glob("SRC-*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"读取失败 {f.name}: {e}")
            continue

        if data.get("status") != "compiled":
            continue

        cs = data.get("compiled_summary", {})
        concepts_data = cs.get("concepts_data") if cs else None
        if not concepts_data or not isinstance(concepts_data, list) or len(concepts_data) == 0:
            missing.append(data)

    return missing


def sort_by_priority(manifests: list[dict]) -> list[dict]:
    """按类型优先级排序: article > pdf > ebook > other > video > audio"""
    priority = {"article": 0, "pdf": 1, "ebook": 2, "other": 3, "video": 4, "audio": 5}
    return sorted(manifests, key=lambda m: priority.get(m.get("type", "other"), 5))


# ============================================================
# 单文件重新编译
# ============================================================


async def recompile_single(
    manifest: dict,
    compiler_worker: CompilerWorker,
    logger,
    semaphore: asyncio.Semaphore,
    adaptive_delay: list[float],
    stats: CompileStats,
) -> tuple[str, bool, str]:
    """重新编译单个文件，只补充 concepts_data"""
    src_id = manifest["id"]
    file_path = KB_PATH / manifest["file_path"]
    title = manifest["title"]
    file_type = manifest.get("type", "")
    start = time.time()

    async with semaphore:
        # 检查文件存在
        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path} [{src_id}]")
            stats.add_record(
                src_id, file_type, "failed", time.time() - start, error="file_not_found"
            )
            return src_id, False, "file_not_found"

        # 音频/视频跳过
        audio_exts = {
            ".mp3",
            ".m4a",
            ".wav",
            ".flac",
            ".aac",
            ".ogg",
            ".mp4",
            ".mkv",
            ".avi",
            ".mov",
        }
        if file_type in ("audio", "video") or file_path.suffix.lower() in audio_exts:
            logger.info(f"音频/视频类型，跳过重新编译: {title} [{src_id}]")
            stats.add_record(
                src_id, file_type, "skipped", time.time() - start, error="audio_video_skip"
            )
            return src_id, True, "skipped"

        # 高风险文件跳过
        should_skip, risk_word = should_skip_file(file_path.name)
        if should_skip:
            logger.warning(f"高风险敏感词 '{risk_word}'，跳过: {file_path.name} [{src_id}]")
            stats.add_record(
                src_id, file_type, "skipped", time.time() - start, error=f"high_risk:{risk_word}"
            )
            return src_id, True, "skipped"

        # 文本提取（使用 compiler_worker 的方法）
        text = await compiler_worker._extract_text(file_path, title, src_id)

        if not text or len(text.strip()) < MIN_AUDIO_TEXT_LENGTH:
            logger.warning(f"文本不足 {MIN_AUDIO_TEXT_LENGTH} 字，跳过: {title} [{src_id}]")
            stats.add_record(src_id, file_type, "skipped", time.time() - start, error="no_text")
            return src_id, True, "skipped"

        # 清洗文本
        with contextlib.suppress(ValueError, AttributeError):
            text = sanitize_pdf_content(text)

        # 清洗标题
        try:
            clean_title = sanitize_filename(title)
        except (ValueError, AttributeError):
            clean_title = Path(title).stem

        # LLM 编译
        logger.info(f"编译中: {clean_title[:60]} [{src_id}]")
        stats.api_calls += 1

        try:
            if compiler_worker.llm:
                summary = await compiler_worker.llm.generate_summary(text, clean_title)
            else:
                logger.error(f"主通道 LLM 未配置: {title} [{src_id}]")
                stats.add_record(
                    src_id, file_type, "failed", time.time() - start, error="no_llm_client"
                )
                return src_id, False, "failed"
        except (TimeoutError, RuntimeError, ValueError, KeyError, ConnectionError) as e:
            logger.error(f"LLM 编译异常: {title} [{src_id}]: {e}")
            stats.add_record(
                src_id, file_type, "failed", time.time() - start, error=f"llm_exception:{e}"
            )
            return src_id, False, "failed"

        if not summary:
            logger.error(f"摘要生成失败: {title} [{src_id}]")
            stats.add_record(src_id, file_type, "failed", time.time() - start, error="llm_failed")
            return src_id, False, "failed"

        stats.api_success += 1

        # 质量评分
        score = score_summary_quality_v4(summary)

        # 提取 concepts_data
        concepts = summary.get("concepts", [])
        concepts_names = [c.get("name", "") if isinstance(c, dict) else str(c) for c in concepts]

        # 更新 manifest（保留已有 summary，只更新 compiled_summary）
        update_manifest_status(
            KB_PATH,
            src_id,
            status="compiled",
            quality_score=score,
            compiled_summary={
                "concepts": concepts_names,
                "concepts_data": concepts,
            },
        )

        duration = time.time() - start
        logger.info(f"编译成功: {clean_title[:60]} [{src_id}] 质量={score} 耗时={duration:.1f}s")
        stats.add_record(src_id, file_type, "success", duration, quality_score=score)
        return src_id, True, "success"


# ============================================================
# 主流程
# ============================================================


async def run_recompile(logger, stats: CompileStats, max_files: int = 0) -> None:
    """主重新编译流程"""
    # 1. 筛选
    logger.info("=" * 60)
    logger.info("重新编译缺少 concepts_data 的 manifest")
    logger.info("=" * 60)

    manifests = find_missing_concepts_data(logger)
    logger.info(f"缺少 concepts_data 的 manifest: {len(manifests)} 个")

    if not manifests:
        logger.info("没有需要重新编译的文件")
        return

    # 2. 按优先级排序
    manifests = sort_by_priority(manifests)

    # 类型分布
    type_counts = Counter(m.get("type", "unknown") for m in manifests)
    logger.info("类型分布:")
    for t, c in type_counts.most_common():
        logger.info(f"  {t}: {c}")

    if max_files > 0:
        manifests = manifests[:max_files]
        logger.info(f"限制编译数量: {max_files}")

    # 3. 分批
    total = len(manifests)
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(f"分批策略: {total} 个文件, {total_batches} 批, 每批 {BATCH_SIZE} 个")
    logger.info(f"并发数: {MAX_CONCURRENCY}, 批间延迟: {BATCH_DELAY}s")

    # 4. 创建 LLM 客户端
    try:
        from openai import AsyncOpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY 环境变量未设置")
            return None
        base_url = _settings.api_base
        async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    except (ImportError, OSError, ValueError) as e:
        logger.error(f"无法创建 LLM 客户端: {e}")
        return

    # 5. 逐批编译
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    adaptive_delay = [2.0]
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("收到中断信号，正在安全退出...")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, AttributeError):
            loop.add_signal_handler(sig, signal_handler)

    consecutive_batch_failures = 0

    for batch_idx in range(total_batches):
        if shutdown_event.is_set():
            logger.info("用户中断，停止编译")
            break

        batch_start = batch_idx * BATCH_SIZE
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = manifests[batch_start:batch_end]
        batch_num = batch_idx + 1

        logger.info(f"\n{'=' * 40}")
        logger.info(f"第 {batch_num}/{total_batches} 批 ({len(batch)} 个文件)")
        logger.info(f"{'=' * 40}")

        batch_start_time = time.time()
        batch_success = 0
        batch_failed = 0
        batch_skipped = 0

        tasks = []
        for m in batch:
            if shutdown_event.is_set():
                break
            tasks.append(
                recompile_single(m, async_client, logger, semaphore, adaptive_delay, stats)
            )

        for future in asyncio.as_completed(tasks):
            if shutdown_event.is_set():
                break
            src_id, ok, status = await future
            if status == "success":
                batch_success += 1
            elif status == "skipped":
                batch_skipped += 1
            else:
                batch_failed += 1

            done = stats.total_success + stats.total_failed + stats.total_skipped
            logger.info(
                f"  总进度: {done}/{total} "
                f"(成功={stats.total_success}, 失败={stats.total_failed}, "
                f"跳过={stats.total_skipped}, "
                f"吞吐={stats.throughput} 文件/分钟)"
            )

        batch_duration = time.time() - batch_start_time
        stats.add_batch(
            batch_num,
            total_batches,
            batch,
            batch_success,
            batch_failed,
            batch_skipped,
            batch_duration,
        )

        logger.info(
            f"第 {batch_num}/{total_batches} 批完成: "
            f"成功={batch_success}, 失败={batch_failed}, 跳过={batch_skipped}, "
            f"耗时={batch_duration:.1f}s"
        )

        # 失败率检查
        batch_total = batch_success + batch_failed
        if batch_total > 0 and (batch_failed / batch_total) > 0.5:
            consecutive_batch_failures += 1
            logger.warning(
                f"批次失败率 {batch_failed}/{batch_total} > 50%，连续失败批次数: {consecutive_batch_failures}"
            )
            if consecutive_batch_failures >= 3:
                logger.error("连续 3 批失败率超过 50%，停止编译")
                break
        else:
            consecutive_batch_failures = 0

        # 批间延迟
        if batch_num < total_batches and not shutdown_event.is_set():
            logger.info(f"等待 {BATCH_DELAY}s 后开始下一批...")
            await asyncio.sleep(BATCH_DELAY)

    # 6. 写入日志
    append_log(
        KB_PATH,
        "recompile_concepts",
        f"重新编译完成: 成功={stats.total_success}, 失败={stats.total_failed}, "
        f"跳过={stats.total_skipped}, 总计={total}, 耗时={stats.elapsed}s",
    )


# ============================================================
# 验证
# ============================================================


def verify_results(logger, sample_size: int = 10) -> dict:
    """随机抽样验证编译结果"""
    import random

    sources_dir = KB_PATH / "manifests" / "sources"
    compiled_with_concepts = []

    for f in sources_dir.glob("SRC-*.json"):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("status") == "compiled":
                cs = data.get("compiled_summary", {})
                cd = cs.get("concepts_data", []) if cs else []
                if cd and isinstance(cd, list) and len(cd) > 0:
                    compiled_with_concepts.append(data)
        except (OSError, json.JSONDecodeError, KeyError):
            continue

    if not compiled_with_concepts:
        logger.info("没有找到包含 concepts_data 的 manifest")
        return {"sample_size": 0, "passed": 0, "failed": 0}

    sample = random.sample(compiled_with_concepts, min(sample_size, len(compiled_with_concepts)))
    passed = 0
    failed = 0

    required_fields = {
        "name",
        "description",
        "explanation",
        "applications",
        "related_concepts",
        "example",
    }

    for m in sample:
        src_id = m["id"]
        cs = m.get("compiled_summary", {})
        cd = cs.get("concepts_data", [])

        issues = []
        # 检查 concepts_data 完整性
        if not cd or len(cd) == 0:
            issues.append("concepts_data 为空")
        else:
            for i, c in enumerate(cd):
                missing = required_fields - set(c.keys())
                if missing:
                    issues.append(f"concepts[{i}] 缺失字段: {missing}")

        # 检查 summary 完整性
        summary = m.get("summary", {})
        if not summary:
            issues.append("summary 为空")
        else:
            if not summary.get("one_line"):
                issues.append("summary.one_line 为空")
            if not summary.get("key_points"):
                issues.append("summary.key_points 为空")
            if not summary.get("detailed_summary"):
                issues.append("summary.detailed_summary 为空")

        if issues:
            failed += 1
            logger.warning(f"验证失败 [{src_id}]: {'; '.join(issues)}")
        else:
            passed += 1
            logger.info(
                f"验证通过 [{src_id}]: concepts_data={len(cd)} 个, quality={m.get('quality_score', 0)}"
            )

    logger.info(f"\n验证结果: 通过={passed}/{len(sample)}, 失败={failed}/{len(sample)}")
    return {"sample_size": len(sample), "passed": passed, "failed": failed}


# ============================================================
# 报告生成
# ============================================================


def generate_report(stats: CompileStats, verify_result: dict, logger) -> str:
    """生成优化报告"""
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("知识库编译优化报告")
    report_lines.append(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 70)

    # 1. 编译统计
    report_lines.append("\n## 1. 编译统计")
    report_lines.append(
        f"  总文件数: {stats.total_success + stats.total_failed + stats.total_skipped}"
    )
    report_lines.append(f"  成功编译: {stats.total_success}")
    report_lines.append(f"  失败编译: {stats.total_failed}")
    report_lines.append(f"  跳过文件: {stats.total_skipped}")
    report_lines.append(
        f"  平均编译时间/文件: {stats.elapsed / max(1, stats.total_success + stats.total_failed):.1f}s"
    )
    report_lines.append(f"  总耗时: {stats.elapsed:.1f}s ({stats.elapsed / 60:.1f}min)")

    # 2. 性能指标
    report_lines.append("\n## 2. 性能指标")
    report_lines.append(f"  编译吞吐量: {stats.throughput} 文件/分钟")
    report_lines.append(f"  API 调用次数: {stats.api_calls}")
    report_lines.append(f"  API 成功次数: {stats.api_success}")
    if stats.api_calls > 0:
        report_lines.append(f"  API 成功率: {stats.api_success / stats.api_calls * 100:.1f}%")

    # 3. 质量指标
    report_lines.append("\n## 3. 质量指标")
    scores = [
        r["quality_score"]
        for r in stats.file_records
        if r["status"] == "success" and r["quality_score"] > 0
    ]
    if scores:
        report_lines.append(f"  平均质量分数: {sum(scores) / len(scores):.1f}")
        report_lines.append(f"  最高质量分数: {max(scores)}")
        report_lines.append(f"  最低质量分数: {min(scores)}")
        low_quality = sum(1 for s in scores if s < 80)
        report_lines.append(f"  低质量文件(<80分): {low_quality}")
        report_lines.append(
            f"  concepts_data 完整率: {stats.total_success}/{stats.total_success + stats.total_failed} ({stats.total_success / max(1, stats.total_success + stats.total_failed) * 100:.1f}%)"
        )

    # 验证结果
    report_lines.append("\n## 4. 验证结果")
    report_lines.append(f"  抽样数量: {verify_result.get('sample_size', 0)}")
    report_lines.append(f"  验证通过: {verify_result.get('passed', 0)}")
    report_lines.append(f"  验证失败: {verify_result.get('failed', 0)}")

    # 4. 错误分析
    report_lines.append("\n## 5. 错误分析")
    error_records = [r for r in stats.file_records if r["status"] == "failed"]
    if error_records:
        error_types = Counter(r.get("error", "unknown") for r in error_records)
        report_lines.append("  错误类型分布:")
        for err, count in error_types.most_common():
            report_lines.append(f"    {err}: {count}")

        report_lines.append("\n  失败文件列表:")
        for r in error_records[:20]:
            report_lines.append(f"    {r['src_id']} ({r['type']}): {r['error']}")
        if len(error_records) > 20:
            report_lines.append(f"    ... 还有 {len(error_records) - 20} 个")
    else:
        report_lines.append("  无错误")

    # 5. 分批统计
    report_lines.append("\n## 6. 分批统计")
    for bs in stats.batch_stats:
        report_lines.append(
            f"  第 {bs['batch_num']}/{bs['total_batches']} 批: "
            f"文件={bs['file_count']}, 成功={bs['success']}, "
            f"失败={bs['failed']}, 跳过={bs['skipped']}, "
            f"耗时={bs['duration']}s"
        )

    # 6. 优化建议
    report_lines.append("\n## 7. 优化建议")
    # 动态计算待编译文件数
    total_manifests = len(list((KB_PATH / "manifests" / "sources").glob("SRC-*.json")))
    # 使用 stats 中的数据更准确
    successfully_compiled = stats.total_success
    remaining = total_manifests - successfully_compiled
    report_lines.append(f"  待编译文件总数: {remaining}")
    if stats.total_failed > 0:
        report_lines.append(f"  建议排查 {stats.total_failed} 个失败文件的错误原因")
    if stats.throughput > 0:
        eta_min = remaining / stats.throughput
        report_lines.append(f"  按当前吞吐量估算，剩余文件需 {eta_min:.0f} 分钟")
    report_lines.append("  建议使用 glm-4-flash 模型，并发数 8，批量 50 个/批")

    report = "\n".join(report_lines)
    return report


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    logger = setup_logging()

    parser = argparse.ArgumentParser(description="重新编译缺少 concepts_data 的 manifest")
    parser.add_argument("--max-files", type=int, default=0, help="最大编译文件数（0=不限）")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="每批文件数")
    parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY, help="并发数")
    parser.add_argument("--skip-compile", action="store_true", help="跳过编译，只生成报告")
    args = parser.parse_args()

    if args.batch_size != BATCH_SIZE:
        BATCH_SIZE = args.batch_size
    if args.concurrency != MAX_CONCURRENCY:
        MAX_CONCURRENCY = args.concurrency

    stats = CompileStats()

    if not args.skip_compile:
        asyncio.run(run_recompile(logger, stats, max_files=args.max_files))

    # 验证
    verify_result = verify_results(logger, sample_size=10)

    # 生成报告
    report = generate_report(stats, verify_result, logger)
    logger.info(f"\n{report}")

    # 保存报告
    report_dir = KB_PATH / "monitoring-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = (
        report_dir / f"recompile_concepts_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    report_file.write_text(report, encoding="utf-8")
    logger.info(f"\n报告已保存: {report_file}")
