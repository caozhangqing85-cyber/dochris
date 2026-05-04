#!/usr/bin/env python3
"""
测试 quality_monitor.py 质量监控脚本
12+ 测试用例
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestLoadProgress(unittest.TestCase):
    """测试加载进度"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("dochris.quality.quality_monitor.PROGRESS_FILE")
    def test_load_progress_existing(self, mock_progress_file):
        """测试加载存在的进度文件"""
        mock_progress_file.exists.return_value = True
        expected_data = {"indexed_files": {}, "failed_files": {}}

        with patch("builtins.open", mock_open(read_data=json.dumps(expected_data))):
            from dochris.quality.quality_monitor import load_progress

            result = load_progress()

        self.assertEqual(result, expected_data)

    @patch("dochris.quality.quality_monitor.PROGRESS_FILE")
    def test_load_progress_nonexistent(self, mock_progress_file):
        """测试加载不存在的进度文件"""
        mock_progress_file.exists.return_value = False

        from dochris.quality.quality_monitor import load_progress

        result = load_progress()

        self.assertEqual(result, {})


class TestCheckProgress(unittest.TestCase):
    """测试进度检查"""

    def test_check_progress_calculates_stats(self):
        """测试计算进度统计"""
        from dochris.quality.quality_monitor import check_progress

        data = {"indexed_files": {"file1": {}, "file2": {}}, "failed_files": {"file3": {}}}

        result = check_progress(data)

        self.assertEqual(result["indexed"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["total"], 3)
        self.assertAlmostEqual(result["success_rate"], 200 / 3)

    def test_check_progress_empty_data(self):
        """测试空数据进度检查"""
        from dochris.quality.quality_monitor import check_progress

        data = {"indexed_files": {}, "failed_files": {}}
        result = check_progress(data)

        self.assertEqual(result["indexed"], 0)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["success_rate"], 0)


class TestCheckLatestLog(unittest.TestCase):
    """测试检查最新日志"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        (self.temp_path / "logs").mkdir()

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("dochris.quality.quality_monitor.LOGS_PATH")
    def test_check_log_no_files(self, mock_logs_path):
        """测试没有日志文件"""
        mock_logs_path.glob.return_value = []

        from dochris.quality.quality_monitor import check_latest_log

        result = check_latest_log()

        self.assertIsNone(result["log_file"])

    @patch("dochris.quality.quality_monitor.LOGS_PATH")
    def test_check_log_parses_errors(self, mock_logs_path):
        """测试解析日志错误"""
        import os
        import tempfile

        from dochris.quality.quality_monitor import check_latest_log

        # 创建临时日志文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write("[INFO] 内容过滤错误: file1.pdf\n")
            f.write("[ERROR] JSON parse failed: file2.pdf\n")
            f.write("[INFO] markitdown 失败: file3.pdf\n")
            f.write("[INFO] 摘要已写入: file4.pdf\n")
            f.write("[ERROR] 摘要生成失败: file5.pdf\n")
            temp_log_path = f.name

        try:
            # 创建 Path 对象
            from pathlib import Path

            mock_log_path = Path(temp_log_path)
            mock_logs_path.glob.return_value = [mock_log_path]

            result = check_latest_log()

            self.assertEqual(result["stats"]["content_filter"], 1)
            self.assertEqual(result["stats"]["json_parse_error"], 1)
            self.assertEqual(result["stats"]["markitdown_failed"], 1)
            self.assertEqual(result["stats"]["success"], 1)
            self.assertEqual(result["stats"]["failed"], 1)
        finally:
            os.unlink(temp_log_path)


class TestCheckLatestSummaryQuality(unittest.TestCase):
    """测试检查最新摘要质量"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        (self.temp_path / "wiki" / "summaries").mkdir(parents=True)

    def tearDown(self):
        """清理测试环境"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("dochris.quality.quality_monitor.SUMMARIES_PATH")
    def test_check_quality_no_files(self, mock_summaries_path):
        """测试没有摘要文件"""
        mock_summaries_path.glob.return_value = []

        from dochris.quality.quality_monitor import check_latest_summary_quality

        result = check_latest_summary_quality()

        self.assertIsNone(result["quality_score"])

    @patch("dochris.quality.quality_monitor.SUMMARIES_PATH")
    def test_check_quality_structure(self, mock_summaries_path):
        """测试检查摘要结构"""
        import os
        import tempfile

        from dochris.quality.quality_monitor import check_latest_summary_quality

        content = """# 测试摘要

