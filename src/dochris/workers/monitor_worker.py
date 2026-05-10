#!/usr/bin/env python3
"""
监控 Worker
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

# 导入 manifest 管理
from dochris.manifest import get_all_manifests, get_default_workspace

logger = logging.getLogger(__name__)


class MonitorWorker:
    """监控 Worker"""

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace if workspace is not None else get_default_workspace()

    def generate_progress_report(self) -> dict[str, Any]:
        """生成进度报告"""
        manifests = get_all_manifests(self.workspace)

        status_count: dict[str, int] = {}
        for manifest in manifests:
            status = manifest.get("status", "unknown")
            status_count[status] = status_count.get(status, 0) + 1

        total = len(manifests)

        # 计算质量分数统计
        quality_scores = [
            m.get("quality_score", 0) for m in manifests if m.get("quality_score", 0) > 0
        ]

        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        max_quality = max(quality_scores) if quality_scores else 0
        min_quality = min(quality_scores) if quality_scores else 0

        report = {
            "total": total,
            "status": status_count,
            "compiled_percentage": (status_count.get("compiled", 0) / total * 100)
            if total > 0
            else 0,
            "quality_stats": {
                "average": round(avg_quality, 1),
                "max": max_quality,
                "min": min_quality,
                "samples": len(quality_scores),
            },
            "timestamp": datetime.now().isoformat(),
        }

        return report

    def print_report(self) -> None:
        """打印报告"""
        report = self.generate_progress_report()

        logger.info("=" * 60)
        logger.info("编译进度报告 - v7 (模块化重构版)")
        logger.info("=" * 60)
        logger.info(f"总计: {report['total']}")
        logger.info(f"报告时间: {report['timestamp']}")

        logger.info("状态分布:")
        for status, count in sorted(report["status"].items()):
            percentage = (count / report["total"] * 100) if report["total"] > 0 else 0
            logger.info(f"  {status:15} {count:5} 个 ({percentage:5.1f}%)")

        if report["quality_stats"]["samples"] > 0:
            logger.info("质量评分统计:")
            logger.info(f"  平均分数: {report['quality_stats']['average']}/100")
            logger.info(f"  最高分数: {report['quality_stats']['max']}/100")
            logger.info(f"  最低分数: {report['quality_stats']['min']}/100")
            logger.info(f"  样本数量: {report['quality_stats']['samples']}")

        logger.info(f"完成率: {report['compiled_percentage']:.1f}%")
        logger.info("=" * 60)

    def save_report(self, report_path: Path | None = None) -> None:
        """保存报告到文件"""
        if report_path is None:
            report_path = (
                self.workspace
                / "monitoring-reports"
                / f"compile_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

        report_path.parent.mkdir(parents=True, exist_ok=True)

        report_data = self.generate_progress_report()

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Report saved to: {report_path}")

    def get_summary_text(self) -> str:
        """获取简化的文本摘要"""
        report = self.generate_progress_report()

        lines = [
            f"总计: {report['total']} 个",
            f"完成: {report['status'].get('compiled', 0)} 个 ({report['compiled_percentage']:.1f}%)",
            f"失败: {report['status'].get('failed', 0)} 个",
            f"待编译: {report['status'].get('ingested', 0)} 个",
            f"平均质量: {report['quality_stats']['average']}/100",
        ]

        return "\n".join(lines)
