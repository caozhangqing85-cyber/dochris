"""
测试 workers/monitor_worker.py 模块
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# 导入 monitor_worker 模块


@pytest.fixture
def mock_workspace(tmp_path):
    """创建模拟工作区"""
    workspace = tmp_path / "kb"
    workspace.mkdir()
    (workspace / "manifests").mkdir()
    (workspace / "manifests" / "sources").mkdir(parents=True)
    return workspace


@pytest.fixture
def sample_manifests(mock_workspace):
    """创建示例 manifests"""
    manifests_data = [
        {
            "id": "SRC-0001",
            "status": "compiled",
            "title": "已编译文档",
            "quality_score": 95,
            "type": "pdf",
        },
        {
            "id": "SRC-0002",
            "status": "ingested",
            "title": "待编译文档",
            "type": "article",
        },
        {
            "id": "SRC-0003",
            "status": "failed",
            "title": "失败文档",
            "error_message": "llm_failed",
            "type": "pdf",
        },
        {
            "id": "SRC-0004",
            "status": "compiled",
            "title": "低质量文档",
            "quality_score": 70,
            "type": "ebook",
        },
        {
            "id": "SRC-0005",
            "status": "promoted_to_wiki",
            "title": "已晋升文档",
            "quality_score": 90,
            "type": "article",
        },
    ]

    for manifest in manifests_data:
        manifest_file = mock_workspace / "manifests" / "sources" / f"{manifest['id']}.json"
        manifest_file.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    return manifests_data


class TestMonitorWorkerInit:
    """测试 MonitorWorker 初始化"""

    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_init_sets_workspace(self, mock_get_workspace, mock_workspace):
        """测试初始化设置工作区"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace

        worker = MonitorWorker()

        assert worker.workspace == mock_workspace


class TestMonitorWorkerGenerateProgressReport:
    """测试进度报告生成"""

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_generate_report_with_manifests(self, mock_get_workspace, mock_get_all, sample_manifests):
        """测试生成有 manifest 的报告"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()
        report = worker.generate_progress_report()

        assert report["total"] == 5
        assert report["status"]["compiled"] == 2
        assert report["status"]["ingested"] == 1
        assert report["status"]["failed"] == 1
        assert report["status"]["promoted_to_wiki"] == 1
        assert report["compiled_percentage"] == 40.0  # 2/5 * 100

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_generate_report_empty(self, mock_get_workspace, mock_get_all, mock_workspace):
        """测试生成空报告"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = []

        worker = MonitorWorker()
        report = worker.generate_progress_report()

        assert report["total"] == 0
        assert report["compiled_percentage"] == 0

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_generate_report_quality_stats(self, mock_get_workspace, mock_get_all, sample_manifests):
        """测试质量统计"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()
        report = worker.generate_progress_report()

        assert report["quality_stats"]["average"] == 85.0  # (95 + 70 + 90) / 3
        assert report["quality_stats"]["max"] == 95
        assert report["quality_stats"]["min"] == 70
        assert report["quality_stats"]["samples"] == 3

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_generate_report_timestamp(self, mock_get_workspace, mock_get_all, sample_manifests):
        """测试报告时间戳"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()
        report = worker.generate_progress_report()

        assert "timestamp" in report
        assert len(report["timestamp"]) > 0


class TestMonitorWorkerPrintReport:
    """测试打印报告"""

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_print_report(self, mock_get_workspace, mock_get_all, sample_manifests, caplog):
        """测试打印报告"""
        import logging

        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()

        with caplog.at_level(logging.INFO, logger="dochris.workers.monitor_worker"):
            worker.print_report()

        # 验证 logger 有输出
        assert len(caplog.records) > 0

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_print_report_with_quality_stats(self, mock_get_workspace, mock_get_all, sample_manifests, caplog):
        """测试打印带质量统计的报告"""
        import logging

        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()

        with caplog.at_level(logging.INFO, logger="dochris.workers.monitor_worker"):
            worker.print_report()

        # 验证包含质量信息
        assert any("质量" in r.message or "quality" in r.message.lower() for r in caplog.records)

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_print_report_empty_workspace(self, mock_get_workspace, mock_get_all, mock_workspace, caplog):
        """测试打印空工作区报告"""
        import logging

        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = []

        worker = MonitorWorker()

        with caplog.at_level(logging.INFO, logger="dochris.workers.monitor_worker"):
            # 应该不抛出异常
            worker.print_report()