## 一句话摘要
这是一句话摘要

## 要点
- 要点1

## 详细摘要
详细内容

## 相关概念
- 概念1
"""

        # 创建临时摘要文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            temp_file_path = f.name

        try:
            # 创建 Path 对象
            from pathlib import Path

            mock_file_path = Path(temp_file_path)
            mock_summaries_path.glob.return_value = [mock_file_path]

            result = check_latest_summary_quality()

            self.assertTrue(result["structure"]["one_line"])
            self.assertTrue(result["structure"]["key_points"])
            self.assertTrue(result["structure"]["detailed_summary"])
            self.assertTrue(result["structure"]["concepts"])
        finally:
            os.unlink(temp_file_path)


class TestCheckProcessStatus(unittest.TestCase):
    """测试检查进程状态"""

    @patch("os.popen")
    def test_process_running(self, mock_popen):
        """测试进程运行中"""
        mock_result = MagicMock()
        mock_result.read.return_value = "user 1234 0.0 phase2_compilation.py\n"
        mock_popen.return_value = mock_result

        from dochris.quality.quality_monitor import check_process_status

        result = check_process_status()

        self.assertTrue(result["running"])
        self.assertEqual(result["process_count"], 1)

    @patch("os.popen")
    def test_process_not_running(self, mock_popen):
        """测试进程未运行"""
        mock_result = MagicMock()
        mock_result.read.return_value = "\n"
        mock_popen.return_value = mock_result

        from dochris.quality.quality_monitor import check_process_status

        result = check_process_status()

        self.assertFalse(result["running"])
        self.assertEqual(result["process_count"], 0)


class TestCheckAlerts(unittest.TestCase):
    """测试告警检查"""

    def test_high_content_filter_alert(self):
        """测试高内容过滤率告警"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 80}
        log_info = {"content_filter_rate": 50}  # > 40%
        quality_info = {"quality_score": 75}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)

        self.assertTrue(any("内容过滤率" in a for a in alerts))

    def test_low_success_rate_alert(self):
        """测试低成功率告警"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 30}  # < 50%
        log_info = {"content_filter_rate": 10, "stats": {}}
        quality_info = {"quality_score": 75}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)

        self.assertTrue(any("成功率" in a for a in alerts))

    def test_process_stopped_alert(self):
        """测试进程停止告警"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 80}
        log_info = {"content_filter_rate": 10, "stats": {}}
        quality_info = {"quality_score": 75}
        process_info = {"running": False}  # 进程未运行

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)

        self.assertTrue(any("进程未运行" in a for a in alerts))

    def test_low_quality_score_alert(self):
        """测试低质量分数告警"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 80}
        log_info = {"content_filter_rate": 10, "stats": {}}
        quality_info = {"quality_score": 50}  # < 70
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)

        self.assertTrue(any("质量分数" in a for a in alerts))

    def test_no_alerts_when_all_ok(self):
        """测试一切正常时无告警"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 90}
        log_info = {"content_filter_rate": 20, "stats": {"failed": 5}}
        quality_info = {"quality_score": 85}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)

        # 检查严重告警
        severe = [a for a in alerts if "🚨" in a]
        self.assertEqual(len(severe), 0)


class TestGenerateReport(unittest.TestCase):
    """测试报告生成"""

    def test_generate_report_structure(self):
        """测试报告结构"""
        from dochris.quality.quality_monitor import generate_report

        progress_info = {"indexed": 100, "failed": 10, "total": 110, "success_rate": 90.9}
        log_info = {
            "log_file": "test.log",
            "total_requests": 110,
            "stats": {},
            "content_filter_rate": 10,
        }
        quality_info = {"file": "test.md", "quality_score": 85, "structure": {}}
        process_info = {"running": True, "process_count": 1}

        report = generate_report(progress_info, log_info, quality_info, process_info)

        self.assertIsInstance(report, str)
        self.assertIn("编译进度", report)
        self.assertIn("日志统计", report)
        self.assertIn("进程状态", report)
        self.assertIn("质量检查", report)


