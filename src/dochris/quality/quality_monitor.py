#!/usr/bin/env python3
"""
Knowledge Base Quality Monitor
定期监控知识库编译系统的质量和进度
"""

import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

# 路径配置
KB_PATH = Path.home() / ".openclaw/knowledge-base"
PROGRESS_FILE = KB_PATH / "progress.json"
LOGS_PATH = KB_PATH / "logs"
SUMMARIES_PATH = KB_PATH / "wiki" / "summaries"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("quality-monitor")


def load_progress() -> dict:
    """加载进度文件"""
    if not PROGRESS_FILE.exists():
        logger.error(f"进度文件不存在: {PROGRESS_FILE}")
        return {}

    with open(PROGRESS_FILE, encoding="utf-8") as f:
        return cast(dict, json.load(f))


def check_progress(data: dict) -> dict:
    """检查编译进度"""
    indexed_files = data.get("indexed_files", {})
    failed_files = data.get("failed_files", {})

    indexed = len(indexed_files)
    failed = len(failed_files)
    total = indexed + failed
    success_rate = (indexed / total * 100) if total > 0 else 0

    return {"indexed": indexed, "failed": failed, "total": total, "success_rate": success_rate}


def check_latest_log() -> dict:
    """检查最新日志文件"""
    log_files = sorted(LOGS_PATH.glob("phase2_*.log"), reverse=True)

    if not log_files:
        logger.warning("没有找到日志文件")
        return {"log_file": None, "stats": {}}

    latest_log = log_files[0]

    # 分析日志
    stats = {
        "content_filter": 0,
        "json_parse_error": 0,
        "markitdown_failed": 0,
        "success": 0,
        "failed": 0,
    }

    with open(latest_log, encoding="utf-8") as f:
        for line in f:
            if "内容过滤错误" in line:
                stats["content_filter"] += 1
            elif "JSON parse failed" in line or "json-repair" in line:
                stats["json_parse_error"] += 1
            elif "markitdown" in line and "失败" in line:
                stats["markitdown_failed"] += 1
            elif "摘要已写入" in line:
                stats["success"] += 1
            elif "摘要生成失败" in line:
                stats["failed"] += 1

    total_errors = stats["content_filter"] + stats["json_parse_error"] + stats["markitdown_failed"]
    total_requests = stats["success"] + stats["failed"] + total_errors

    content_filter_rate = (
        (stats["content_filter"] / total_requests * 100) if total_requests > 0 else 0
    )

    return {
        "log_file": latest_log.name,
        "stats": stats,
        "total_requests": total_requests,
        "content_filter_rate": content_filter_rate,
    }


def check_latest_summary_quality() -> dict:
    """检查最新摘要质量"""
    summary_files = sorted(SUMMARIES_PATH.glob("*.md"), reverse=True)

    if not summary_files:
        return {"quality_score": None, "structure": {}}

    latest_summary = summary_files[0]

    # 检查结构完整性
    structure = {
        "one_line": False,
        "key_points": False,
        "detailed_summary": False,
        "concepts": False,
    }

    with open(latest_summary, encoding="utf-8") as f:
        content = f.read()
        structure["one_line"] = "## 一句话摘要" in content
        structure["key_points"] = "## 要点" in content
        structure["detailed_summary"] = "## 详细摘要" in content
        structure["concepts"] = "## 相关概念" in content

    # 提取质量分数（如果有的话）
    quality_match = re.search(r"质量分数[：:]\s*(\d+)", content)
    quality_score = int(quality_match.group(1)) if quality_match else None

    return {"file": latest_summary.name, "quality_score": quality_score, "structure": structure}


def check_process_status() -> dict:
    """检查进程状态"""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = result.stdout.splitlines()
        processes = [
            line for line in lines if re.search(r"phase2_compilation|pdf_compilation", line)
        ]
        return {
            "running": len(processes) > 0,
            "process_count": len(processes),
            "processes": processes,
        }
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
        logger.error(f"检查进程状态失败: {e}")
        return {"running": False, "process_count": 0, "processes": []}