class TestMonitorWorkerSaveReport:
    """测试保存报告"""

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_save_report_default_path(self, mock_get_workspace, mock_get_all, mock_workspace):
        """测试保存报告到默认路径"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = []

        worker = MonitorWorker()
        report_path = mock_workspace / "monitoring-reports" / "test_report.json"

        worker.save_report(report_path)

        assert report_path.exists()

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_save_report_custom_path(self, mock_get_workspace, mock_get_all, mock_workspace, tmp_path):
        """测试保存报告到自定义路径"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = []

        worker = MonitorWorker()
        custom_path = tmp_path / "custom_report.json"

        worker.save_report(custom_path)

        assert custom_path.exists()

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_save_report_content(self, mock_get_workspace, mock_get_all, mock_workspace, sample_manifests):
        """测试保存报告内容"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()
        report_path = mock_workspace / "test_report.json"

        worker.save_report(report_path)

        content = report_path.read_text(encoding="utf-8")
        data = json.loads(content)

        assert data["total"] == 5
        assert "status" in data
        assert "quality_stats" in data


class TestMonitorWorkerGetSummaryText:
    """测试获取文本摘要"""

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_get_summary_text(self, mock_get_workspace, mock_get_all, sample_manifests):
        """测试获取文本摘要"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()
        summary = worker.get_summary_text()

        assert "总计: 5 个" in summary
        assert "完成: 2 个" in summary
        assert "失败: 1 个" in summary
        assert "待编译: 1 个" in summary
        assert "平均质量: 85.0/100" in summary

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_get_summary_text_empty(self, mock_get_workspace, mock_get_all, mock_workspace):
        """测试获取空摘要"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = []

        worker = MonitorWorker()
        summary = worker.get_summary_text()

        assert "总计: 0 个" in summary
        assert "完成: 0 个" in summary


class TestMonitorWorkerEdgeCases:
    """测试边界情况"""

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_handles_manifests_without_quality_score(self, mock_get_workspace, mock_get_all, mock_workspace):
        """测试处理没有质量分数的 manifest"""
        from dochris.workers.monitor_worker import MonitorWorker

        manifests = [
            {"id": "SRC-0001", "status": "compiled", "title": "文档1"},
            {"id": "SRC-0002", "status": "compiled", "title": "文档2", "quality_score": 80},
        ]

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = manifests

        worker = MonitorWorker()
        report = worker.generate_progress_report()

        # 应该只计算有质量分数的
        assert report["quality_stats"]["samples"] == 1
        assert report["quality_stats"]["average"] == 80

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_handles_zero_quality_scores(self, mock_get_workspace, mock_get_all, mock_workspace):
        """测试处理质量分数为 0 的情况"""
        from dochris.workers.monitor_worker import MonitorWorker

        manifests = [
            {"id": "SRC-0001", "status": "compiled", "title": "文档1", "quality_score": 0},
            {"id": "SRC-0002", "status": "compiled", "title": "文档2", "quality_score": 100},
        ]

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = manifests

        worker = MonitorWorker()
        report = worker.generate_progress_report()

        # 0 分应该被计入
        assert report["quality_stats"]["samples"] == 1  # 只有非 0 的被计入
        assert report["quality_stats"]["average"] == 100

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_calculates_compiled_percentage(self, mock_get_workspace, mock_get_all, mock_workspace):
        """测试编译百分比计算"""
        from dochris.workers.monitor_worker import MonitorWorker

        manifests = [
            {"id": "SRC-0001", "status": "compiled", "title": "文档1"},
            {"id": "SRC-0002", "status": "compiled", "title": "文档2"},
            {"id": "SRC-0003", "status": "ingested", "title": "文档3"},
        ]

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = manifests

        worker = MonitorWorker()
        report = worker.generate_progress_report()

        assert report["compiled_percentage"] == pytest.approx(66.67, abs=0.01)  # 2/3 * 100

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_handles_unknown_status(self, mock_get_workspace, mock_get_all, mock_workspace):
        """测试处理未知状态"""
        from dochris.workers.monitor_worker import MonitorWorker

        manifests = [
            {"id": "SRC-0001", "status": "unknown_status", "title": "文档1"},
            {"id": "SRC-0002", "status": "compiled", "title": "文档2"},
        ]

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = manifests

        worker = MonitorWorker()
        report = worker.generate_progress_report()

        assert report["status"]["unknown_status"] == 1


class TestMonitorWorkerReportFormatting:
    """测试报告格式化"""

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_report_has_header(self, mock_get_workspace, mock_get_all, sample_manifests, caplog):
        """测试报告有标题"""
        import logging

        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()
        with caplog.at_level(logging.INFO, logger="dochris.workers.monitor_worker"):
            worker.print_report()

        # 检查有分隔线输出
        assert any("=" * 10 in r.message for r in caplog.records)

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_report_shows_total(self, mock_get_workspace, mock_get_all, sample_manifests, caplog):
        """测试报告显示总数"""
        import logging

        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()
        with caplog.at_level(logging.INFO, logger="dochris.workers.monitor_worker"):
            worker.print_report()

        # 检查是否显示总数
        assert any("5" in r.message for r in caplog.records)

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_report_shows_completion_rate(self, mock_get_workspace, mock_get_all, sample_manifests, caplog):
        """测试报告显示完成率"""
        import logging

        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = sample_manifests

        worker = MonitorWorker()
        with caplog.at_level(logging.INFO, logger="dochris.workers.monitor_worker"):
            worker.print_report()

        # 检查是否显示完成率
        assert any("40" in r.message for r in caplog.records)


class TestMonitorWorkerErrorHandling:
    """测试错误处理"""

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_handles_corrupted_manifest_files(self, mock_get_workspace, mock_get_all, mock_workspace):
        """测试处理损坏的 manifest 文件"""
        from dochris.workers.monitor_worker import MonitorWorker

        # 创建损坏的 JSON 文件
        corrupted_file = mock_workspace / "manifests" / "sources" / "SRC-CORRUPT.json"
        corrupted_file.write_text("{ invalid json", encoding="utf-8")

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = []

        worker = MonitorWorker()

        # 应该不抛出异常
        report = worker.generate_progress_report()
        assert report["total"] == 0

    @patch('dochris.workers.monitor_worker.get_all_manifests')
    @patch('dochris.workers.monitor_worker.get_default_workspace')
    def test_save_report_creates_directory(self, mock_get_workspace, mock_get_all, mock_workspace):
        """测试保存报告时创建目录"""
        from dochris.workers.monitor_worker import MonitorWorker

        mock_get_workspace.return_value = mock_workspace
        mock_get_all.return_value = []

        worker = MonitorWorker()
        nested_path = mock_workspace / "deep" / "nested" / "report.json"

        worker.save_report(nested_path)

        assert nested_path.parent.exists()
        assert nested_path.exists()