class TestScoreDistribution(unittest.TestCase):
    """测试分数分布"""

    def test_score_distribution_calculation(self):
        """测试分数分布计算"""
        manifests = [
            {"quality_score": 30},
            {"quality_score": 50},
            {"quality_score": 70},
            {"quality_score": 90},
        ]

        distribution = {"0-40": 0, "41-60": 0, "61-84": 0, "85-100": 0}

        for m in manifests:
            score = m["quality_score"]
            if score < 41:
                distribution["0-40"] += 1
            elif score < 61:
                distribution["41-60"] += 1
            elif score < 85:
                distribution["61-84"] += 1
            else:
                distribution["85-100"] += 1

        self.assertEqual(distribution["0-40"], 1)
        self.assertEqual(distribution["41-60"], 1)
        self.assertEqual(distribution["61-84"], 1)
        self.assertEqual(distribution["85-100"], 1)


class TestCheckProgressEdgeCases(unittest.TestCase):
    """进度检查边界条件"""

    def test_only_indexed_files(self):
        """只有成功文件"""
        from dochris.quality.quality_monitor import check_progress

        data = {"indexed_files": {"f1": {}, "f2": {}, "f3": {}}, "failed_files": {}}
        result = check_progress(data)

        self.assertEqual(result["indexed"], 3)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["success_rate"], 100.0)

    def test_only_failed_files(self):
        """只有失败文件"""
        from dochris.quality.quality_monitor import check_progress

        data = {"indexed_files": {}, "failed_files": {"f1": {}, "f2": {}}}
        result = check_progress(data)

        self.assertEqual(result["indexed"], 0)
        self.assertEqual(result["failed"], 2)
        self.assertEqual(result["success_rate"], 0.0)

    def test_missing_keys(self):
        """缺少键"""
        from dochris.quality.quality_monitor import check_progress

        result = check_progress({})

        self.assertEqual(result["indexed"], 0)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["total"], 0)

    def test_extra_keys_ignored(self):
        """额外键被忽略"""
        from dochris.quality.quality_monitor import check_progress

        data = {
            "indexed_files": {"f1": {}},
            "failed_files": {},
            "extra_key": "ignored",
        }
        result = check_progress(data)

        self.assertEqual(result["total"], 1)


class TestCheckAlertsEdgeCases(unittest.TestCase):
    """告警检查边界条件"""

    def test_all_alerts_triggered(self):
        """所有告警同时触发"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 30}
        log_info = {"content_filter_rate": 60, "stats": {"failed": 20}}
        quality_info = {"quality_score": 50}
        process_info = {"running": False}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)

        self.assertGreater(len(alerts), 0)

    def test_none_quality_score_no_alert(self):
        """quality_score 为 None 时不触发质量告警"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 90}
        log_info = {"content_filter_rate": 10, "stats": {}}
        quality_info = {"quality_score": None}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)

        quality_alerts = [a for a in alerts if "质量分数" in a]
        self.assertEqual(len(quality_alerts), 0)

    def test_high_failed_count_alert(self):
        """高失败计数告警"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 80}
        log_info = {"content_filter_rate": 10, "stats": {"failed": 15}}
        quality_info = {"quality_score": 80}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)

        self.assertTrue(any("失败文件" in a for a in alerts))

    def test_boundary_success_rate(self):
        """成功率边界值"""
        from dochris.quality.quality_monitor import check_alerts

        # 刚好 50% 不应触发
        progress_info = {"success_rate": 50}
        log_info = {"content_filter_rate": 10, "stats": {}}
        quality_info = {"quality_score": 80}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)
        success_alerts = [a for a in alerts if "成功率" in a]
        self.assertEqual(len(success_alerts), 0)

    def test_just_below_success_threshold(self):
        """成功率刚好低于阈值"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 49.9}
        log_info = {"content_filter_rate": 10, "stats": {}}
        quality_info = {"quality_score": 80}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)
        self.assertTrue(any("成功率" in a for a in alerts))