def check_alerts(
    progress_info: dict[str, Any],
    log_info: dict[str, Any],
    quality_info: dict[str, Any],
    process_info: dict[str, Any],
) -> list[str]:
    """检查告警条件"""
    alerts = []

    # 告警 1: 内容过滤率过高
    if log_info.get("content_filter_rate", 0) > 40:
        alerts.append(f"🚨 严重告警: 内容过滤率 {log_info['content_filter_rate']:.1f}% > 40%")

    # 告警 2: 成功率过低
    if progress_info.get("success_rate", 0) < 50:
        alerts.append(f"⚠️ 告警: 成功率 {progress_info['success_rate']:.1f}% < 50%")

    # 告警 3: 进程意外停止
    if not process_info.get("running", True):
        alerts.append("🚨 严重告警: phase2_compilation 进程未运行")

    # 告警 4: 质量分数过低
    if quality_info.get("quality_score", 100) is not None and quality_info["quality_score"] < 70:
        alerts.append(f"⚠️ 告警: 最新摘要质量分数 {quality_info['quality_score']} < 70")

    # 告警 5: 连续失败（通过日志检查）
    if log_info.get("stats", {}).get("failed", 0) > 10:
        alerts.append(f"⚠️ 告警: 日志中有 {log_info['stats']['failed']} 个失败文件")

    return alerts


def generate_report(
    progress_info: dict[str, Any],
    log_info: dict[str, Any],
    quality_info: dict[str, Any],
    process_info: dict[str, Any],
) -> str:
    """生成监控报告"""
    report = []
    report.append("=" * 60)
    report.append("知识库编译质量监控报告")
    report.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 60)
    report.append("")

    # 1. 编译进度
    report.append("📊 编译进度")
    report.append("-" * 40)
    report.append(f"待编译总数: {progress_info['total']} 个")
    report.append(f"已编译: {progress_info['indexed']} 个")
    report.append(f"失败: {progress_info['failed']} 个")
    report.append(f"成功率: {progress_info['success_rate']:.1f}%")
    report.append("")

    # 2. 日志统计
    report.append("📋 日志统计")
    report.append("-" * 40)
    stats = log_info.get("stats", {})
    report.append(f"最新日志: {log_info.get('log_file', '无')}")
    report.append(f"总请求数: {log_info.get('total_requests', 0)}")
    report.append(f"成功编译: {stats.get('success', 0)} 个")
    report.append(f"失败: {stats.get('failed', 0)} 个")
    report.append(
        f"内容过滤: {stats.get('content_filter', 0)} 个 ({log_info.get('content_filter_rate', 0):.1f}%)"
    )
    report.append(f"JSON 解析错误: {stats.get('json_parse_error', 0)} 个")
    report.append(f"markitdown 失败: {stats.get('markitdown_failed', 0)} 个")
    report.append("")

    # 3. 进程状态
    report.append("⚙️  进程状态")
    report.append("-" * 40)
    if process_info.get("running", False):
        report.append(f"✅ 运行中 ({process_info['process_count']} 个进程)")
    else:
        report.append("❌ 未运行")
    report.append("")

    # 4. 质量检查
    report.append("✨ 质量检查")
    report.append("-" * 40)
    if quality_info.get("quality_score") is not None:
        report.append(f"最新摘要: {quality_info.get('file', '无')}")
        report.append(f"质量分数: {quality_info['quality_score']}/100")
    structure = quality_info.get("structure", {})
    report.append("结构完整性:")
    report.append(f"  - 一句话摘要: {'✅' if structure.get('one_line') else '❌'}")
    report.append(f"  - 要点: {'✅' if structure.get('key_points') else '❌'}")
    report.append(f"  - 详细摘要: {'✅' if structure.get('detailed_summary') else '❌'}")
    report.append(f"  - 相关概念: {'✅' if structure.get('concepts') else '❌'}")
    report.append("")

    # 5. 告警
    alerts = check_alerts(progress_info, log_info, quality_info, process_info)
    if alerts:
        report.append("🚨 告警")
        report.append("-" * 40)
        for alert in alerts:
            report.append(alert)
    else:
        report.append("✅ 无告警")
    report.append("")

    return "\n".join(report)


def main() -> None:
    """主函数"""
    logger.info("开始质量监控检查...")

    # 1. 加载进度
    progress_data = load_progress()
    if not progress_data:
        logger.error("无法加载进度数据")
        return

    # 2. 检查各项
    progress_info = check_progress(progress_data)
    log_info = check_latest_log()
    quality_info = check_latest_summary_quality()
    process_info = check_process_status()

    # 3. 生成报告
    report = generate_report(progress_info, log_info, quality_info, process_info)
    print(report)

    # 4. 检查是否有严重告警
    alerts = check_alerts(progress_info, log_info, quality_info, process_info)
    severe_alerts = [a for a in alerts if "🚨" in a]

    if severe_alerts:
        logger.error("发现严重告警，请立即处理！")
        # 扩展点：可以在此添加外部通知功能（如飞书、邮件等）
        # send_feishu_notification(severe_alerts)


if __name__ == "__main__":
    main()