class TestGenerateReportEdgeCases(unittest.TestCase):
    """报告生成边界条件"""

    def test_report_with_no_data(self):
        """无数据报告"""
        from dochris.quality.quality_monitor import generate_report

        progress_info = {"indexed": 0, "failed": 0, "total": 0, "success_rate": 0}
        log_info = {"log_file": None, "total_requests": 0, "stats": {}, "content_filter_rate": 0}
        quality_info = {"quality_score": None, "structure": {}}
        process_info = {"running": False, "process_count": 0}

        report = generate_report(progress_info, log_info, quality_info, process_info)

        self.assertIn("编译进度", report)
        self.assertIn("未运行", report)

    def test_report_with_quality_score(self):
        """包含质量分数的报告"""
        from dochris.quality.quality_monitor import generate_report

        progress_info = {"indexed": 10, "failed": 0, "total": 10, "success_rate": 100}
        log_info = {
            "log_file": "test.log",
            "total_requests": 10,
            "stats": {
                "success": 10,
                "failed": 0,
                "content_filter": 0,
                "json_parse_error": 0,
                "markitdown_failed": 0,
            },
            "content_filter_rate": 0,
        }
        quality_info = {
            "file": "test.md",
            "quality_score": 92,
            "structure": {
                "one_line": True,
                "key_points": True,
                "detailed_summary": True,
                "concepts": True,
            },
        }
        process_info = {"running": True, "process_count": 1}

        report = generate_report(progress_info, log_info, quality_info, process_info)

        self.assertIn("92", report)
        self.assertIn("运行中", report)

    def test_report_contains_timestamp(self):
        """报告包含时间戳"""
        from dochris.quality.quality_monitor import generate_report

        progress_info = {"indexed": 0, "failed": 0, "total": 0, "success_rate": 0}
        log_info = {"log_file": None, "total_requests": 0, "stats": {}, "content_filter_rate": 0}
        quality_info = {"quality_score": None, "structure": {}}
        process_info = {"running": False, "process_count": 0}

        report = generate_report(progress_info, log_info, quality_info, process_info)

        self.assertIn("时间:", report)


class TestLoadProgressEdgeCases(unittest.TestCase):
    """进度加载边界条件"""

    @patch("dochris.quality.quality_monitor.PROGRESS_FILE")
    def test_load_progress_with_invalid_json(self, mock_progress_file):
        """无效 JSON 进度文件"""
        mock_progress_file.exists.return_value = True

        with patch("builtins.open", mock_open(read_data="invalid json")):
            from dochris.quality.quality_monitor import load_progress

            # 应抛出 JSONDecodeError 或返回空
            try:
                load_progress()
            except json.JSONDecodeError:
                pass  # 预期行为

    @patch("dochris.quality.quality_monitor.PROGRESS_FILE")
    def test_load_progress_with_empty_file(self, mock_progress_file):
        """空进度文件"""
        mock_progress_file.exists.return_value = True

        with patch("builtins.open", mock_open(read_data="{}")):
            from dochris.quality.quality_monitor import load_progress

            result = load_progress()
            self.assertEqual(result, {})


class TestCheckProgressLargeScale(unittest.TestCase):
    """大规模数据进度检查"""

    def test_large_number_of_files(self):
        """大量文件的进度计算"""
        from dochris.quality.quality_monitor import check_progress

        indexed = {f"file_{i}": {"score": 80} for i in range(1000)}
        failed = {f"fail_{i}": {"error": "err"} for i in range(200)}
        data = {"indexed_files": indexed, "failed_files": failed}

        result = check_progress(data)

        self.assertEqual(result["indexed"], 1000)
        self.assertEqual(result["failed"], 200)
        self.assertEqual(result["total"], 1200)
        self.assertAlmostEqual(result["success_rate"], 1000 / 1200 * 100)


class TestCheckAlertsBoundaryValues(unittest.TestCase):
    """告警边界值测试"""

    def test_content_filter_rate_exactly_40(self):
        """内容过滤率恰好 40% — 不触发"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 90}
        log_info = {"content_filter_rate": 40, "stats": {}}
        quality_info = {"quality_score": 80}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)
        filter_alerts = [a for a in alerts if "内容过滤率" in a]
        self.assertEqual(len(filter_alerts), 0)

    def test_content_filter_rate_just_above_40(self):
        """内容过滤率刚超过 40% — 触发"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 90}
        log_info = {"content_filter_rate": 40.1, "stats": {}}
        quality_info = {"quality_score": 80}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)
        self.assertTrue(any("内容过滤率" in a for a in alerts))

    def test_quality_score_exactly_70(self):
        """质量分数恰好 70 — 不触发"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 90}
        log_info = {"content_filter_rate": 10, "stats": {}}
        quality_info = {"quality_score": 70}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)
        quality_alerts = [a for a in alerts if "质量分数" in a]
        self.assertEqual(len(quality_alerts), 0)

    def test_quality_score_69(self):
        """质量分数 69 — 触发"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 90}
        log_info = {"content_filter_rate": 10, "stats": {}}
        quality_info = {"quality_score": 69}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)
        self.assertTrue(any("质量分数" in a for a in alerts))

    def test_failed_count_exactly_10(self):
        """失败数恰好 10 — 不触发"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 90}
        log_info = {"content_filter_rate": 10, "stats": {"failed": 10}}
        quality_info = {"quality_score": 80}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)
        failed_alerts = [a for a in alerts if "失败文件" in a]
        self.assertEqual(len(failed_alerts), 0)

    def test_failed_count_11(self):
        """失败数 11 — 触发"""
        from dochris.quality.quality_monitor import check_alerts

        progress_info = {"success_rate": 90}
        log_info = {"content_filter_rate": 10, "stats": {"failed": 11}}
        quality_info = {"quality_score": 80}
        process_info = {"running": True}

        alerts = check_alerts(progress_info, log_info, quality_info, process_info)
        self.assertTrue(any("失败文件" in a for a in alerts))


class TestCheckLatestLogEdgeCases(unittest.TestCase):
    """日志检查边界条件"""

    @patch("dochris.quality.quality_monitor.LOGS_PATH")
    def test_empty_log_file(self, mock_logs_path):
        """空日志文件"""
        import os
        import tempfile

        from dochris.quality.quality_monitor import check_latest_log

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            temp_log_path = f.name

        try:
            mock_logs_path.glob.return_value = [Path(temp_log_path)]
            result = check_latest_log()

            self.assertEqual(result["stats"]["content_filter"], 0)
            self.assertEqual(result["stats"]["success"], 0)
            self.assertEqual(result["total_requests"], 0)
        finally:
            os.unlink(temp_log_path)

    @patch("dochris.quality.quality_monitor.LOGS_PATH")
    def test_log_with_json_repair_keyword(self, mock_logs_path):
        """日志包含 json-repair 关键词"""
        import os
        import tempfile

        from dochris.quality.quality_monitor import check_latest_log

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write("[INFO] json-repair applied to file.pdf\n")
            temp_log_path = f.name

        try:
            mock_logs_path.glob.return_value = [Path(temp_log_path)]
            result = check_latest_log()

            self.assertEqual(result["stats"]["json_parse_error"], 1)
        finally:
            os.unlink(temp_log_path)


class TestCheckLatestSummaryPartial(unittest.TestCase):
    """摘要部分结构检查"""

    @patch("dochris.quality.quality_monitor.SUMMARIES_PATH")
    def test_partial_structure_missing_concepts(self, mock_summaries_path):
        """缺少相关概念部分"""
        import os
        import tempfile

        from dochris.quality.quality_monitor import check_latest_summary_quality

        content = """# 测试摘要

## 一句话摘要
这是一句话摘要

## 要点
- 要点1

## 详细摘要
详细内容
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            temp_file_path = f.name

        try:
            mock_summaries_path.glob.return_value = [Path(temp_file_path)]
            result = check_latest_summary_quality()

            self.assertTrue(result["structure"]["one_line"])
            self.assertTrue(result["structure"]["key_points"])
            self.assertTrue(result["structure"]["detailed_summary"])
            self.assertFalse(result["structure"]["concepts"])
        finally:
            os.unlink(temp_file_path)

    @patch("dochris.quality.quality_monitor.SUMMARIES_PATH")
    def test_summary_with_quality_score(self, mock_summaries_path):
        """摘要包含质量分数"""
        import os
        import tempfile

        from dochris.quality.quality_monitor import check_latest_summary_quality

        content = """# 摘要

## 一句话摘要
测试

质量分数：88
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            temp_file_path = f.name

        try:
            mock_summaries_path.glob.return_value = [Path(temp_file_path)]
            result = check_latest_summary_quality()

            self.assertEqual(result["quality_score"], 88)
        finally:
            os.unlink(temp_file_path)


class TestGenerateReportWithAlerts(unittest.TestCase):
    """包含告警的报告"""

    def test_report_includes_alerts(self):
        """报告包含告警内容"""
        from dochris.quality.quality_monitor import generate_report

        progress_info = {"indexed": 50, "failed": 50, "total": 100, "success_rate": 50.0}
        log_info = {
            "log_file": "test.log",
            "total_requests": 100,
            "stats": {},
            "content_filter_rate": 10,
        }
        quality_info = {"quality_score": None, "structure": {}}
        process_info = {"running": False, "process_count": 0}

        report = generate_report(progress_info, log_info, quality_info, process_info)

        self.assertIn("告警", report)


if __name__ == "__main__":
    unittest.main()
